/* ── OJ Coach - 对话 & 命令模块 ────────────────────── */
/* 依赖：session.js (state, saveToHistory, refreshStatus), ui.js (setSendDisabled, showToast, hideSuggestions) */

const RUN_OUTPUT_COLLAPSE_LINE_LIMIT = 20;

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
        const commandName = isCommand
            ? raw.slice(1).trim().split(/\s+/, 1)[0].toLowerCase()
            : 'ask';
        if (commandName === 'ask' || commandName === 'summary') {
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
        addResultMsg(_formatFrontendCommandOutput(payload, data.output));
    }
    await refreshStatus();
    if (typeof _isReadingLogOpen === 'function' && _isReadingLogOpen()) {
        await loadReadingLog();
    }
    return data;
}

/**
 * 在线复盘和运行分析仍完整展示，只去掉面向实现的 LLM 分段标题。
 * 离线时的“规则版复盘”没有这些标题，因此保持原样。
 */
function _formatFrontendCommandOutput(payload, output) {
    const raw = String(payload && payload.raw || '').trim();
    const command = String(
        payload && payload.command || (raw.startsWith('/') ? raw.slice(1).split(/\s+/, 1)[0] : '')
    ).toLowerCase();
    let text = String(output ?? '');

    if (command === 'run') {
        text = text.replace(/^---\s*LLM\s*分析\s*---\s*\n?/m, '');
    } else if (command === 'summary') {
        text = text.replace(/^LLM\s*讲解版复盘[：:]\s*\n?/m, '');
    }
    return text;
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

    const ensureStreamMessage = (title = '') => {
        const created = !streamMsgEl;
        if (!streamMsgEl) {
            streamMsgEl = document.createElement('div');
            streamMsgEl.className = 'msg msg-streaming';
            streamMsgEl.innerHTML = '<div class="msg-header"></div><div class="stream-text"></div>';
            container.appendChild(streamMsgEl);
            textSpan = streamMsgEl.querySelector('.stream-text');
        }
        const header = streamMsgEl.querySelector('.msg-header');
        if (header && (created || title)) {
            header.textContent = String(title || '回答').replace(/[：:]$/, '');
        }
        scrollChat();
    };

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

            if (streamMsgEl) {
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
                        ensureStreamMessage();
                        streamRawText += data;
                        textSpan.innerHTML = renderMarkdown(streamRawText);
                        applyHighlight(streamMsgEl);
                        scrollChat();
                    } else if (eventType === 'result' && hasData) {
                        try {
                            const result = JSON.parse(data);
                            if (result.has_stream) {
                                ensureStreamMessage(result.stream_title || '回答');
                            }
                            for (const msg of (result.messages || [])) {
                                addSystemMsg(msg);
                            }
                            if (result.output) {
                                addResultMsg(_formatFrontendCommandOutput(payload, result.output));
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
            applyLongOutputCollapse(streamMsgEl);
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
    // 题目样例已由 paste_problem 写入后端，不能再次作为用户用例提交。
    const userCases = cases.filter(c => typeof _isUserTestCase === 'function' && _isUserTestCase(c));
    if (userCases.length === 0) {
        addErrorMsg('当前没有需要提交的用户测试用例，请先点击“添加用例”。');
        return;
    }
    if (!userCases.some(c => String(c.expected_output || '').trim())) {
        addErrorMsg('没有识别到可运行测试用例，请确认每组用例至少包含期望输出（输入可为空）。');
        return;
    }
    const text = (typeof _serializeTestCases === 'function')
        ? _serializeTestCases(userCases)
        : JSON.stringify({
            test_cases: userCases.map(c => ({ stdin: c.stdin, expected_output: c.expected_output })),
        });
    // 用例编辑器提交的是当前用户用例全集，因此必须使用替换语义，才能同步删除和覆盖。
    const result = await normalCommand({ command: 'replace_cases', args: '', input_text: text });
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
    applyLongOutputCollapse(div);
    scrollChat();
}

/** 所有展示态代码块超过 20 行时默认折叠，短内容保持完整展示。 */
function applyLongOutputCollapse(container) {
    if (!container) return;
    container.querySelectorAll('.code-block').forEach(block => {
        if (block.classList.contains('long-output-collapsible')) return;
        const code = block.querySelector('pre code');
        if (!code) return;
        const lineCount = _renderedOutputLineCount(code.parentElement, code.textContent);
        if (lineCount <= RUN_OUTPUT_COLLAPSE_LINE_LIMIT) return;

        block.classList.add('long-output-collapsible');
        const toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'long-output-toggle';
        toggle.textContent = '展开';
        toggle.setAttribute('aria-expanded', 'false');
        toggle.addEventListener('click', () => {
            const expanded = block.classList.toggle('expanded');
            toggle.textContent = expanded ? '收起' : '展开';
            toggle.setAttribute('aria-expanded', String(expanded));
        });
        block.insertBefore(toggle, block.querySelector('pre'));
    });
}

/**
 * 同时统计逻辑换行和浏览器自动换行后的可见行数。
 * 压力用例经常是一整行几十万字符，只数换行符会误判为短输出。
 */
function _renderedOutputLineCount(element, text) {
    const normalized = String(text ?? '').replace(/\r\n?/g, '\n');
    const logicalLines = normalized ? normalized.split('\n').length : 0;
    if (!element || !element.scrollHeight) return logicalLines;

    const style = window.getComputedStyle(element);
    const fontSize = parseFloat(style.fontSize) || 12;
    const lineHeight = parseFloat(style.lineHeight) || fontSize * 1.6;
    const verticalPadding = (parseFloat(style.paddingTop) || 0) + (parseFloat(style.paddingBottom) || 0);
    const renderedLines = Math.ceil(Math.max(0, element.scrollHeight - verticalPadding) / lineHeight);
    return Math.max(logicalLines, renderedLines);
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
