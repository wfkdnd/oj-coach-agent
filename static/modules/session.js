/* ── OJ Coach - 会话管理模块 ──────────────────────── */
/* 依赖：chat.js (addSystemMsg, addErrorMsg), ui.js (setBadge) */

const state = {
    sessionId: null,
    sessions: [],
    sessionListVersion: 0,
    // 未激活会话的前端视图缓存；后端状态仍由各自的 session 独立保存。
    sessionViews: new Map(),
    workspaceLoaded: false,
    connected: false,
    isStreaming: false,
    cmdHistory: [],
    cmdHistoryIdx: -1,
    llmConfig: {
        baseUrl: '',
        model: '',
        apiKeyConfigured: false,
        reason: '',
    },
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
        const listRes = await fetch('/api/sessions');
        const listData = await listRes.json();
        state.sessions = _sortSessionSummaries(listData.ok ? listData.sessions : []);

        const savedSessionId = localStorage.getItem('ojCoachActiveSession');
        let target = state.sessions.find(item => item.session_id === savedSessionId)
            || state.sessions[state.sessions.length - 1];
        let created = false;

        if (!target) {
            const createRes = await fetch('/api/sessions', { method: 'POST' });
            const createData = await createRes.json();
            if (!createData.ok) throw new Error('后端未能创建会话');
            target = createData.session || _newSessionSummary(createData.session_id);
            state.sessions = _sortSessionSummaries([...state.sessions, target]);
            created = true;
        }

        _renderSessionMenu();
        await switchSession(target.session_id, {
            saveCurrent: false,
            announceCreated: created,
            initializeEmpty: created,
        });
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
        state.llmConfig = {
            baseUrl: String(data.base_url || ''),
            model: String(data.model || ''),
            apiKeyConfigured: Boolean(data.api_key_configured),
            reason: String(data.reason || ''),
        };
        _renderLlmConfigPopover();
        if (data.ok && data.llm_available) {
            setBadge('llmBadge', `LLM: ${data.model}`, 'badge llm-badge-button status-ok');
        } else {
            const reason = data.reason || '未配置';
            setBadge('llmBadge', `LLM: ${reason}`, 'badge llm-badge-button status-err');
        }
    } catch {
        state.llmConfig.reason = '检测失败';
        _renderLlmConfigPopover();
        setBadge('llmBadge', 'LLM: 检测失败', 'badge llm-badge-button status-err');
    }
}

function _renderLlmConfigPopover() {
    const baseUrl = document.getElementById('llmConfigBaseUrl');
    const apiKey = document.getElementById('llmConfigApiKey');
    const model = document.getElementById('llmConfigModel');
    const status = document.getElementById('llmConfigStatus');
    if (!baseUrl || !apiKey || !model || !status) return;

    baseUrl.value = state.llmConfig.baseUrl;
    model.value = state.llmConfig.model;
    // 这里只写入固定占位值，真实 API Key 从未由后端返回。
    apiKey.value = state.llmConfig.apiKeyConfigured ? 'configured' : '';
    apiKey.placeholder = state.llmConfig.apiKeyConfigured ? '' : '未配置';
    status.textContent = state.llmConfig.reason || '配置读取成功';
    status.classList.toggle('status-error', Boolean(state.llmConfig.reason));
}

function toggleLlmConfigPopover(event, forceOpen) {
    if (event) event.stopPropagation();
    const popover = document.getElementById('llmConfigPopover');
    const badge = document.getElementById('llmBadge');
    if (!popover || !badge) return;

    const shouldOpen = typeof forceOpen === 'boolean'
        ? forceOpen
        : !popover.classList.contains('show');
    popover.classList.toggle('show', shouldOpen);
    badge.setAttribute('aria-expanded', String(shouldOpen));
    if (shouldOpen) {
        _renderLlmConfigPopover();
        const rect = badge.getBoundingClientRect();
        const popoverWidth = Math.min(390, window.innerWidth - 20);
        const maxLeft = Math.max(10, window.innerWidth - popoverWidth - 10);
        popover.style.top = `${rect.bottom + 8}px`;
        popover.style.left = `${Math.min(Math.max(10, rect.left), maxLeft)}px`;
        popover.style.right = 'auto';
    }
}

// ── 状态刷新 ────────────────────────────────────────

