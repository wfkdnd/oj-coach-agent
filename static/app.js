/* OJ Coach Agent - WebUI 前端逻辑 */
/* 纯原生 JS，无框架依赖 */

// ── 状态 ────────────────────────────────────────────

const state = {
    sessionId: null,
    connected: false,
    isStreaming: false,
};

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
}

// ── 命令发送 ────────────────────────────────────────

async function sendCommand() {
    if (state.isStreaming) return;

    const input = document.getElementById('commandInput');
    const raw = input.value.trim();
    if (!raw) return;

    input.value = '';
    hideSuggestions();

    // 用户输入以 / 开头 → 命令；否则 → /ask
    const isCommand = raw.startsWith('/');
    addUserMsg(raw);

    const payload = isCommand ? { raw } : { command: 'ask', args: '', input_text: raw };

    try {
        if (isCommand && raw.startsWith('/ask') || !isCommand) {
            // 流式输出
            await streamCommand(payload);
        } else {
            // 非流式
            await normalCommand(payload);
        }
    } catch (err) {
        addErrorMsg(`请求失败：${err.message}`);
    }
}

async function normalCommand(payload) {
    const url = `/api/sessions/${state.sessionId}/command`;
    const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    const data = await res.json();

    // 展示消息
    for (const msg of (data.messages || [])) {
        addSystemMsg(msg);
    }
    if (data.output) {
        addResultMsg(data.output);
    }

    // 同步状态
    await refreshStatus();
}

async function streamCommand(payload) {
    state.isStreaming = true;
    setSendDisabled(true);

    const url = `/api/sessions/${state.sessionId}/command/stream`;
    const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let streamMsg = null;

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop(); // 保留不完整的行

        for (const line of lines) {
            if (!line.trim()) continue;

            if (line.startsWith('event: ')) {
                const eventType = line.slice(7).trim();
                // 下一行是 data
                continue;
            }

            if (line.startsWith('data: ')) {
                const data = line.slice(6);
                // 简单判断事件类型：通过前一批次的 event: 事件
                // SSE 事件会在不同的行中
                if (line.includes('event: token') || buffer.includes('event: token')) {
                    // token 流
                    if (streamMsg) {
                        streamMsg.textContent += data;
                    }
                }
            }
        }
    }

    // 重新解析完整的 SSE 数据
    const fullText = buffer;
    // 用更可靠的方式处理 SSE
    // ...

    state.isStreaming = false;
    setSendDisabled(false);
    await refreshStatus();
}

// SSE 流式处理优化版
async function streamCommandV2(payload) {
    state.isStreaming = true;
    setSendDisabled(true);

    const url = `/api/sessions/${state.sessionId}/command/stream`;
    const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let streamMsgEl = null;

    // 先添加一个占位消息，用于流式填充
    const container = document.getElementById('chatMessages');
    streamMsgEl = document.createElement('div');
    streamMsgEl.className = 'msg msg-streaming';
    streamMsgEl.innerHTML = '<div class="msg-header">回答</div><span class="stream-text"></span>';
    container.appendChild(streamMsgEl);
    scrollChat();
    const textSpan = streamMsgEl.querySelector('.stream-text');

    let currentEvent = '';
    let buffer = '';

    try {
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            while (true) {
                const eventEnd = buffer.indexOf('\n\n');
                if (eventEnd === -1) break;

                const block = buffer.substring(0, eventEnd);
                buffer = buffer.substring(eventEnd + 2);

                const lines = block.split('\n');
                let eventType = '';
                let data = '';

                for (const line of lines) {
                    if (line.startsWith('event: ')) {
                        eventType = line.substring(7).trim();
                    } else if (line.startsWith('data: ')) {
                        data = line.substring(6);
                    }
                }

                if (eventType === 'token' && data) {
                    textSpan.textContent += data;
                    scrollChat();
                } else if (eventType === 'result') {
                    try {
                        const result = JSON.parse(data);
                        for (const msg of (result.messages || [])) {
                            addSystemMsg(msg);
                        }
                    } catch (e) {}
                }
            }
        }
    } finally {
        // 流式完成
        if (streamMsgEl) {
            streamMsgEl.className = 'msg msg-assistant';
        }
        state.isStreaming = false;
        setSendDisabled(false);
        await refreshStatus();
    }
}

// 用 V2 替换原版
streamCommand = streamCommandV2;

// ── 面板提交 ────────────────────────────────────────

async function submitProblem() {
    const text = document.getElementById('problemInput').value.trim();
    if (!text) {
        addErrorMsg('请先输入题目文本');
        return;
    }
    addSystemMsg('正在提交题目...');
    await normalCommand({ command: 'paste_problem', args: '', input_text: text });
}

