import json
import os
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from app.config import ROOT, load_env, provider
from app.llm import ModelError, chat
from app.prompts import render
from app.retrieval import index_status, search

load_env()
DB = ROOT / 'data' / 'knowledge.sqlite3'


def require_text(payload, key, maximum=4000):
    value = payload.get(key, '')
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'请填写{key}。')
    if len(value) > maximum:
        raise ValueError(f'{key} 内容过长。')
    return value.strip()


def limited_list(payload, key, maximum=5, text_limit=5000):
    value = payload.get(key, [])
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError(f'{key} 格式不正确。')
    if not all(isinstance(item, str) and len(item) <= text_limit for item in value):
        raise ValueError(f'{key} 格式不正确。')
    return value


def source_context(hits):
    return '\n\n'.join(f"[资料 {index}: {hit['source']}]\n{hit['content']}"
                       for index, hit in enumerate(hits, 1))


def answer(payload):
    question = require_text(payload, 'question')
    state = index_status(DB)
    if not state['chunks']:
        raise ValueError('请先运行 python index_knowledge.py 建立知识库索引。')
    hits = search(DB, question, limit=10)
    if not hits:
        return {'answer': '当前已接入知识库没有足够依据。请提供更具体的课程、章节或知识点。', 'sources': []}
    messages = [{'role': 'system', 'content': (ROOT / 'prompts' / 'runtime-system.txt').read_text(encoding='utf-8')}]
    history = payload.get('history', [])
    if not isinstance(history, list) or len(history) > 12:
        raise ValueError('对话历史格式不正确。')
    for item in history:
        if not isinstance(item, dict) or item.get('role') not in ('user', 'assistant'):
            raise ValueError('对话历史格式不正确。')
        text = item.get('content')
        if not isinstance(text, str) or len(text) > 5000:
            raise ValueError('对话历史内容过长。')
        messages.append({'role': item['role'], 'content': text})
    messages.append({'role': 'user', 'content': render('navigation.txt', {
        '_question': question, 'knowledge': source_context(hits),
    })})
    output = chat(provider('NAV'), messages)
    sources = [{'source': hit['source'], 'page': hit['page']} for hit in hits]
    return {'answer': output, 'sources': sources}


def quiz_question(payload):
    core = require_text(payload, 'core_question')
    task = require_text(payload, 'task_name', 200)
    task_type = require_text(payload, 'task_type', 50)
    difficulty = require_text(payload, 'difficulty', 50)
    hint = payload.get('hint', '关闭')
    question_types = limited_list(payload, 'question_types', maximum=3, text_limit=20)
    if not question_types or any(x not in ('单选题', '多选题', '判断题') for x in question_types):
        raise ValueError('请选择至少一种题型。')
    if task_type not in ('阶梯闯关', '主干生成') or difficulty not in ('简单', '较为简单', '适中', '较为困难', '困难'):
        raise ValueError('任务类型或难度不正确。')
    if hint not in ('开启', '关闭'):
        raise ValueError('对话提示设置不正确。')
    round_number = payload.get('round')
    if not isinstance(round_number, int) or isinstance(round_number, bool) or not 1 <= round_number <= 5:
        raise ValueError('练习轮次必须为 1 至 5。')
    previous = limited_list(payload, 'previous_questions', maximum=4)
    group = f"任务名称：{task}\n任务类型：{task_type}\n核心问题：{core}\n题型：{'、'.join(question_types)}\n难度：{difficulty}\n对话提示：{hint}"
    prompt = render('exercise-generate.txt', {
        'core_question': core, 'group1': group, 'current_round': round_number,
        'USER_INTERRUPTER_INPUT': difficulty, 'USER_INTERRUPTER_INPUT_1': '、'.join(question_types),
    })
    if previous:
        prompt += '\n\n此前已经出过的题目，请避免重复：\n' + '\n\n'.join(previous)
    question = chat(provider('QUIZ'), [{'role': 'user', 'content': prompt}])
    return {'question': question}


def quiz_grade(payload):
    question = require_text(payload, 'question', 6000)
    student_answer = require_text(payload, 'student_answer', 2000)
    round_number = payload.get('round')
    if not isinstance(round_number, int) or isinstance(round_number, bool) or not 1 <= round_number <= 5:
        raise ValueError('练习轮次必须为 1 至 5。')
    feedback = chat(provider('QUIZ'), [{'role': 'user', 'content': render('exercise-judge.txt', {
        'output': question, 'student_answer': student_answer,
    })}])
    record_prompt = render('exercise-record.txt', {'current_round': round_number, 'output': question,
                                                   'student_answer': student_answer, 'judge_feedback': feedback})
    try:
        record = chat(provider('QUIZ'), [{'role': 'user', 'content': record_prompt}])
        record_source = 'model'
    except ModelError:
        record = f'第 {round_number} 题\n题目：{question}\n学生回答：{student_answer}\n判题反馈：{feedback}'
        record_source = 'local'
    return {'feedback': feedback, 'record': record, 'record_source': record_source}


def quiz_report(payload):
    core = require_text(payload, 'core_question')
    config = require_text(payload, 'config', 3000)
    records = limited_list(payload, 'records', maximum=5, text_limit=12000)
    if not records:
        raise ValueError('至少完成一轮答题后才能生成报告。')
    prompt = render('exercise-report.txt', {'core_question': core, 'group1': config,
                                            'answer_records': '\n\n'.join(records)})
    return {'report': chat(provider('QUIZ'), [{'role': 'user', 'content': prompt}])}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / 'static'), **kwargs)

    def send_json(self, status, value):
        body = json.dumps(value, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/api/status':
            try:
                self.send_json(200, {'index': index_status(DB),
                                     'navigation_configured': all(provider('NAV').values()),
                                     'quiz_configured': all(provider('QUIZ').values())})
            except Exception:
                self.send_json(500, {'error': '读取索引状态失败，请重新建立索引。'})
            return
        super().do_GET()

    def do_POST(self):
        handlers = {'/api/ask': answer, '/api/quiz/question': quiz_question,
                    '/api/quiz/grade': quiz_grade, '/api/quiz/report': quiz_report}
        handler = handlers.get(urlparse(self.path).path)
        if handler is None:
            self.send_json(404, {'error': '接口不存在。'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length <= 0 or length > 200_000:
                raise ValueError('请求内容为空或过大。')
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError('请求格式不正确。')
            self.send_json(200, handler(payload))
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json(400, {'error': str(exc) if isinstance(exc, ValueError) else '请求格式不正确。'})
        except ModelError as exc:
            self.send_json(502, {'error': str(exc)})
        except Exception:
            self.send_json(500, {'error': '处理失败，请检查索引和服务日志。'})


if __name__ == '__main__':
    host = os.getenv('HOST', '127.0.0.1')
    port = int(os.getenv('PORT', '8765'))
    print(f'知脉已启动：http://{host}:{port}', flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()
