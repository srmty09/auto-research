const API = '/api';

let token = localStorage.getItem('token');
let currentSessionId = null;
let selectedModel = '';

function apiUrl(path) { return `${API}${path}`; }

async function api(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...options.headers };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(apiUrl(path), { ...options, headers });
  if (res.status === 401) { logout(); throw new Error('Unauthorized'); }
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    const err = new Error(body.detail?.message || body.detail || 'Request failed');
    err.status = res.status;
    err.body = body;
    throw err;
  }
  return res.json();
}

function escHtml(str) {
  if (!str) return '';
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

// Auth
function showPage(id) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById(id).classList.add('active');
}

function logout() {
  token = null;
  localStorage.removeItem('token');
  currentSessionId = null;
  showPage('auth-page');
}

async function handleLogin(e) {
  e.preventDefault();
  const errEl = document.getElementById('login-error');
  errEl.textContent = '';
  try {
    const data = await api('/auth/login', {
      method: 'POST', body: JSON.stringify({
        username: document.getElementById('login-username').value,
        password: document.getElementById('login-password').value,
      }),
    });
    token = data.access_token;
    localStorage.setItem('token', data.access_token);
    await initMain();
  } catch (err) { errEl.textContent = err.message; }
}

async function handleRegister(e) {
  e.preventDefault();
  const errEl = document.getElementById('register-error');
  errEl.textContent = '';
  try {
    const data = await api('/auth/register', {
      method: 'POST', body: JSON.stringify({
        username: document.getElementById('register-username').value,
        password: document.getElementById('register-password').value,
      }),
    });
    token = data.access_token;
    localStorage.setItem('token', data.access_token);
    await initMain();
  } catch (err) { errEl.textContent = err.message; }
}

// Main
async function initMain() {
  const [user, models] = await Promise.all([
    api('/auth/me'),
    api('/models').catch(() => []),
  ]);
  document.getElementById('username-display').textContent = user.username;
  populateModels(models);
  showPage('main-page');
  newChat();
  await loadSessions();
}

function populateModels(models) {
  const sel = document.getElementById('model-select');
  if (models.length === 0) {
    sel.innerHTML = '<option value="">Default</option>';
    return;
  }
  const saved = localStorage.getItem('selectedModel') || models[0]?.id || '';
  selectedModel = saved;
  sel.innerHTML = models.map(m =>
    `<option value="${m.id}" ${m.id === saved ? 'selected' : ''}>${m.name}</option>`
  ).join('');
  sel.addEventListener('change', () => {
    selectedModel = sel.value;
    localStorage.setItem('selectedModel', selectedModel);
  });
}

// Chat state
let messages = [];
let running = false;

const chatMessages = document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const emptyState = document.getElementById('empty-state');

function newChat() {
  currentSessionId = null;
  messages = [];
  chatMessages.innerHTML = '<div class="empty-state" id="empty-state">\n          <h2>Auto Research</h2>\n          <p>Ask anything — I\'ll research, run code, and produce structured results.</p>\n          <div class="examples">\n            <button class="example-btn" data-goal="What is the current population of Japan?">Population of Japan</button>\n            <button class="example-btn" data-goal="Research the current CEO of NVIDIA and write their biography">CEO of NVIDIA</button>\n            <button class="example-btn" data-goal="Calculate 15% of 8472">Calculate 15% of 8472</button>\n          </div>\n        </div>';
  document.querySelectorAll('.session-item').forEach(el => el.classList.remove('active'));
  chatInput.value = '';
  chatInput.style.height = 'auto';
  chatInput.focus();
  attachExampleListeners();
}

function scrollToBottom() {
  requestAnimationFrame(() => {
    chatMessages.scrollTop = chatMessages.scrollHeight;
  });
}

function addMessage(msg) {
  messages.push(msg);
  emptyState.style.display = 'none';
  renderMessage(msg);
  scrollToBottom();
}

function renderMessage(msg) {
  if (msg.role === 'user') {
    const el = document.createElement('div');
    el.className = 'message user';
    el.innerHTML = `<div class="msg-bubble">${escHtml(msg.content)}</div>`;
    chatMessages.appendChild(el);
  } else if (msg.role === 'agent') {
    const el = document.createElement('div');
    el.className = 'message agent';

    let html = `<div class="msg-bubble">${escHtml(msg.content)}</div>`;

    const log = msg.result?.log || [];
    if (log.length > 0) {
      const showByDefault = msg.expandReasoning;
      html += `<div class="reasoning-bar" onclick="toggleReasoning(this)">
        <span class="count">${showByDefault ? 'Hide reasoning' : log.length + ' ' + (log.length === 1 ? 'step' : 'steps')}</span>
        <span class="arrow ${showByDefault ? 'open' : ''}">▾</span> ${showByDefault ? 'Hide reasoning' : 'Show reasoning'}
      </div>
      <div class="reasoning-steps${showByDefault ? ' open' : ''}">`;

      log.forEach((step, i) => {
        const sn = step.step || i + 1;
        const tool = step.tool ? escHtml(step.tool) : '';
        html += `<div class="step">
          <div class="step-header" onclick="toggleStep(this)">
            <span class="arrow">▾</span>
            <span class="step-num">Step ${sn}</span>
            ${tool ? '<span>— ' + tool + '</span>' : '<span>thought</span>'}
          </div>
          <div class="step-body">
            ${step.thought ? `<div class="step-label">Thought</div><div class="step-text">${escHtml(step.thought)}</div>` : ''}
            ${step.input ? `<div class="step-label">Input</div><div class="step-code">${escHtml(JSON.stringify(step.input, null, 2))}</div>` : ''}
            ${step.output ? `<div class="step-label">Output</div><div class="step-text">${escHtml(step.output)}</div>` : ''}
          </div>
        </div>`;
      });

      html += `</div>`;
    }

    if (msg.result) {
      const status = msg.result.success ? '' : 'Failed after ';
      const meta = `${status}${msg.result.steps} step${msg.result.steps === 1 ? '' : 's'}` +
        (msg.result.time ? ` · ${msg.result.time.toFixed(1)}s` : '');
      html += `<div class="msg-meta">${meta}</div>`;
    }

    el.innerHTML = html;
    chatMessages.appendChild(el);
  }
}

