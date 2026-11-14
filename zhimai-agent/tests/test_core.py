import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen

import server
from app.prompts import render
from app.retrieval import build_index, index_status, query_tokens, search


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        notes = self.root / 'notes'
        notes.mkdir()
        (notes / '信号.md').write_text('采样定理说明采样频率与信号频率的关系。', encoding='utf-8')
        (notes / '代数.md').write_text('矩阵的秩与线性代数中的定理有关。', encoding='utf-8')
        self.db = self.root / 'test.sqlite3'
        build_index(notes, self.db)

    def tearDown(self):
        self.temp.cleanup()

    def test_chinese_query_prefers_relevant_source(self):
        results = search(self.db, '采样定理需要哪些前置知识？')
        self.assertEqual(results[0]['source'], '信号.md')
        self.assertIn('采样', results[0]['content'])

    def test_generic_overlap_does_not_fabricate_evidence(self):
        self.assertEqual(search(self.db, '量子纠缠定理'), [])

    def test_index_reports_files_and_chunks(self):
        self.assertEqual(index_status(self.db)['files'], 2)
        self.assertEqual(index_status(self.db)['chunks'], 2)

    def test_missing_local_source_fails_without_destroying_old_index(self):
        with self.assertRaises(ValueError):
            build_index(self.root / 'notes', self.db, source_dir=self.root / 'missing')
        self.assertEqual(index_status(self.db)['files'], 2)

    def test_navigation_uses_retrieved_material(self):
        with patch.object(server, 'DB', self.db), patch.object(server, 'chat', return_value='有依据的回答') as model:
            result = server.answer({'question': '采样定理', 'history': []})
        self.assertEqual(result['answer'], '有依据的回答')
        self.assertEqual(result['sources'][0]['source'], '信号.md')
        self.assertIn('采样频率', model.call_args.args[1][-1]['content'])

    def test_local_source_refreshes_bundled_course_notes(self):
        bundled = self.root / 'notes' / 'local-notes'
        bundled.mkdir()
        (bundled / '课程.md').write_text('旧课程笔记', encoding='utf-8')
        live = self.root / 'source' / '知识库' / '大学课程知识库'
        live.mkdir(parents=True)
        (live / '课程.md').write_text('新课程笔记采样定理', encoding='utf-8')
        build_index(self.root / 'notes', self.db, source_dir=self.root / 'source')
        found = search(self.db, '新课程笔记采样定理')
        self.assertTrue(any('新课程笔记' in result['content'] for result in found))
        self.assertFalse(any('旧课程笔记' in result['content'] for result in found))


class FlowTests(unittest.TestCase):
    def test_template_does_not_reinterpret_user_placeholders(self):
        result = render('navigation.txt', {'_question': '{{knowledge}}', 'knowledge': '证据内容'})
        self.assertIn('{{knowledge}}', result)
        self.assertIn('证据内容', result)

    def test_quiz_validation_and_generation(self):
        payload = {'task_name': '信号', 'core_question': '采样定理', 'task_type': '阶梯闯关',
                   'difficulty': '适中', 'hint': '开启', 'question_types': ['单选题'],
                   'round': 2, 'previous_questions': ['上一题']}
        with patch.object(server, 'chat', return_value='第二题') as model:
            result = server.quiz_question(payload)
        self.assertEqual(result['question'], '第二题')
        self.assertIn('上一题', model.call_args.args[1][0]['content'])
        with self.assertRaises(ValueError):
            server.quiz_question({**payload, 'round': 6})

    def test_quiz_grade_falls_back_to_local_record(self):
        with patch.object(server, 'chat', side_effect=['回答正确', server.ModelError('失败')]):
            result = server.quiz_grade({'question': '一加一？', 'student_answer': '二', 'round': 1})
        self.assertEqual(result['feedback'], '回答正确')
        self.assertEqual(result['record_source'], 'local')
        self.assertIn('二', result['record'])

    def test_http_serves_frontend_and_status(self):
        httpd = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            base = f'http://127.0.0.1:{httpd.server_port}'
            with urlopen(base + '/') as response:
                self.assertIn('课程知识链路导航', response.read().decode('utf-8'))
            with urlopen(base + '/api/status') as response:
                self.assertEqual(response.status, 200)
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