async function refreshStatus() {
    if (!state.sessionId) return;
    const requestedSessionId = state.sessionId;
    try {
        const res = await fetch(`/api/sessions/${requestedSessionId}/status`);
        const data = await res.json();
        // 切换发生在请求期间时，旧响应不能覆盖新会话的界面。
        if (data.ok && state.sessionId === requestedSessionId) updateUIFromStatus(data.status);
    } catch (err) {
        console.error('状态刷新失败:', err);
    }
}

function updateUIFromStatus(status) {
    if (status.language && status.language !== '未设置') {
        document.getElementById('langSelect').value = status.language;
    }
    const timeoutInput = document.getElementById('timeoutInput');
    const timeoutMs = Number(status.timeout_ms);
    if (timeoutInput && Number.isFinite(timeoutMs) && timeoutMs > 0) {
        // 命令行 /set_timeout 和顶部输入框共享后端状态，刷新后以后端值为准。
        timeoutInput.value = String(timeoutMs);
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

async function switchSession(sessionId, options = {}) {
    const nextSessionId = String(sessionId || '').trim();
    if (!nextSessionId) return false;
    if (state.isStreaming) {
        showToast('当前会话仍在生成回复，请完成后再切换', 'toast-warning');
        toggleSessionMenu(false);
        return false;
    }
    if (nextSessionId === state.sessionId) {
        toggleSessionMenu(false);
        return true;
    }

    if (options.saveCurrent !== false) _saveCurrentSessionView();
    state.sessionId = nextSessionId;
    state.connected = true;
    localStorage.setItem('ojCoachActiveSession', nextSessionId);

    const cachedView = _restoreSessionView(nextSessionId, options.announceCreated);
    state.workspaceLoaded = false;
    _updateCurrentSessionIdentity();
    toggleSessionMenu(false);
    toggleReadingLog(false);
    _closeSessionFloatPanels();

    // 回到已经打开过的会话时直接使用内存视图；新会话也无需再请求一次空状态。
    if (cachedView?.workspaceLoaded) {
        _restoreCachedWorkspace(cachedView.workspace);
    } else if (options.initializeEmpty) {
        _applySessionWorkspace({});
    } else {
        await loadSessionWorkspace(nextSessionId);
    }
    _renderSessionMenu();
    return true;
}

async function createNewSession() {
    if (state.isStreaming) {
        showToast('当前会话仍在生成回复，请完成后再新建会话', 'toast-warning');
        return;
    }
    const button = document.getElementById('newSessionBtn');
    if (button) button.disabled = true;
    try {
        const res = await fetch('/api/sessions', { method: 'POST' });
        const data = await res.json();
        if (!data.ok) throw new Error(data.detail || '后端未能创建会话');

        const summary = data.session || _newSessionSummary(data.session_id);
        state.sessionListVersion += 1;
        state.sessions = _sortSessionSummaries([...state.sessions, summary]);
        _renderSessionMenu();
        // 创建接口已经返回轻量摘要；不再串行刷新列表、状态和 LLM 配置。
        await switchSession(summary.session_id, {
            announceCreated: true,
            initializeEmpty: true,
        });
    } catch (err) {
        addErrorMsg(`创建会话失败: ${err.message}`);
    } finally {
        if (button) button.disabled = false;
    }
}

async function refreshSessionList() {
    const requestVersion = state.sessionListVersion;
    try {
        const res = await fetch('/api/sessions');
        const data = await res.json();
        // 新建请求可能和菜单的后台刷新并发，旧列表不能覆盖刚创建的会话。
        if (data.ok && requestVersion === state.sessionListVersion) {
            state.sessions = _sortSessionSummaries(data.sessions || []);
            _renderSessionMenu();
            _updateCurrentSessionIdentity();
        }
    } catch { /* 列表刷新失败不影响当前会话使用 */ }
}

function toggleSessionMenu(forceOpen) {
    const popover = document.getElementById('sessionMenuPopover');
    const trigger = document.getElementById('sessionMenuTrigger');
    if (!popover || !trigger) return;

    const shouldOpen = typeof forceOpen === 'boolean' ? forceOpen : popover.hidden;
    popover.hidden = !shouldOpen;
    trigger.setAttribute('aria-expanded', String(shouldOpen));
    if (shouldOpen) {
        _renderSessionMenu();
        // 菜单先立即显示缓存，再在后台同步轻量列表。
        void refreshSessionList();
    }
}

function _renderSessionMenu() {
    const list = document.getElementById('sessionMenuList');
    if (!list) return;
    list.replaceChildren();

    if (!state.sessions.length) {
        const empty = document.createElement('div');
        empty.className = 'session-menu-empty';
        empty.textContent = '暂无会话';
        list.appendChild(empty);
        return;
    }

    for (const session of state.sessions) {
        const item = document.createElement('button');
        item.type = 'button';
        item.className = 'session-menu-item';
        item.classList.toggle('active', session.session_id === state.sessionId);
        item.setAttribute('role', 'menuitem');

        const title = document.createElement('span');
        title.className = 'session-menu-item-title';
        title.textContent = session.title || `会话 ${_shortSessionId(session.session_id)}`;

        const meta = document.createElement('span');
        meta.className = 'session-menu-item-meta';
        meta.textContent = `${session.language || '未设置'} · ${_shortSessionId(session.session_id)}`;
        item.append(title, meta);
        item.addEventListener('click', () => void switchSession(session.session_id));
        list.appendChild(item);
    }
}

function _saveCurrentSessionView() {
    if (!state.sessionId) return;
    const chat = document.getElementById('chatMessages');
    const chatFragment = document.createDocumentFragment();
    if (chat) {
        while (chat.firstChild) chatFragment.appendChild(chat.firstChild);
    }

    const problemText = _getSessionEditorValue('problemInput');
    const workspace = {
        problemText,
        codeText: _getSessionEditorValue('codeInput'),
        language: document.getElementById('langSelect')?.value || 'python',
        timeoutMs: document.getElementById('timeoutInput')?.value || '3000',
        testCases: _cloneSessionCases(window.__testCases || []),
        testCasesDirty: Boolean(window.__testCasesDirty),
        problemLocked: Boolean(window.__problemLocked),
        codeLocked: Boolean(window.__codeLocked),
        problemPreviewing: Boolean(window.__problemPreviewing),
        commandDraft: document.getElementById('commandInput')?.value || '',
        runCompleted: document.getElementById('runStatus')?.classList.contains('status-ok') || false,
    };
    state.sessionViews.set(state.sessionId, {
        chat: chatFragment,
        workspace,
        workspaceLoaded: state.workspaceLoaded,
    });

    const title = _titleFromProblem(problemText, state.sessionId);
    state.sessions = state.sessions.map(item => item.session_id === state.sessionId
        ? { ...item, title, language: workspace.language }
        : item);
}

function _restoreSessionView(sessionId, announceCreated = false) {
    const chat = document.getElementById('chatMessages');
    const cached = state.sessionViews.get(sessionId);
    if (chat) chat.replaceChildren();
    if (cached && chat) {
        chat.appendChild(cached.chat);
        state.sessionViews.delete(sessionId);
    } else if (announceCreated) {
        addSystemMsg(`新会话已创建 (${_shortSessionId(sessionId)})`);
    } else {
        addSystemMsg(`已切换到会话 ${_shortSessionId(sessionId)}`);
    }
    return cached || null;
}

function invalidateSessionWorkspace(sessionId) {
    const cached = state.sessionViews.get(sessionId);
    if (cached) cached.workspaceLoaded = false;
}

async function loadSessionWorkspace(sessionId) {
    try {
        const res = await fetch(`/api/sessions/${sessionId}/workspace`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (state.sessionId === sessionId) _applySessionWorkspace(data.workspace || {});
    } catch (err) {
        if (state.sessionId === sessionId) addErrorMsg(`加载会话失败: ${err.message}`);
    }
}

function _applySessionWorkspace(workspace) {
    if (typeof _setProblemPreview === 'function') _setProblemPreview(false);
    _setSessionEditorValue('problemInput', workspace.problem_text || '');
    _setSessionEditorValue('codeInput', workspace.code || '');

    const language = workspace.language && workspace.language !== '未设置'
        ? workspace.language
        : 'python';
    const langSelect = document.getElementById('langSelect');
    if (langSelect) langSelect.value = language;
    if (window.__updateCodeLang) window.__updateCodeLang(language);

    const timeoutInput = document.getElementById('timeoutInput');
    if (timeoutInput) timeoutInput.value = String(workspace.timeout_ms || 3000);
    _setRunStatus(Boolean(String(workspace.last_run_result || '').trim()));

    window.__testCases = _cloneSessionCases(workspace.test_cases || []);
    window.__testCasesDirty = false;
    window.__testCasesSyncing = false;
    if (typeof _renderTestCaseList === 'function') _renderTestCaseList();
    const commandInput = document.getElementById('commandInput');
    if (commandInput) commandInput.value = '';
    _setSessionLocks(false, false);
    state.workspaceLoaded = true;
}

function _restoreCachedWorkspace(workspace) {
    if (typeof _setProblemPreview === 'function') _setProblemPreview(false);
    _setSessionEditorValue('problemInput', workspace.problemText || '');
    _setSessionEditorValue('codeInput', workspace.codeText || '');

    const langSelect = document.getElementById('langSelect');
    if (langSelect) langSelect.value = workspace.language || 'python';
    if (window.__updateCodeLang) window.__updateCodeLang(workspace.language || 'python');

    const timeoutInput = document.getElementById('timeoutInput');
    if (timeoutInput) timeoutInput.value = String(workspace.timeoutMs || 3000);
    _setRunStatus(Boolean(workspace.runCompleted));
    window.__testCases = _cloneSessionCases(workspace.testCases || []);
    window.__testCasesDirty = Boolean(workspace.testCasesDirty);
    window.__testCasesSyncing = false;
    if (typeof _renderTestCaseList === 'function') _renderTestCaseList();
    _setSessionLocks(Boolean(workspace.problemLocked), Boolean(workspace.codeLocked));
    if (workspace.problemPreviewing && typeof _setProblemPreview === 'function') {
        _setProblemPreview(true);
    }
    const commandInput = document.getElementById('commandInput');
    if (commandInput) commandInput.value = workspace.commandDraft || '';
    state.workspaceLoaded = true;
}

function _setSessionEditorValue(textareaId, content) {
    if (typeof _setEditorContent === 'function') {
        _setEditorContent(textareaId, String(content || ''));
        return;
    }
    const textarea = document.getElementById(textareaId);
    if (textarea) textarea.value = String(content || '');
}

function _getSessionEditorValue(textareaId) {
    const editor = window.__editorViews?.[textareaId];
    if (editor) return editor.state.doc.toString();
    return document.getElementById(textareaId)?.value || '';
}

function _setSessionLocks(problemLocked, codeLocked) {
    if (Boolean(window.__problemLocked) !== problemLocked && window.toggleProblemLock) {
        window.toggleProblemLock();
    }
    if (Boolean(window.__codeLocked) !== codeLocked && window.toggleCodeLock) {
        window.toggleCodeLock();
    }
}

function _setRunStatus(hasRun) {
    const badge = document.getElementById('runStatus');
    if (!badge) return;
    badge.textContent = hasRun ? '已运行' : '未运行';
    badge.className = hasRun ? 'badge status-ok' : 'badge';
}

function _updateCurrentSessionIdentity() {
    if (!state.sessionId) return;
    const session = state.sessions.find(item => item.session_id === state.sessionId);
    const shortId = _shortSessionId(state.sessionId);
    const label = document.getElementById('sessionCurrentLabel');
    if (label) label.textContent = session?.title || `会话 ${shortId}`;
    setBadge('sessionBadge', `会话 ${shortId}`, 'badge status-ok');
}

function _closeSessionFloatPanels() {
    if (typeof closeFloatTab !== 'function') return;
    for (const name of ['problem', 'cases']) closeFloatTab(name);
}

function _cloneSessionCases(cases) {
    return cases.map((item, index) => ({
        name: String(item.name || item['名称'] || `用例 ${index + 1}`),
        source: String(item.source || item['来源'] || '后端同步'),
        stdin: String(item.stdin || ''),
        expected_output: String(item.expected_output || ''),
    }));
}

function _sortSessionSummaries(sessions) {
    return [...sessions].sort((left, right) =>
        String(left.created_at || '').localeCompare(String(right.created_at || '')));
}

function _newSessionSummary(sessionId) {
    const now = new Date().toISOString();
    return {
        session_id: sessionId,
        title: `会话 ${_shortSessionId(sessionId)}`,
        created_at: now,
        updated_at: now,
        language: '未设置',
    };
}

function _titleFromProblem(problemText, sessionId) {
    const firstLine = String(problemText || '').split(/\r?\n/)
        .map(line => line.trim().replace(/^#+\s*/, ''))
        .find(Boolean);
    return firstLine ? firstLine.slice(0, 36) : `会话 ${_shortSessionId(sessionId)}`;
}

function _shortSessionId(sessionId) {
    return String(sessionId || '').slice(0, 8);
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
