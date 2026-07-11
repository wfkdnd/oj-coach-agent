/* ── OJ Coach - 会话管理模块 ──────────────────────── */
/* 依赖：chat.js (addSystemMsg, addErrorMsg), ui.js (setBadge) */

const state = {
    sessionId: null,
    connected: false,
    isStreaming: false,
    cmdHistory: [],
    cmdHistoryIdx: -1,
};

// ── 命令历史 (localStorage) ──────────────────────────

function loadHistory() {
    try {
        return JSON.parse(localStorage.getItem('ojCoachCmdHistory') || '[]');
    } catch { return []; }
}

function saveToHistory(cmd) {
    if (!cmd.trim()) return;
    let history = loadHistory().filter(h => h !== cmd);
    history.push(cmd);
    if (history.length > 200) history = history.slice(-200);
    localStorage.setItem('ojCoachCmdHistory', JSON.stringify(history));
    state.cmdHistory = history;
}

// ── 会话管理 ────────────────────────────────────────

async function initSession() {
    try {
        const res = await fetch('/api/sessions', { method: 'POST' });
        const data = await res.json();
        if (data.ok) {
            state.sessionId = data.session_id;
            state.connected = true;
            setBadge('sessionBadge', `会话 ${data.session_id}`, 'badge status-ok');
            addSystemMsg(`会话已创建 (${data.session_id})`);
        }
    } catch (err) {
        setBadge('sessionBadge', '连接失败', 'badge status-err');
        console.error('创建会话失败:', err);
    }
    await checkLlmStatus();
}

// ── LLM 状态检查 ────────────────────────────────────

async function checkLlmStatus() {
    try {
        const res = await fetch('/api/status/llm');
        const data = await res.json();
        if (data.ok && data.llm_available) {
            setBadge('llmBadge', `LLM: ${data.model}`, 'badge status-ok');
        } else {
            const reason = data.reason || '未配置';
            setBadge('llmBadge', `LLM: ${reason}`, 'badge status-err');
        }
    } catch {
        setBadge('llmBadge', 'LLM: 检测失败', 'badge status-err');
    }
}

// ── 状态刷新 ────────────────────────────────────────

async function refreshStatus() {
    if (!state.sessionId) return;
    try {
        const res = await fetch(`/api/sessions/${state.sessionId}/status`);
        const data = await res.json();
        if (data.ok) updateUIFromStatus(data.status);
    } catch (err) {
        console.error('状态刷新失败:', err);
    }
}

function updateUIFromStatus(status) {
    if (status.language && status.language !== '未设置') {
        document.getElementById('langSelect').value = status.language;
    }
    const runBadge = document.getElementById('runStatus');
    if (status.last_run_result_set) {
        runBadge.textContent = '已运行';
        runBadge.className = 'badge status-ok';
    } else {
        runBadge.textContent = '未运行';
        runBadge.className = 'badge';
    }
    if (status.test_case_sources && Object.keys(status.test_case_sources).length > 0) {
        const srcText = Object.entries(status.test_case_sources)
            .map(([k, v]) => `${k}:${v}`).join(', ');
        const titleEl = document.getElementById('testCasePanelTitle');
        if (titleEl) titleEl.textContent = `测试用例 (${srcText})`;
    }
}

// ── 断线重连 + 状态指示 ────────────────────────────

let _connectionLost = false;

async function pingConnection() {
    if (!state.sessionId) return;
    try {
        const res = await fetch(`/api/sessions/${state.sessionId}/status`,
            { signal: AbortSignal.timeout(3000) });
        if (res.ok) {
            if (_connectionLost) {
                _connectionLost = false;
                setBadge('connBadge', '已连接', 'badge status-ok');
                const reconnectBtn = document.getElementById('reconnectBtn');
                if (reconnectBtn) reconnectBtn.style.display = 'none';
            }
            state.connected = true;
        } else {
            _markDisconnected();
        }
    } catch {
        _markDisconnected();
    }
}

function _markDisconnected() {
    if (!_connectionLost) {
        _connectionLost = true;
        setBadge('connBadge', '连接断开', 'badge status-err');
        const reconnectBtn = document.getElementById('reconnectBtn');
        if (reconnectBtn) {
            reconnectBtn.style.display = 'inline-block';
            reconnectBtn.textContent = '重连';
        }
    }
    state.connected = false;
}

// ── 多会话支持 ──────────────────────────────────────

async function switchSession(sessionId) {
    state.sessionId = sessionId;
    state.connected = true;
    setBadge('sessionBadge', `会话 ${sessionId}`, 'badge status-ok');
    const chat = document.getElementById('chatMessages');
    chat.innerHTML = `<div class="msg msg-system"><div class="msg-header">OJ Coach</div>已切换到会话 ${sessionId}</div>`;
    await refreshStatus();
    await checkLlmStatus();
}

async function createNewSession() {
    try {
        const res = await fetch('/api/sessions', { method: 'POST' });
        const data = await res.json();
        if (data.ok) {
            await switchSession(data.session_id);
            await refreshSessionList();
        }
    } catch (err) {
        addErrorMsg(`创建会话失败: ${err.message}`);
    }
}

async function refreshSessionList() {
    try {
        const res = await fetch('/api/sessions');
        const data = await res.json();
        if (data.ok) {
            const switcher = document.getElementById('sessionSwitcher');
            if (switcher) {
                const currentVal = switcher.value;
                switcher.innerHTML = data.sessions
                    .map(s => `<option value="${s.session_id}"${s.session_id === state.sessionId ? ' selected' : ''}>${s.session_id} (${s.language})</option>`)
                    .join('');
                switcher.innerHTML += '<option value="__new__">+ 新建会话</option>';
                if (currentVal && currentVal !== '__new__') switcher.value = currentVal;
            }
        }
    } catch { /* 列表刷新失败不影响使用 */ }
}