async function submitCode() {
    const code = document.getElementById('codeInput').value.trim();
    const lang = document.getElementById('langSelect').value;
    if (!code) {
        addErrorMsg('请先输入代码');
        return;
    }
    addSystemMsg(`正在提交 ${lang} 代码...`);
    await normalCommand({ command: 'paste_code', args: lang, input_text: code });
}

async function submitCases() {
    const text = document.getElementById('testCaseInput').value.trim();
    if (!text) {
        addErrorMsg('请先输入测试用例');
        return;
    }
    addSystemMsg('正在添加测试用例...');
    await normalCommand({ command: 'set_cases', args: '', input_text: text });
}

// ── 状态刷新 ────────────────────────────────────────

async function refreshStatus() {
    if (!state.sessionId) return;
    try {
        const res = await fetch(`/api/sessions/${state.sessionId}/status`);
        const data = await res.json();
        if (data.ok) {
            updateUIFromStatus(data.status);
        }
    } catch (err) {
        console.error('状态刷新失败:', err);
    }
}

function updateUIFromStatus(status) {
    // 语言选择
    if (status.language && status.language !== '未设置') {
        document.getElementById('langSelect').value = status.language;
    }

    // 运行状态
    const runBadge = document.getElementById('runStatus');
    if (status.last_run_result_set) {
        runBadge.textContent = '已运行';
        runBadge.className = 'badge status-ok';
    } else {
        runBadge.textContent = '未运行';
        runBadge.className = 'badge';
    }

    // 测试用例数量
    if (status.test_case_sources && Object.keys(status.test_case_sources).length > 0) {
        const srcText = Object.entries(status.test_case_sources)
            .map(([k, v]) => `${k}:${v}`)
            .join(', ');
        document.getElementById('testCasePanel').querySelector('.panel-header span').textContent =
            `测试用例 (${srcText})`;
    }
}

// ── 命令候选提示 ────────────────────────────────────

const commands = [
    { cmd: '/paste_problem', desc: '粘贴题目' },
    { cmd: '/paste_code python', desc: '粘贴 Python 代码' },
    { cmd: '/paste_code cpp', desc: '粘贴 C++ 代码' },
    { cmd: '/paste_code java', desc: '粘贴 Java 代码' },
    { cmd: '/set_cases', desc: '添加测试用例' },
    { cmd: '/run', desc: '运行代码' },
    { cmd: '/ask', desc: '提问' },
    { cmd: '/summary', desc: '复盘总结' },
    { cmd: '/status', desc: '查看状态' },
    { cmd: '/set_timeout', desc: '设置超时' },
    { cmd: '/help', desc: '帮助' },
];

function filterCommands(query) {
    if (!query.startsWith('/')) return [];
    const q = query.slice(1).toLowerCase();
    return commands.filter(c => c.cmd.toLowerCase().includes(q));
}

function showSuggestions() {
    const input = document.getElementById('commandInput');
    const suggestions = document.getElementById('suggestions');
    const value = input.value.trim().toLowerCase();

    if (!value) {
        hideSuggestions();
        return;
    }

    const matches = filterCommands(value);
    if (matches.length === 0) {
        // 非 / 开头 → 提示会转为 /ask
        if (!value.startsWith('/')) {
            suggestions.innerHTML = `<div class="suggestion-item"><span class="desc">按 Enter 发送 (自动转为 /ask)</span></div>`;
            suggestions.classList.add('show');
        } else {
            hideSuggestions();
        }
        return;
    }

    suggestions.innerHTML = matches
        .map(m => `<div class="suggestion-item" data-cmd="${m.cmd}"><span class="cmd">${m.cmd}</span><span class="desc">${m.desc}</span></div>`)
        .join('');

    suggestions.querySelectorAll('.suggestion-item').forEach(el => {
        el.addEventListener('click', () => {
            document.getElementById('commandInput').value = el.dataset.cmd + ' ';
            hideSuggestions();
            document.getElementById('commandInput').focus();
        });
    });

    suggestions.classList.add('show');
}

function hideSuggestions() {
    document.getElementById('suggestions').classList.remove('show');
}

// ── 对话消息 ────────────────────────────────────────

function addSystemMsg(text) {
    addMsg('system', '系统', text);
}

function addUserMsg(text) {
    addMsg('user', '你', text);
}

function addResultMsg(text) {
    addMsg('result', '结果', text);
}

function addErrorMsg(text) {
    addMsg('error', '错误', text);
}

function addMsg(type, header, text) {
    const container = document.getElementById('chatMessages');
    const div = document.createElement('div');
    div.className = `msg msg-${type}`;
    div.innerHTML = `<div class="msg-header">${header}</div>${escapeHtml(text)}`;
    container.appendChild(div);
    scrollChat();
}

