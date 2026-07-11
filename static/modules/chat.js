/* ── OJ Coach - 对话 & 命令模块 ────────────────────── */
/* 依赖：session.js (state, saveToHistory, refreshStatus), ui.js (setSendDisabled, showToast, hideSuggestions) */

// ── 命令发送 ────────────────────────────────────────

async function sendCommand() {
    if (state.isStreaming) {
        showToast('正在等待回答，请稍候...', 'toast-warning');
        return;
    }

    const input = document.getElementById('commandInput');
    const raw = input.value.trim();
    if (!raw) return;

    input.value = '';
    hideSuggestions();
    saveToHistory(raw);
    state.cmdHistoryIdx = -1;

    const isCommand = raw.startsWith('/');
    addUserMsg(raw);

    const payload = isCommand ? { raw } : { command: 'ask', args: '', input_text: raw };

    try {
        if ((isCommand && raw.startsWith('/ask')) || !isCommand) {
            await streamCommand(payload);
        } else {
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

    for (const msg of (data.messages || [])) {
        addSystemMsg(msg);
    }
    if (data.output) {
        addResultMsg(data.output);
    }
    await refreshStatus();
}

// SSE 流式处理（含断线重连）
async function streamCommand(payload) {
    state.isStreaming = true;
    setSendDisabled(true);

    const url = `/api/sessions/${state.sessionId}/command/stream`;
    const container = document.getElementById('chatMessages');
    const maxRetries = 2;
    let streamMsgEl = null;
    let textSpan = null;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
        try {
            const retryPayload = (attempt > 0) ? { resume: true } : payload;
            const res = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(retryPayload),
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);

            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            if (!streamMsgEl) {
                streamMsgEl = document.createElement('div');
                streamMsgEl.className = 'msg msg-streaming';
                streamMsgEl.innerHTML = '<div class="msg-header">回答</div><span class="stream-text"></span>';
                container.appendChild(streamMsgEl);
                scrollChat();
                textSpan = streamMsgEl.querySelector('.stream-text');
            } else {
                const notice = streamMsgEl.querySelector('.reconnect-notice');
                if (notice) notice.remove();
            }

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                let text = decoder.decode(value, { stream: true });
                buffer += text.replace(/\r\n/g, '\n');

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
                            data += (data ? '\n' : '') + line.substring(6);
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
                            if (result.output) {
                                addResultMsg(result.output);
                            }
                        } catch (e) { /* JSON 解析失败忽略 */ }
                    }
                }
            }
            break; // 成功，退出重试循环

        } catch (err) {
            console.error(`SSE 连接失败 (第${attempt + 1}次):`, err);

            if (streamMsgEl && attempt < maxRetries) {
                const existingNotice = streamMsgEl.querySelector('.reconnect-notice');
                if (!existingNotice) {
                    const notice = document.createElement('div');
                    notice.className = 'reconnect-notice';
                    notice.textContent = `连接中断，正在重连 (${attempt + 1}/${maxRetries})...`;
                    streamMsgEl.appendChild(notice);
                    scrollChat();
                }
                await sleep(1000 * (attempt + 1));
            } else {
                if (streamMsgEl) {
                    const notice = streamMsgEl.querySelector('.reconnect-notice');
                    if (notice) notice.textContent = '连接失败，请重试';
                }
                if (!streamMsgEl) {
                    addErrorMsg(`SSE 连接失败: ${err.message}`);
                }
            }
        }
    }

    if (streamMsgEl && textSpan && !textSpan.textContent.trim()) {
        textSpan.textContent = '（未收到回答内容，请检查 LLM 配置或网络）';
    }
    if (streamMsgEl) {
        streamMsgEl.className = 'msg msg-assistant';
        if (textSpan && textSpan.textContent.trim()) {
            textSpan.innerHTML = renderMarkdown(textSpan.textContent);
            applyHighlight(streamMsgEl);
        }
    }
    state.isStreaming = false;
    setSendDisabled(false);
    await refreshStatus();
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// ── 编辑器同步 ──────────────────────────────────────

function _syncEditors() {
    if (window.__syncEditors) window.__syncEditors();
}

