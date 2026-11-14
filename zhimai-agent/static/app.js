const $ = (selector) => document.querySelector(selector);
const messages = $('#messages');
let history = [];
let quiz = null;

async function api(path, payload) {
  const response = await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || '请求失败，请稍后再试。');
  return data;
}

async function loadStatus() {
  try {
    const response = await fetch('/api/status');
    const data = await response.json();
    const index = data.index;
    const model = data.navigation_configured && data.quiz_configured ? '模型已配置' : '请配置模型服务';
    $('#status').textContent = index.chunks ? `${index.searchable_files}/${index.files} 份资料可检索 · ${model}` : `知识库尚未索引 · ${model}`;
  } catch { $('#status').textContent = '无法连接本地服务'; }
}

function switchTab(which) {
  for (const name of ['chat', 'quiz']) {
    const active = name === which;
    $(`#${name}-panel`).hidden = !active;
    $(`#tab-${name}`).classList.toggle('active', active);
    $(`#tab-${name}`).setAttribute('aria-selected', String(active));
  }
}
$('#tab-chat').addEventListener('click', () => switchTab('chat'));
$('#tab-quiz').addEventListener('click', () => switchTab('quiz'));

function addMessage(role, text, sources = []) {
  const welcome = messages.querySelector('.welcome');
  if (welcome) welcome.remove();
  const item = document.createElement('div'); item.className = `message ${role}`;
  const who = document.createElement('div'); who.className = 'who'; who.textContent = role === 'user' ? '你' : '小脉';
  const bubble = document.createElement('div'); bubble.className = 'bubble'; bubble.textContent = text;
  item.append(who, bubble);
  if (sources.length) {
    const refs = document.createElement('div'); refs.className = 'sources';
    const unique = [...new Set(sources.map(s => s.source))];
    refs.textContent = `检索资料：${unique.join('、')}`;
    item.append(refs);
  }
  messages.append(item); messages.scrollTop = messages.scrollHeight;
  return bubble;
}
$('#chat-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const field = $('#question'); const question = field.value.trim(); if (!question) return;
  const button = event.currentTarget.querySelector('button'); button.disabled = true;
  addMessage('user', question); field.value = '';
  const waiting = addMessage('assistant', '正在查找资料…');
  try {
    const data = await api('/api/ask', {question, history: history.slice(-12)});
    waiting.parentElement.remove(); addMessage('assistant', data.answer, data.sources);
    history.push({role: 'user', content: question}, {role: 'assistant', content: data.answer});
  } catch (error) { waiting.textContent = error.message; waiting.classList.add('error'); }
  finally { button.disabled = false; field.focus(); }
});
$('#question').addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); $('#chat-form').requestSubmit(); } });
document.querySelectorAll('.suggestions button').forEach(button => button.addEventListener('click', () => { $('#question').value = button.textContent; $('#chat-form').requestSubmit(); }));
$('#clear-chat').addEventListener('click', () => { history = []; messages.replaceChildren(); addMessage('assistant', '对话已清空。请告诉我你想了解的课程或知识点。'); });

function addQuizCard(title, content, isError = false) {
  const card = document.createElement('article'); card.className = 'quiz-card';
  const h = document.createElement('h3'); h.textContent = title;
  const p = document.createElement('p'); p.textContent = content; if (isError) p.className = 'error';
  card.append(h, p); $('#quiz-log').append(card); card.scrollIntoView({block: 'nearest'}); return card;
}
async function generateQuestion() {
  $('#answer-form').hidden = true; $('#next-question').hidden = true; $('#make-report').hidden = true;
  $('#quiz-round').textContent = `第 ${quiz.round} / 5 题`;
  const pending = addQuizCard('准备题目', '正在生成，请稍候…');
  try {
    const data = await api('/api/quiz/question', {...quiz.settings, round: quiz.round, previous_questions: quiz.questions});
    pending.remove(); quiz.current = data.question; quiz.questions.push(data.question);
    addQuizCard(`第 ${quiz.round} 题`, data.question); $('#student-answer').value = ''; $('#answer-form').hidden = false;
  } catch (error) { pending.remove(); addQuizCard('无法生成题目', error.message, true); $('#next-question').hidden = false; $('#next-question').textContent = '重试本题'; }
}
$('#quiz-config').addEventListener('submit', async event => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const types = form.getAll('question_types'); if (!types.length) { alert('请至少选择一种题型。'); return; }
  quiz = {round: 1, questions: [], records: [], current: '', settings: {
    task_name: form.get('task_name'), core_question: form.get('core_question'), task_type: form.get('task_type'),
    difficulty: form.get('difficulty'), hint: form.get('hint'), question_types: types,
  }};
  event.currentTarget.hidden = true; $('#quiz-session').hidden = false; $('#quiz-log').replaceChildren(); await generateQuestion();
});
$('#answer-form').addEventListener('submit', async event => {
  event.preventDefault(); const studentAnswer = $('#student-answer').value.trim(); if (!studentAnswer) return;
  const button = event.currentTarget.querySelector('button'); button.disabled = true;
  const pending = addQuizCard('判题中', '正在生成反馈…');
  try {
    const data = await api('/api/quiz/grade', {question: quiz.current, student_answer: studentAnswer, round: quiz.round});
    pending.remove(); addQuizCard('你的回答', studentAnswer); addQuizCard('判题反馈', data.feedback);
    quiz.records.push(data.record); $('#answer-form').hidden = true;
    if (quiz.round < 5) { $('#next-question').textContent = '下一题 →'; $('#next-question').hidden = false; }
    else $('#make-report').hidden = false;
  } catch (error) { pending.remove(); addQuizCard('无法判题', error.message, true); }
  finally { button.disabled = false; }
});
$('#next-question').addEventListener('click', async () => {
  if (quiz.records.length === quiz.round) quiz.round += 1;
  await generateQuestion();
});
$('#make-report').addEventListener('click', async event => {
  event.currentTarget.disabled = true; const pending = addQuizCard('学习报告', '正在整理…');
  try {
    const config = `任务：${quiz.settings.task_name}；类型：${quiz.settings.task_type}；题型：${quiz.settings.question_types.join('、')}；难度：${quiz.settings.difficulty}；对话提示：${quiz.settings.hint}`;
    const data = await api('/api/quiz/report', {core_question: quiz.settings.core_question, config, records: quiz.records});
    pending.remove(); addQuizCard('学习质量评估报告', data.report); event.currentTarget.hidden = true;
  } catch (error) { pending.remove(); addQuizCard('无法生成报告', error.message, true); }
  finally { event.currentTarget.disabled = false; }
});
$('#reset-quiz').addEventListener('click', () => { quiz = null; $('#quiz-session').hidden = true; $('#quiz-config').hidden = false; });
loadStatus();