// Toggle reasoning
window.toggleReasoning = function(el) {
  const steps = el.nextElementSibling;
  const arrow = el.querySelector('.arrow');
  const isOpen = steps.classList.toggle('open');
  arrow.classList.toggle('open', isOpen);
  el.querySelector('.count').textContent = isOpen
    ? 'Hide reasoning'
    : `${steps.querySelectorAll('.step').length} ${steps.querySelectorAll('.step').length === 1 ? 'step' : 'steps'}`;
  scrollToBottom();
};

window.toggleStep = function(el) {
  const body = el.nextElementSibling;
  const arrow = el.querySelector('.arrow');
  body.classList.toggle('open');
  arrow.classList.toggle('open');
};

// Typing indicator
let typingEl = null;

function showTyping() {
  if (typingEl) return;
  typingEl = document.createElement('div');
  typingEl.className = 'typing';
  typingEl.innerHTML = '<div class="dot"></div><div class="dot"></div><div class="dot"></div>';
  chatMessages.appendChild(typingEl);
  scrollToBottom();
}

function hideTyping() {
  if (typingEl) { typingEl.remove(); typingEl = null; }
}

// Send message
async function sendMessage(text) {
  if (!text.trim() || running) return;

  running = true;
  sendBtn.disabled = true;
  sendBtn.textContent = '...';
  chatInput.disabled = true;

  const goal = text.trim();
  addMessage({ role: 'user', content: goal });
  chatInput.value = '';
  chatInput.style.height = 'auto';
  showTyping();

  try {
    let result;
    const body = { model: selectedModel };

    if (currentSessionId) {
      body.session_id = currentSessionId;
      body.message = goal;
      body.max_steps = 10;
      result = await api('/agent/followup', { method: 'POST', body: JSON.stringify(body) });
    } else {
      body.goal = goal;
      body.max_steps = 15;
      result = await api('/agent/run', { method: 'POST', body: JSON.stringify(body) });
      currentSessionId = result.session_id;
    }

    hideTyping();
    addMessage({ role: 'agent', content: result.final_answer, result });
    await loadSessions();
  } catch (err) {
    hideTyping();

    if (err.body?.detail?.error === 'rate_limit') {
      const model = err.body.detail.model || 'this model';
      addMessage({
        role: 'agent',
        content: `⚠️ **Rate limit reached on ${model}**\n\nThe API is temporarily rate-limited. Try switching to a different model using the dropdown below and send your message again.`,
      });
    } else {
      addMessage({ role: 'agent', content: 'Error: ' + err.message });
    }
  } finally {
    running = false;
    sendBtn.disabled = false;
    sendBtn.textContent = 'Send';
    chatInput.disabled = false;
    chatInput.focus();
  }
}

// Sessions
async function loadSessions() {
  const list = document.getElementById('session-list');
  try {
    const sessions = await api('/sessions');
    list.innerHTML = sessions.length === 0
      ? '<p style="color: var(--text2); font-size: 13px; padding: 8px;">No sessions yet</p>'
      : sessions.map(s => `
        <div class="session-item" data-id="${s.session_id}">
          <div class="goal-text">${escHtml(s.goal)}</div>
          <div class="meta">${s.steps} steps · ${s.time.toFixed(1)}s</div>
        </div>
      `).join('');
    document.querySelectorAll('.session-item').forEach(el => {
      el.addEventListener('click', () => loadSession(el.dataset.id));
    });
  } catch (err) { list.innerHTML = `<p style="color: var(--danger);">Error loading sessions</p>`; }
}

async function loadSession(sessionId) {
  try {
    const s = await api(`/sessions/${sessionId}`);
    currentSessionId = sessionId;

    chatMessages.innerHTML = '';
    emptyState.style.display = 'none';

    addMessage({ role: 'user', content: s.goal });
    addMessage({ role: 'agent', content: s.final_answer, result: s, expandReasoning: true });

    document.querySelectorAll('.session-item').forEach(el => {
      el.classList.toggle('active', el.dataset.id === sessionId);
    });
  } catch (err) { alert('Failed to load session: ' + err.message); }
}

// Event listeners
document.getElementById('login-form').addEventListener('submit', handleLogin);
document.getElementById('register-form').addEventListener('submit', handleRegister);
document.getElementById('logout-btn').addEventListener('click', logout);
document.getElementById('new-chat-btn').addEventListener('click', newChat);

sendBtn.addEventListener('click', () => {
  const text = chatInput.value;
  if (text.trim()) sendMessage(text);
});

chatInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    const text = chatInput.value;
    if (text.trim()) sendMessage(text);
  }
});

chatInput.addEventListener('input', () => {
  chatInput.style.height = 'auto';
  chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
});

function attachExampleListeners() {
  document.querySelectorAll('.example-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      sendMessage(btn.dataset.goal);
    });
  });
}
attachExampleListeners();

// Auth tabs
document.querySelectorAll('.auth-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.auth-form').forEach(f => f.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById(`${tab.dataset.tab}-form`).classList.add('active');
  });
});

// Init
if (token) {
  initMain().catch(() => { logout(); });
}
