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
    if (typeof _isReadingLogOpen === 'function' && _isReadingLogOpen()) {
        await loadReadingLog();
    }
    return data;
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
    let streamRawText = '';

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
                streamMsgEl.innerHTML = '<div class="msg-header">回答</div><div class="stream-text"></div>';
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
                    let hasData = false;

                    for (const line of lines) {
                        if (line.startsWith('event: ')) {
                            eventType = line.substring(7).trim();
                        } else if (line.startsWith('data:')) {
                            let value = line.substring(5);
                            if (value.startsWith(' ')) value = value.substring(1);
                            data += (hasData ? '\n' : '') + value;
                            hasData = true;
                        }
                    }

                    if (eventType === 'token' && hasData) {
                        streamRawText += data;
                        textSpan.innerHTML = renderMarkdown(streamRawText);
                        applyHighlight(streamMsgEl);
                        scrollChat();
                    } else if (eventType === 'result' && hasData) {
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

    if (streamMsgEl && textSpan && !streamRawText.trim()) {
        streamRawText = '（未收到回答内容，请检查 LLM 配置或网络）';
        textSpan.innerHTML = renderMarkdown(streamRawText);
    }
    if (streamMsgEl) {
        streamMsgEl.className = 'msg msg-assistant';
        if (textSpan && streamRawText.trim()) {
            textSpan.innerHTML = renderMarkdown(streamRawText);
            applyHighlight(streamMsgEl);
        }
    }
    state.isStreaming = false;
    setSendDisabled(false);
    await refreshStatus();
    if (typeof _isReadingLogOpen === 'function' && _isReadingLogOpen()) {
        await loadReadingLog();
    }
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
    const result = await normalCommand({ command: 'paste_problem', args: '', input_text: text });
    if (result && result.ok) {
        window.__testCasesDirty = false;
        await refreshStatus();
    }
}

async function submitCode() {
    _syncEditors();
    const code = document.getElementById('codeInput').value.trim();
    const lang = document.getElementById('langSelect').value;
    if (!code) { addErrorMsg('请先输入代码'); return; }
    await normalCommand({ command: 'paste_code', args: lang, input_text: code });
}

async function submitCases() {
    // 先从当前 DOM 同步，避免用户刚输入就点击提交时数据仍停留在旧值。
    if (typeof _syncTestCaseFields === 'function') _syncTestCaseFields();
    const cases = window.__testCases || [];
    if (cases.length === 0) { addErrorMsg('请先添加测试用例（可从题目中自动检测或手动添加）'); return; }
    if (!cases.some(c => String(c.expected_output || '').trim())) {
        addErrorMsg('没有识别到可运行测试用例，请确认每组用例至少包含期望输出（输入可为空）。');
        return;
    }
    const text = (typeof _serializeTestCases === 'function')
        ? _serializeTestCases()
        : JSON.stringify({
            test_cases: cases.map(c => ({ stdin: c.stdin, expected_output: c.expected_output })),
        });
    const result = await normalCommand({ command: 'set_cases', args: '', input_text: text });
    if (result && result.ok) {
        window.__testCasesDirty = false;
        await refreshStatus();
    }
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
    // 用户输入按纯文本展示；系统、结果、错误和回答均安全渲染 Markdown。
    const rendered = type === 'user'
        ? escapeHtml(text).replace(/\n/g, '<br>')
        : renderMarkdown(text);
    div.innerHTML = `<div class="msg-header">${header}</div>${rendered}`;
    container.appendChild(div);
    applyHighlight(div);
    scrollChat();
}

// ── 安全 Markdown 渲染 ──────────────────────────────

function renderMarkdown(text) {
    const normalized = String(text ?? '').replace(/\r\n?/g, '\n');
    return `<div class="markdown-body">${_renderMarkdownBlocks(normalized)}</div>`;
}