function scrollChat() {
    const container = document.getElementById('chatMessages');
    container.scrollTop = container.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML.replace(/\n/g, '<br>');
}

// ── UI 辅助 ─────────────────────────────────────────

function setBadge(id, text, className) {
    const el = document.getElementById(id);
    el.textContent = text;
    el.className = className || 'badge';
}

function setSendDisabled(disabled) {
    document.getElementById('sendBtn').disabled = disabled;
    document.getElementById('commandInput').disabled = disabled;
}

// ── 面板拖动调整大小 ────────────────────────────────

function initResizers() {
    // 水平分隔条（左右分栏）
    const hResizer = document.getElementById('hResizer');
    const workspace = document.getElementById('workspace');
    const chatArea = document.getElementById('chatArea');

    let isResizingH = false;
    hResizer.addEventListener('mousedown', (e) => {
        isResizingH = true;
        hResizer.classList.add('active');
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
    });

    document.addEventListener('mousemove', (e) => {
        if (!isResizingH) return;
        const mainArea = document.getElementById('mainArea');
        const rect = mainArea.getBoundingClientRect();
        const ratio = (e.clientX - rect.left) / rect.width;
        const clampedRatio = Math.max(0.2, Math.min(0.75, ratio));
        workspace.style.flex = `0 0 ${clampedRatio * 100}%`;
    });

    document.addEventListener('mouseup', () => {
        if (isResizingH) {
            isResizingH = false;
            hResizer.classList.remove('active');
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
        }
    });

    // 垂直分隔条（左侧面板上下调整）
    document.querySelectorAll('.resizer-v').forEach(resizer => {
        const targetId = resizer.dataset.target;
        const siblingId = resizer.dataset.sibling;
        let isResizingV = false;

        resizer.addEventListener('mousedown', (e) => {
            isResizingV = true;
            resizer.classList.add('active');
            document.body.style.cursor = 'row-resize';
            document.body.style.userSelect = 'none';
        });

        document.addEventListener('mousemove', (e) => {
            if (!isResizingV) return;
            const target = document.getElementById(targetId);
            const sibling = document.getElementById(siblingId);
            const workspaceEl = document.getElementById('workspace');
            const wsRect = workspaceEl.getBoundingClientRect();
            const mouseY = e.clientY;

            // 简单实现：按鼠标位置分配百分比
            if (target && sibling) {
                const tRect = target.getBoundingClientRect();
                const sRect = sibling.getBoundingClientRect();
                const offset = mouseY - tRect.top;
                const totalH = tRect.offsetHeight + sRect.offsetHeight + 4; // 4px for resizer
                const ratio = offset / totalH;
                const clampedRatio = Math.max(0.15, Math.min(0.85, ratio));
                target.style.flex = `${clampedRatio}`;
                sibling.style.flex = `${1 - clampedRatio}`;
            }
        });

        document.addEventListener('mouseup', () => {
            if (isResizingV) {
                isResizingV = false;
                resizer.classList.remove('active');
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
            }
        });
    });
}

// ── 事件绑定 ────────────────────────────────────────

function initEvents() {
    const cmdInput = document.getElementById('commandInput');

    // Enter 发送, Shift+Enter 换行
    cmdInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendCommand();
        }
    });

    // 命令候选
    cmdInput.addEventListener('input', showSuggestions);
    cmdInput.addEventListener('blur', () => {
        setTimeout(hideSuggestions, 150); // 延迟以允许点击候选项
    });

    // 面板快捷键
    document.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === 'Enter') {
            e.preventDefault();
            sendCommand();
        }
        // Ctrl+B → 提交代码
        if (e.ctrlKey && e.key === 'b' && !e.target.closest('#commandInput')) {
            e.preventDefault();
            submitCode();
        }
    });

    // 超时输入变更自动同步
    document.getElementById('timeoutInput').addEventListener('change', async () => {
        const timeout = document.getElementById('timeoutInput').value;
        addSystemMsg(`设置超时: ${timeout}ms`);
        await normalCommand({ command: 'set_timeout', args: timeout });
    });
}

// ── 启动 ────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    initSession();
    initResizers();
    initEvents();

    // 自动调整 textarea 高度
    const cmdInput = document.getElementById('commandInput');
    cmdInput.addEventListener('input', () => {
        cmdInput.style.height = 'auto';
        cmdInput.style.height = Math.min(cmdInput.scrollHeight, 120) + 'px';
    });

    // 定时刷新状态
    setInterval(refreshStatus, 5000);

    console.log('OJ Coach Agent WebUI 已就绪');
});
