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
    if (
        Array.isArray(status.test_cases)
        && !window.__testCasesDirty
        && typeof _renderTestCaseList === 'function'
    ) {
        const incomingCases = status.test_cases.map((item, index) => ({
            name: String(item.name || item['名称'] || `用例 ${index + 1}`),
            source: String(item.source || item['来源'] || '后端同步'),
            stdin: String(item.stdin || ''),
            expected_output: String(item.expected_output || ''),
        }));
        if (JSON.stringify(incomingCases) !== JSON.stringify(window.__testCases || [])) {
            window.__testCases = incomingCases;
            _renderTestCaseList();
        }
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
    window.__testCases = [];
    window.__testCasesDirty = false;
    if (typeof _renderTestCaseList === 'function') _renderTestCaseList();
    toggleReadingLog(false);
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

// ── 阶段 6/7 阅读日志 ──────────────────────────────

function toggleReadingLog(forceOpen) {
    const drawer = document.getElementById('readingLogDrawer');
    const backdrop = document.getElementById('readingLogBackdrop');
    const button = document.getElementById('readingLogBtn');
    if (!drawer || !backdrop || !button) return;

    const shouldOpen = typeof forceOpen === 'boolean'
        ? forceOpen
        : !drawer.classList.contains('show');
    drawer.classList.toggle('show', shouldOpen);
    backdrop.classList.toggle('show', shouldOpen);
    button.classList.toggle('active', shouldOpen);
    if (shouldOpen) loadReadingLog();
}

function _isReadingLogOpen() {
    return Boolean(document.getElementById('readingLogDrawer')?.classList.contains('show'));
}

async function loadReadingLog() {
    if (!state.sessionId) return;
    const statusEl = document.getElementById('readingLogStatus');
    const snapshotEl = document.getElementById('readingLogSnapshot');
    const eventsEl = document.getElementById('readingLogEvents');
    if (!statusEl || !snapshotEl || !eventsEl) return;

    statusEl.textContent = '正在读取…';
    try {
        const [contextRes, eventsRes] = await Promise.all([
            fetch(`/api/sessions/${state.sessionId}/context`),
            fetch(`/api/sessions/${state.sessionId}/events?limit=30`),
        ]);
        if (!contextRes.ok || !eventsRes.ok) throw new Error('阅读日志接口不可用');
        const contextData = await contextRes.json();
        const eventsData = await eventsRes.json();
        _renderReadingLogStatus(contextData);
        _renderReadingLogSnapshot(contextData.snapshot || {});
        _renderReadingLogEvents(eventsData.events || []);
    } catch (err) {
        statusEl.textContent = `读取失败：${err.message}`;
        snapshotEl.textContent = '暂无快照';
        eventsEl.textContent = '暂无事件';
    }
}

function _renderReadingLogStatus(context) {
    const container = document.getElementById('readingLogStatus');
    const count = document.getElementById('readingLogCount');
    if (!container) return;
    if (count) count.textContent = String(context.event_count || 0);
    container.replaceChildren();

    const chips = [
        [`事件 ${context.event_count || 0}`, ''],
        [`对话 ${context.conversation_message_count || 0}`, ''],
        [`距上次压缩 ${context.events_since_last_compress || 0}`, ''],
        [context.should_compress ? '已达到压缩阈值' : '尚未达到阈值', context.should_compress ? 'warning' : 'success'],
    ];
    for (const [text, className] of chips) {
        const chip = document.createElement('span');
        chip.className = `reading-log-chip ${className}`.trim();
        chip.textContent = text;
        container.appendChild(chip);
    }
}

function _renderReadingLogSnapshot(snapshot) {
    const container = document.getElementById('readingLogSnapshot');
    if (!container) return;
    if (!snapshot || snapshot.is_empty) {
        container.textContent = '暂无快照，可使用 /compress 手动压缩。';
        return;
    }
    const parts = [
        `**压缩模式：** ${snapshot.compression_mode || '未知'}`,
        `**来源事件：** ${snapshot.source_event_count || 0}`,
    ];
    const fields = [
        ['题目摘要', snapshot.problem_summary],
        ['代码摘要', snapshot.code_summary],
        ['用例摘要', snapshot.test_case_summary],
        ['运行摘要', snapshot.run_summary],
        ['对话摘要', snapshot.conversation_summary],
    ];
    for (const [label, value] of fields) {
        if (value) parts.push(`### ${label}\n${value}`);
    }
    if (Array.isArray(snapshot.important_facts) && snapshot.important_facts.length) {
        parts.push(`### 关键事实\n${snapshot.important_facts.map(item => `- ${item}`).join('\n')}`);
    }
    const markdown = parts.join('\n\n');
    if (typeof renderMarkdown === 'function') {
        container.innerHTML = renderMarkdown(markdown);
    } else {
        container.textContent = markdown;
    }
}

function _renderReadingLogEvents(events) {
    const container = document.getElementById('readingLogEvents');
    if (!container) return;
    container.replaceChildren();
    if (!events.length) {
        container.textContent = '暂无事件';
        return;
    }

    for (const event of [...events].reverse()) {
        const item = document.createElement('div');
        item.className = 'reading-log-event';
        const head = document.createElement('div');
        head.className = 'reading-log-event-head';
        const title = document.createElement('span');
        const command = event.payload?.command ? ` /${event.payload.command}` : '';
        title.textContent = `${event.type || 'event'}${command}`;
        const time = document.createElement('span');
        time.className = 'reading-log-event-time';
        time.textContent = _formatReadingLogTime(event.created_at);
        head.append(title, time);

        const detail = document.createElement('div');
        detail.className = 'reading-log-event-detail';
        detail.textContent = JSON.stringify(event.payload || {});
        item.append(head, detail);
        container.appendChild(item);
    }
}

function _formatReadingLogTime(value) {
    if (!value) return '';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
}

async function compressReadingLogContext() {
    if (!state.sessionId) return;
    try {
        const res = await fetch(`/api/sessions/${state.sessionId}/context/compress`, { method: 'POST' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        addSystemMsg('上下文压缩完成，阅读日志已刷新。');
        await loadReadingLog();
    } catch (err) {
        addErrorMsg(`上下文压缩失败：${err.message}`);
    }
}