function _renderMarkdownBlocks(text) {
    const lines = text.split('\n');
    const html = [];
    let paragraph = [];
    let index = 0;

    const flushParagraph = () => {
        if (paragraph.length === 0) return;
        html.push(`<p>${paragraph.map(renderMarkdownInline).join('<br>')}</p>`);
        paragraph = [];
    };

    while (index < lines.length) {
        const line = lines[index];
        const trimmed = line.trim();

        const fence = trimmed.match(/^```([\w+-]*)\s*$/);
        if (fence) {
            flushParagraph();
            const codeLines = [];
            index += 1;
            while (index < lines.length && !/^```\s*$/.test(lines[index].trim())) {
                codeLines.push(lines[index]);
                index += 1;
            }
            if (index < lines.length) index += 1;
            html.push(renderCodeBlock(fence[1], codeLines.join('\n')));
            continue;
        }

        if (!trimmed) {
            flushParagraph();
            index += 1;
            continue;
        }

        const heading = trimmed.match(/^(#{1,6})\s+(.+)$/);
        if (heading) {
            flushParagraph();
            const level = heading[1].length;
            html.push(`<h${level}>${renderMarkdownInline(heading[2])}</h${level}>`);
            index += 1;
            continue;
        }

        if (/^(?:-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
            flushParagraph();
            html.push('<hr>');
            index += 1;
            continue;
        }

        if (line.includes('|') && index + 1 < lines.length && _isMarkdownTableSeparator(lines[index + 1])) {
            flushParagraph();
            const headers = _splitMarkdownTableRow(line);
            index += 2;
            const rows = [];
            while (index < lines.length && lines[index].includes('|') && lines[index].trim()) {
                rows.push(_splitMarkdownTableRow(lines[index]));
                index += 1;
            }
            const headHtml = headers.map(cell => `<th>${renderMarkdownInline(cell)}</th>`).join('');
            const bodyHtml = rows.map(row => `<tr>${headers.map((_, cellIndex) =>
                `<td>${renderMarkdownInline(row[cellIndex] || '')}</td>`).join('')}</tr>`).join('');
            html.push(`<div class="markdown-table-wrap"><table><thead><tr>${headHtml}</tr></thead><tbody>${bodyHtml}</tbody></table></div>`);
            continue;
        }

        if (/^\s*>\s?/.test(line)) {
            flushParagraph();
            const quoteLines = [];
            while (index < lines.length && /^\s*>\s?/.test(lines[index])) {
                quoteLines.push(lines[index].replace(/^\s*>\s?/, ''));
                index += 1;
            }
            html.push(`<blockquote>${_renderMarkdownBlocks(quoteLines.join('\n'))}</blockquote>`);
            continue;
        }

        const unordered = line.match(/^\s*[-+*]\s+(.+)$/);
        const ordered = line.match(/^\s*\d+[.)]\s+(.+)$/);
        if (unordered || ordered) {
            flushParagraph();
            const tag = unordered ? 'ul' : 'ol';
            const items = [];
            while (index < lines.length) {
                const itemMatch = tag === 'ul'
                    ? lines[index].match(/^\s*[-+*]\s+(.+)$/)
                    : lines[index].match(/^\s*\d+[.)]\s+(.+)$/);
                if (!itemMatch) break;
                items.push(`<li>${renderMarkdownInline(itemMatch[1])}</li>`);
                index += 1;
            }
            html.push(`<${tag}>${items.join('')}</${tag}>`);
            continue;
        }

        paragraph.push(line);
        index += 1;
    }

    flushParagraph();
    return html.join('');
}

function renderCodeBlock(lang, code) {
    const safeLang = String(lang || '').replace(/[^\w+-]/g, '');
    const langLabel = safeLang ? ` <span class="code-lang">${safeLang}</span>` : '';
    const langClass = safeLang ? `hljs language-${safeLang}` : 'hljs';
    return `<div class="code-block">${langLabel}<pre><code class="${langClass}">${escapeHtml(code).trim()}</code></pre></div>`;
}

function renderMarkdownInline(text) {
    const codeSpans = [];
    let result = escapeHtml(String(text ?? ''));
    result = result.replace(/`([^`]+)`/g, (_, code) => {
        const token = `\u0000CODE${codeSpans.length}\u0000`;
        codeSpans.push(`<code class="inline-code">${code}</code>`);
        return token;
    });
    result = result.replace(/\[([^\]]+)]\(((?:https?:\/\/|mailto:)[^\s)]+)\)/g,
        '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    result = result.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    result = result.replace(/~~(.+?)~~/g, '<del>$1</del>');
    result = result.replace(/(^|[^*])\*([^*]+)\*/g, '$1<em>$2</em>');
    result = result.replace(/\u0000CODE(\d+)\u0000/g, (_, index) => codeSpans[Number(index)]);
    return result;
}

function _isMarkdownTableSeparator(line) {
    return /^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line);
}

function _splitMarkdownTableRow(line) {
    return line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(cell => cell.trim());
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