// ── 获取题目文本（兼容 CodeMirror）─────────────────

function _getProblemText() {
    const editors = window.__editorViews;
    if (editors && editors['problemInput']) {
        return editors['problemInput'].state.doc.toString();
    }
    const ta = document.getElementById('problemInput');
    return ta ? ta.value : '';
}

// ── 面板提交 ────────────────────────────────────────

async function submitProblem() {
    _syncEditors();
    const text = _getProblemText().trim();
    if (!text) { addErrorMsg('请先输入题目文本'); return; }
    // 提交前自动从题目中提取测试用例
    if (typeof _extractAndPopulateTestCases === 'function') {
        _extractAndPopulateTestCases(text);
    }
    await normalCommand({ command: 'paste_problem', args: '', input_text: text });
}

async function submitCode() {
    _syncEditors();
    const code = document.getElementById('codeInput').value.trim();
    const lang = document.getElementById('langSelect').value;
    if (!code) { addErrorMsg('请先输入代码'); return; }
    await normalCommand({ command: 'paste_code', args: lang, input_text: code });
}

async function submitCases() {
    // 从卡片数据序列化用例
    const cases = window.__testCases || [];
    if (cases.length === 0) { addErrorMsg('请先添加测试用例（可从题目中自动检测或手动添加）'); return; }
    const text = (typeof _serializeTestCases === 'function')
        ? _serializeTestCases()
        : JSON.stringify(cases.map(c => ({ stdin: c.stdin, expected_output: c.expected_output })));
    await normalCommand({ command: 'set_cases', args: '', input_text: text });
}

// ── 对话消息 ────────────────────────────────────────

function addSystemMsg(text) { addMsg('system', '系统', text); }
function addUserMsg(text)   { addMsg('user', '你', text); }
function addResultMsg(text) { addMsg('result', '结果', text); }
function addErrorMsg(text)  { addMsg('error', '错误', text); }

function addMsg(type, header, text) {
    const container = document.getElementById('chatMessages');
    const div = document.createElement('div');
    div.className = `msg msg-${type}`;
    const rendered = (type === 'assistant' || type === 'streaming')
        ? renderMarkdown(text)
        : escapeHtml(text).replace(/\n/g, '<br>');
    div.innerHTML = `<div class="msg-header">${header}</div>${rendered}`;
    container.appendChild(div);
    applyHighlight(div);
    scrollChat();
}

// ── 简易 Markdown 渲染 ──────────────────────────────

function renderMarkdown(text) {
    const escaped = escapeHtml(text);
    const parts = [];
    let lastIndex = 0;
    const codeRegex = /```(\w*)\n?([\s\S]*?)```/g;
    let match;
    while ((match = codeRegex.exec(escaped)) !== null) {
        const [full, lang, code] = match;
        parts.push(renderMarkdownInline(escaped.slice(lastIndex, match.index)));
        parts.push(renderCodeBlock(lang, code));
        lastIndex = match.index + full.length;
    }
    parts.push(renderMarkdownInline(escaped.slice(lastIndex)));
    return parts.join('');
}

function renderCodeBlock(lang, code) {
    const langLabel = lang ? ` <span class="code-lang">${lang}</span>` : '';
    const langClass = lang ? `hljs language-${lang}` : 'hljs';
    return `<div class="code-block">${langLabel}<pre><code class="${langClass}">${code.trim()}</code></pre></div>`;
}

function renderMarkdownInline(text) {
    let result = text;
    result = result.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');
    result = result.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    result = result.replace(/\*(.+?)\*/g, '<em>$1</em>');
    result = result.replace(/\n/g, '<br>');
    return result;
}

function applyHighlight(container) {
    if (!container || !window.hljs) return;
    try {
        if (window.hljs.highlightAllUnder) {
            window.hljs.highlightAllUnder(container);
        } else {
            container.querySelectorAll('pre code').forEach(el => {
                if (window.hljs.highlightElement) window.hljs.highlightElement(el);
            });
        }
    } catch (e) {
        console.warn('Code highlight failed:', e);
    }
}

function scrollChat() {
    const container = document.getElementById('chatMessages');
    container.scrollTop = container.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
