/* ── OJ Coach - UI 工具 & 事件模块 ─────────────────── */
/* 依赖：session.js (state, initSession, createNewSession, switchSession), chat.js (sendCommand, submitCode, normalCommand, addSystemMsg) */

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

    if (!value) { hideSuggestions(); return; }

    const matches = filterCommands(value);
    if (matches.length === 0) {
        if (!value.startsWith('/')) {
            suggestions.innerHTML = '<div class="suggestion-item"><span class="desc">按 Enter 发送 (自动转为 /ask)</span></div>';
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

// ── UI 辅助 ─────────────────────────────────────────

function setBadge(id, text, className) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = text;
    el.className = className || 'badge';
}

function setSendDisabled(disabled) {
    document.getElementById('sendBtn').disabled = disabled;
    document.getElementById('commandInput').disabled = disabled;
}

function showToast(text, className) {
    const toast = document.createElement('div');
    toast.className = `toast ${className || ''}`;
    toast.textContent = text;
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 1500);
}

// ── 标签页切换 ─────────────────────────────────────

function switchTab(tabName) {
    // 更新标签按钮
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    const btn = document.getElementById('tab' + tabName.charAt(0).toUpperCase() + tabName.slice(1));
    if (btn) btn.classList.add('active');

    // 更新内容区
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    const content = document.getElementById('tabContent-' + tabName);
    if (content) {
        content.classList.add('active');
        // 刷新 CodeMirror 编辑器尺寸（从 hidden 到 visible 需要重新测量）
        setTimeout(() => _refreshEditor(tabName), 50);
    }
    // 切换到用例标签时刷新卡片渲染
    if (tabName === 'cases') _renderTestCaseList();
}

function _refreshEditor(tabName) {
    const editors = window.__editorViews;
    if (!editors) return;
    const idMap = { problem: 'problemInput', code: 'codeInput' };
    const editor = editors[idMap[tabName]];
    if (editor && editor.requestMeasure) editor.requestMeasure();
}

// ── 浮动面板（浏览器标签拖出 / 放回）───────────────

let _floatDrag = null;    // { panel, startX, startY, startLeft, startTop }
let _floatResize = null;  // { panel, startX, startY, startW, startH }
let _tabDrag = null;      // { tabName, startX, startY, ghost }
let _skipTabClick = false;
const TAB_DRAG_THRESHOLD = 10;

const _floatDefaults = {
    problem: { left: 280, top: 90, width: 400, height: 340 },
    cases:   { left: 310, top: 120, width: 400, height: 280 },
};

function _getEditorContent(textareaId) {
    const editors = window.__editorViews;
    if (editors && editors[textareaId]) {
        return editors[textareaId].state.doc.toString();
    }
    const ta = document.getElementById(textareaId);
    return ta ? ta.value : '';
}

/** 从标签栏"拖出"为浮动面板 */
function detachTab(tabName) {
    const panel = document.getElementById('floatPanel-' + tabName);
    if (!panel) return;
    let content = '';

    if (tabName === 'problem') {
        content = _getEditorContent('problemInput');
    } else if (tabName === 'cases') {
        const cases = window.__testCases || [];
        content = cases.map((tc, i) => {
            let s = `用例 ${i + 1}：\n输入：\n${tc.stdin}\n输出：\n${tc.expected_output}`;
            if (i < cases.length - 1) s += '\n---\n';
            return s;
        }).join('\n');
    }

    if (!content.trim()) {
        showToast(tabName === 'problem' ? '请先在题目标签页中粘贴题目内容' : '请先在用例标签页中添加用例', 'toast-warning');
        return;
    }
    const body = document.getElementById('floatBody-' + tabName);
    if (body) body.textContent = content;
    const def = _floatDefaults[tabName];
    panel.style.left = def.left + 'px';
    panel.style.top = def.top + 'px';
    panel.style.width = def.width + 'px';
    panel.style.height = def.height + 'px';
    panel.style.display = 'flex';
    // 标签栏标记为"已拖出"
    const btn = document.getElementById('tab' + tabName.charAt(0).toUpperCase() + tabName.slice(1));
    if (btn) btn.classList.add('detached');
}

/** 将浮动面板"放回"标签栏 */
function dockTab(tabName) {
    const panel = document.getElementById('floatPanel-' + tabName);
    if (panel) panel.style.display = 'none';
    const btn = document.getElementById('tab' + tabName.charAt(0).toUpperCase() + tabName.slice(1));
    if (btn) btn.classList.remove('detached');
    switchTab(tabName);
    _floatDrag = null;
    _floatResize = null;
}

/** 关闭浮动面板（不放回标签栏） */
function closeFloatTab(tabName) {
    const panel = document.getElementById('floatPanel-' + tabName);
    if (panel) panel.style.display = 'none';
    const btn = document.getElementById('tab' + tabName.charAt(0).toUpperCase() + tabName.slice(1));
    if (btn) btn.classList.remove('detached');
    _floatDrag = null;
    _floatResize = null;
}

// ── 标签按钮拖出为浮动面板 ──

function _initTabDrag() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('mousedown', (e) => {
            if (e.button !== 0) return;
            const tabName = btn.dataset.tab;
            if (!tabName || tabName === 'code') return;
            _tabDrag = { tabName, startX: e.clientX, startY: e.clientY, ghost: null };
            _skipTabClick = false;
        });
    });

    document.addEventListener('mousemove', (e) => {
        if (!_tabDrag) return;
        const dx = e.clientX - _tabDrag.startX;
        const dy = e.clientY - _tabDrag.startY;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < TAB_DRAG_THRESHOLD && !_tabDrag.ghost) return;

        if (!_tabDrag.ghost) {
            _skipTabClick = true;
            const ghost = document.createElement('div');
            ghost.className = 'float-ghost';
            ghost.textContent = '拖出「' + _tabDrag.tabName + '」';
            document.body.appendChild(ghost);
            _tabDrag.ghost = ghost;
        }
        _tabDrag.ghost.style.left = (e.clientX + 14) + 'px';
        _tabDrag.ghost.style.top = (e.clientY + 14) + 'px';
    });

    document.addEventListener('mouseup', (e) => {
        if (!_tabDrag) return;
        const tabName = _tabDrag.tabName;
        if (_tabDrag.ghost) {
            _tabDrag.ghost.remove();
            const tabsBar = document.getElementById('workspaceTabs');
            if (tabsBar) {
                const r = tabsBar.getBoundingClientRect();
                if (e.clientY > r.bottom + 8) {
                    detachTab(tabName);
                }
            }
        }
        _tabDrag = null;
    });
}

// ── 浮动面板拖拽 / 缩放 / 放回 ──

function _initFloatPanels() {
    document.querySelectorAll('.float-panel').forEach(panel => {
        const header = panel.querySelector('.float-panel-header');
        const resizeHandle = panel.querySelector('.float-panel-resize');

        if (header) {
            header.addEventListener('mousedown', (e) => {
                if (e.target.closest('.float-btn')) return;
                if (e.button !== 0) return;
                e.preventDefault();
                const rect = panel.getBoundingClientRect();
                _floatDrag = {
                    panel,
                    startX: e.clientX,
                    startY: e.clientY,
                    startLeft: rect.left,
                    startTop: rect.top,
                };
                document.body.style.userSelect = 'none';
            });
        }

        if (resizeHandle) {
            resizeHandle.addEventListener('mousedown', (e) => {
                if (e.button !== 0) return;
                e.preventDefault();
                e.stopPropagation();
                const rect = panel.getBoundingClientRect();
                _floatResize = {
                    panel,
                    startX: e.clientX,
                    startY: e.clientY,
                    startW: rect.width,
                    startH: rect.height,
                };
                document.body.style.userSelect = 'none';
            });
        }
    });

    document.addEventListener('mousemove', (e) => {
        if (_floatDrag) {
            const dx = e.clientX - _floatDrag.startX;
            const dy = e.clientY - _floatDrag.startY;
            _floatDrag.panel.style.left = (_floatDrag.startLeft + dx) + 'px';
            _floatDrag.panel.style.top = (_floatDrag.startTop + dy) + 'px';

            // dock 区域高亮检测
            const tabsBar = document.getElementById('workspaceTabs');
            if (tabsBar) {
                const r = tabsBar.getBoundingClientRect();
                if (e.clientX >= r.left && e.clientX <= r.right &&
                    e.clientY >= r.top - 15 && e.clientY <= r.bottom + 10) {
                    tabsBar.classList.add('dock-zone');
                } else {
                    tabsBar.classList.remove('dock-zone');
                }
            }
            return;
        }
        if (_floatResize) {
            const dx = e.clientX - _floatResize.startX;
            const dy = e.clientY - _floatResize.startY;
            _floatResize.panel.style.width = Math.max(260, _floatResize.startW + dx) + 'px';
            _floatResize.panel.style.height = Math.max(120, _floatResize.startH + dy) + 'px';
            return;
        }
    });

    document.addEventListener('mouseup', (e) => {
        if (_floatDrag) {
            const tabsBar = document.getElementById('workspaceTabs');
            if (tabsBar) {
                const r = tabsBar.getBoundingClientRect();
                if (e.clientX >= r.left && e.clientX <= r.right &&
                    e.clientY >= r.top - 15 && e.clientY <= r.bottom + 10) {
                    const panelId = _floatDrag.panel.id;
                    const tabName = panelId.replace('floatPanel-', '');
                    dockTab(tabName);
                }
                tabsBar.classList.remove('dock-zone');
            }
            _floatDrag = null;
            document.body.style.userSelect = '';
        }
        if (_floatResize) {
            _floatResize = null;
            document.body.style.userSelect = '';
        }
    });
}

// ── 面板拖动调整大小 ────────────────────────────────

function initResizers() {
    const hResizer = document.getElementById('hResizer');
    const workspace = document.getElementById('workspace');

    let isResizingH = false;

    hResizer.addEventListener('mousedown', () => {
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
        const clampedRatio = Math.max(0.18, Math.min(0.75, ratio));
        workspace.style.flex = `0 0 ${clampedRatio * 100}%`;
    });

    document.addEventListener('mouseup', () => {
        if (isResizingH) {
            isResizingH = false;
            hResizer.classList.remove('active');
        }
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
    });
}

// ── 文件上传（题目面板：点击 + 拖拽）───────────────

function _initFileUpload() {
    const fileInput = document.getElementById('problemFileInput');
    const workspace = document.getElementById('workspace');
    const dropZone = document.getElementById('problemDropZone');

    if (!fileInput || !workspace || !dropZone) return;

    // ── 点击浏览 ──

    fileInput.addEventListener('change', () => {
        const file = fileInput.files[0];
        if (file) _loadFile(file);
        fileInput.value = '';
    });

    // ── 拖拽 ──

    workspace.addEventListener('dragenter', (e) => {
        e.preventDefault();
        dropZone.classList.add('show');
    });

    workspace.addEventListener('dragover', (e) => {
        e.preventDefault();
    });

    workspace.addEventListener('dragleave', (e) => {
        if (e.relatedTarget === null || !workspace.contains(e.relatedTarget)) {
            dropZone.classList.remove('show');
        }
    });

    workspace.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('show');
        const file = e.dataTransfer.files[0];
        if (file) _loadFile(file);
    });
}

/** 将内容写入编辑器（兼容 CodeMirror 和原生 textarea） */
function _setEditorContent(textareaId, content) {
    const editors = window.__editorViews;
    if (editors && editors[textareaId]) {
        const view = editors[textareaId];
        view.dispatch({
            changes: { from: 0, to: view.state.doc.length, insert: content }
        });
        if (view._textarea) view._textarea.value = content;
    } else {
        const ta = document.getElementById(textareaId);
        if (ta) ta.value = content;
    }
    // 刷新编辑器尺寸（内容变长后需要重新测量）
    const tabMap = { problemInput: 'problem', codeInput: 'code', testCaseInput: 'cases' };
    if (tabMap[textareaId]) _refreshEditor(tabMap[textareaId]);
}

/** 读取文件内容并填入题目编辑器 */
async function _loadFile(file) {
    try {
        const text = await file.text();
        if (!text.trim()) {
            showToast('文件内容为空', 'toast-warning');
            return;
        }
        _setEditorContent('problemInput', text);
        // 自动从题目中提取测试用例
        _extractAndPopulateTestCases(text);
        showToast('已加载: ' + file.name);
        switchTab('problem');
    } catch (err) {
        showToast('读取文件失败: ' + err.message, 'toast-error');
    }
}

// ── 测试用例卡片管理 ────────────────────────────────

/** 全局用例数据：{ name, source, stdin, expected_output }[] */
window.__testCases = [];

/** 从题目文本中提取样例输入输出（客户端正则，复用后端 analyze_problem 逻辑） */
function _extractTestCases(problemText) {
    const lines = problemText.replace(/\r\n/g, '\n').split('\n');
    const samples = [];
    let current = { stdin: '', expected_output: '' };
    let currentKey = '';   // 'stdin' | 'expected_output' | ''
    let inSample = false;  // 是否进入了示例区域
    let inFullCodeFence = false;      // ``` 围栏内
    let inInlineCodeFence = false;    // ~~~ 围栏内

    // 匹配 "### 示例 1" / "## 样例" / "示例 1：" / "Example 1:" 等
    const isSampleHeading = (h) =>
        /^(#+\s*)?(示例\s*\d+|样例\s*\d+|example\s*\d+|sample\s*\d+)/i.test(h);

    // 匹配 "输入：" / "输入:" / "样例输入：" / "Sample Input:" 等
    const isInputMarker = (h) =>
        /^(样例输入|输入样例|示例输入|sample\s*input|example\s*input|输入[：:])/i.test(h);

    // 匹配 "输出：" / "输出:" / "样例输出：" / "Sample Output:" 等
    const isOutputMarker = (h) =>
        /^(样例输出|输出样例|示例输出|sample\s*output|example\s*output|输出[：:])/i.test(h);

    // 匹配非示例的节标题（表示离开示例区域）
    const isSectionHeading = (h) => {
        const known = ['题目描述', '输入描述', '输入格式', '输出描述', '输出格式', '数据范围',
            '约束', '限制', '提示', '注意', '说明', '复杂度分析', '参考解答', '关键思路', '测试用例',
            'description', 'input format', 'output format', 'constraints', 'hint', 'note'];
        const stripped = h.replace(/^#+:?\s*/, '').trim().toLowerCase();
        // 排除示例/样例标题
        if (/^(示例|样例|example|sample)/i.test(stripped)) return false;
        return known.some(k => stripped.startsWith(k.toLowerCase()));
    };

    // 检测是否带冒号的纯输入/输出行（如 "输入："、"输出："）
    const isPlainInput = (line) => /^\s*输入[：:]\s*/.test(line);
    const isPlainOutput = (line) => /^\s*输出[：:]\s*/.test(line);

    for (let i = 0; i < lines.length; i++) {
        const rawLine = lines[i];
        const line = rawLine.trimEnd();
        const trimmed = line.trim();
        const heading = trimmed.replace(/^#+:?\s*/, '').trim();

        // ── 代码围栏追踪 ──
        if (trimmed.startsWith('```')) {
            if (inFullCodeFence) {
                inFullCodeFence = false;
            } else if (trimmed.length > 3 && trimmed.endsWith('```')) {
                // 单行内开闭围栏（如 ```输入：```），跳过
                continue;
            } else {
                inFullCodeFence = true;
            }
            continue;
        }
        if (trimmed.startsWith('~~~')) {
            inInlineCodeFence = !inInlineCodeFence;
            continue;
        }
        if (inFullCodeFence || inInlineCodeFence) continue;

        // ── 示例区域标题：保存上一个，开启新的 ──
        if (isSampleHeading(heading)) {
            // 保存上一个样例
            if (current.stdin.trim() || current.expected_output.trim()) {
                samples.push({ ...current });
            } else {
                // 上一个样例是空的（连续两个示例标题间无内容），丢弃
            }
            current = { stdin: '', expected_output: '' };
            currentKey = '';
            inSample = true;
            continue;
        }

        // ── 退出示例区域：遇到节标题 ──
        if (isSectionHeading(heading)) {
            inSample = false;
            currentKey = '';
            continue;
        }

        // ── 输入/输出标记 ──
        if (isInputMarker(heading) || (inSample && isPlainInput(trimmed))) {
            if (!inSample) {
                // 不在示例区域内也遇到了输入标记，视为新示例开始
                if (current.stdin.trim() || current.expected_output.trim()) {
                    samples.push({ ...current });
                }
                current = { stdin: '', expected_output: '' };
                inSample = true;
            }
            currentKey = 'stdin';
            // 提取冒号后面的内联内容（如 "输入：1 2"）
            const parts = trimmed.split(/[：:]/);
            if (parts.length > 1) {
                const tail = parts.slice(1).join(':').trim();
                if (tail) current.stdin = tail;
            }
            continue;
        }

        if (isOutputMarker(heading) || (inSample && isPlainOutput(trimmed))) {
            if (!inSample) {
                inSample = true;
            }
            currentKey = 'expected_output';
            const parts = trimmed.split(/[：:]/);
            if (parts.length > 1) {
                const tail = parts.slice(1).join(':').trim();
                if (tail) current.expected_output = tail;
            }
            continue;
        }

        // ── 收集内容行 ──
        if (currentKey && current[currentKey] !== undefined && inSample) {
            // 跳过空行（但保留首个空行可能表示多组示例之间的分隔）
            const content = line.trim();
            if (content && !content.startsWith('#') && !/^(输入|输出)[：:]/.test(content)) {
                current[currentKey] += (current[currentKey] ? '\n' : '') + content;
            }
        }
    }

    // 保存最后一个样例
    if (current.stdin.trim() || current.expected_output.trim()) {
        samples.push(current);
    }

    // 如果上述方式没匹配到，尝试兜底：遍历所有非围栏内容，匹配"输入："和"输出："
    if (samples.length === 0) {
        let fallbackCurrent = { stdin: '', expected_output: '' };
        let fallbackKey = '';
        for (const rawLine of lines) {
            const trimmed = rawLine.trim();
            if (trimmed.startsWith('```') || trimmed.startsWith('~~~')) continue;
            if (/^输入[：:]/.test(trimmed)) {
                if (fallbackCurrent.stdin || fallbackCurrent.expected_output) {
                    samples.push({ ...fallbackCurrent });
                }
                fallbackCurrent = { stdin: '', expected_output: '' };
                fallbackKey = 'stdin';
                const parts = trimmed.split(/[：:]/);
                if (parts.length > 1) {
                    const tail = parts.slice(1).join(':').trim();
                    if (tail) fallbackCurrent.stdin = tail;
                }
                continue;
            }
            if (/^输出[：:]/.test(trimmed)) {
                fallbackKey = 'expected_output';
                const parts = trimmed.split(/[：:]/);
                if (parts.length > 1) {
                    const tail = parts.slice(1).join(':').trim();
                    if (tail) fallbackCurrent.expected_output = tail;
                }
                continue;
            }
            if (fallbackKey && fallbackCurrent[fallbackKey] !== undefined && trimmed && !trimmed.startsWith('#')) {
                fallbackCurrent[fallbackKey] += (fallbackCurrent[fallbackKey] ? '\n' : '') + trimmed;
            }
        }
        if (fallbackCurrent.stdin || fallbackCurrent.expected_output) {
            samples.push(fallbackCurrent);
        }
    }

    return samples.filter(s => s.stdin.trim() || s.expected_output.trim()).map((s, i) => ({
        name: `题目样例 ${i + 1}`,
        source: '题目样例',
        stdin: s.stdin.trim(),
        expected_output: s.expected_output.trim(),
    }));
}

/** 从题目编辑器提取用例并填充到用例面板 */
function _extractAndPopulateTestCases(problemText) {
    const extracted = _extractTestCases(problemText);
    if (extracted.length > 0) {
        window.__testCases = extracted;
        _renderTestCaseList();
        showToast(`从题目中检测到 ${extracted.length} 个测试用例`);
    }
}

/** 刷新用例面板标题 */
function _updateTestCaseTitle() {
    const titleEl = document.getElementById('testCasePanelTitle');
    if (titleEl) {
        titleEl.textContent = `测试用例 (${window.__testCases.length})`;
    }
}

/** 渲染用例卡片列表 */
function _renderTestCaseList() {
    const container = document.getElementById('testCaseList');
    if (!container) return;
    _updateTestCaseTitle();
    if (window.__testCases.length === 0) {
        container.innerHTML = '<div style="color:var(--text-muted);font-size:12px;padding:16px;text-align:center;">暂无测试用例，提交题目可自动检测</div>';
        return;
    }
    container.innerHTML = window.__testCases.map((tc, i) => `
        <div class="tc-card">
            <div class="tc-card-header">
                <span>${escapeHtml(tc.name)} <span class="tc-card-source">${escapeHtml(tc.source)}</span></span>
                <div class="tc-card-actions">
                    <button class="tc-card-btn" onclick="deleteTestCase(${i})" title="删除此用例">✕</button>
                </div>
            </div>
            <div class="tc-card-fields">
                <div class="tc-field">
                    <span class="tc-field-label">输入 (stdin)</span>
                    <textarea rows="2" data-tc-index="${i}" data-tc-field="stdin"
                        onchange="_onTestCaseFieldChange(this)" 
                        oninput="_autoResizeTcTextarea(this)">${escapeHtml(tc.stdin)}</textarea>
                </div>
                <div class="tc-field">
                    <span class="tc-field-label">期望输出</span>
                    <textarea rows="2" data-tc-index="${i}" data-tc-field="expected_output"
                        onchange="_onTestCaseFieldChange(this)" 
                        oninput="_autoResizeTcTextarea(this)">${escapeHtml(tc.expected_output)}</textarea>
                </div>
            </div>
        </div>
    `).join('');

    // 渲染后自动调整所有 textarea 高度
    setTimeout(() => {
        container.querySelectorAll('.tc-field textarea').forEach(_autoResizeTcTextarea);
    }, 0);
}

/** 自动调整用例 textarea 高度 */
function _autoResizeTcTextarea(el) {
    el.style.height = 'auto';
    el.style.height = Math.max(32, el.scrollHeight) + 'px';
}

/** 用例字段变更时更新数据 */
function _onTestCaseFieldChange(el) {
    const idx = parseInt(el.dataset.tcIndex);
    const field = el.dataset.tcField;
    if (idx >= 0 && idx < window.__testCases.length && field) {
        window.__testCases[idx][field] = el.value;
    }
}

/** 手动添加空白用例 */
function addTestCase() {
    window.__testCases.push({
        name: `用例 ${window.__testCases.length + 1}`,
        source: '手动添加',
        stdin: '',
        expected_output: '',
    });
    _renderTestCaseList();
    switchTab('cases');
    // 聚焦到新用例的第一个 textarea
    setTimeout(() => {
        const container = document.getElementById('testCaseList');
        if (!container) return;
        const cards = container.querySelectorAll('.tc-card');
        const last = cards[cards.length - 1];
        if (last) {
            const firstTA = last.querySelector('textarea');
            if (firstTA) firstTA.focus();
        }
    }, 100);
}

/** 删除用例 */
function deleteTestCase(index) {
    if (index < 0 || index >= window.__testCases.length) return;
    window.__testCases.splice(index, 1);
    _renderTestCaseList();
}

/** 将用例卡片数据序列化为提交格式（JSON） */
function _serializeTestCases() {
    return JSON.stringify(window.__testCases.map(tc => ({
        stdin: tc.stdin,
        expected_output: tc.expected_output,
    })));
}

// ── 锁按钮降级（CodeMirror 未加载时）────────────
if (!window.toggleProblemLock) {
    window.__problemLocked = false;
    window.toggleProblemLock = function() {
        const editor = window.__editorViews && window.__editorViews['problemInput'];
        if (editor && editor._editableCompartment && window.__cmImports) {
            // CodeMirror 模式（Compartment）
            window.__problemLocked = !window.__problemLocked;
            editor.dispatch({
                effects: editor._editableCompartment.reconfigure(
                    window.__cmImports.EditorView.editable.of(!window.__problemLocked)
                )
            });
        } else {
            // 降级为原生 textarea readOnly
            const ta = document.getElementById('problemInput');
            if (ta) {
                window.__problemLocked = !window.__problemLocked;
                ta.readOnly = window.__problemLocked;
                ta.style.opacity = window.__problemLocked ? '0.6' : '1';
            }
        }
        const btn = document.getElementById('lockProblemBtn');
        if (btn) {
            btn.textContent = window.__problemLocked ? '🔒' : '🔓';
            btn.title = window.__problemLocked ? '解锁题目（允许编辑）' : '锁定题目（禁止编辑）';
        }
    };
}

// ── 事件绑定 ────────────────────────────────────────

function initEvents() {
    const cmdInput = document.getElementById('commandInput');

    cmdInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendCommand();
            return;
        }
        if (e.key === 'ArrowUp') {
            if (state.cmdHistory.length === 0) return;
            if (state.cmdHistoryIdx === -1 || state.cmdHistoryIdx > 0) {
                state.cmdHistoryIdx = (state.cmdHistoryIdx === -1)
                    ? state.cmdHistory.length - 1 : state.cmdHistoryIdx - 1;
                cmdInput.value = state.cmdHistory[state.cmdHistoryIdx];
                e.preventDefault();
            }
        }
        if (e.key === 'ArrowDown') {
            if (state.cmdHistoryIdx === -1) return;
            if (state.cmdHistoryIdx < state.cmdHistory.length - 1) {
                state.cmdHistoryIdx++;
                cmdInput.value = state.cmdHistory[state.cmdHistoryIdx];
            } else {
                state.cmdHistoryIdx = -1;
                cmdInput.value = '';
            }
            e.preventDefault();
        }
    });

    cmdInput.addEventListener('input', showSuggestions);
    cmdInput.addEventListener('blur', () => setTimeout(hideSuggestions, 150));

    document.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === 'Enter') {
            e.preventDefault();
            sendCommand();
        }
        if (e.ctrlKey && e.key === 'b' && !e.target.closest('#commandInput')) {
            e.preventDefault();
            submitCode();
        }
        // Ctrl+1/2/3 切换标签页
        if (e.ctrlKey && !e.altKey && !e.metaKey && !e.shiftKey) {
            if (e.key === '1') { e.preventDefault(); switchTab('problem'); }
            if (e.key === '2') { e.preventDefault(); switchTab('code'); }
            if (e.key === '3') { e.preventDefault(); switchTab('cases'); }
        }
        // Ctrl+Shift+P 拖出题目，Ctrl+Shift+T 拖出用例
        if (e.ctrlKey && e.shiftKey && !e.altKey && !e.metaKey) {
            if (e.key === 'P' || e.key === 'p') { e.preventDefault(); detachTab('problem'); }
            if (e.key === 'T' || e.key === 't') { e.preventDefault(); detachTab('cases'); }
        }
        // Esc 关闭所有浮动面板
        if (e.key === 'Escape') {
            const anyOpen = document.querySelector('.float-panel[style*="display: flex"]');
            if (anyOpen) {
                e.preventDefault();
                document.querySelectorAll('.float-panel').forEach(p => {
                    const tabName = p.id.replace('floatPanel-', '');
                    closeFloatTab(tabName);
                });
            }
        }
    });

    // 标签栏点击：已拖出→放回，未拖出→切换
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            if (_skipTabClick) { _skipTabClick = false; return; }
            const tab = btn.dataset.tab;
            if (!tab) return;
            if (btn.classList.contains('detached')) {
                dockTab(tab);
            } else {
                switchTab(tab);
            }
        });
    });

    document.getElementById('timeoutInput').addEventListener('change', async () => {
        const timeout = document.getElementById('timeoutInput').value;
        addSystemMsg(`设置超时: ${timeout}ms`);
        await normalCommand({ command: 'set_timeout', args: timeout });
    });

    const sessionSwitcher = document.getElementById('sessionSwitcher');
    if (sessionSwitcher) {
        sessionSwitcher.addEventListener('change', () => {
            const newSid = sessionSwitcher.value;
            if (newSid === '__new__') createNewSession();
            else if (newSid !== state.sessionId) switchSession(newSid);
        });
    }

    const reconnectBtn = document.getElementById('reconnectBtn');
    if (reconnectBtn) {
        reconnectBtn.addEventListener('click', () => initSession());
    }

    const langSelect = document.getElementById('langSelect');
    if (langSelect && window.__updateCodeLang) {
        langSelect.addEventListener('change', () => {
            window.__updateCodeLang(langSelect.value);
        });
    }

    // 浮动面板交互
    _initTabDrag();
    _initFloatPanels();

    // 文件上传
    _initFileUpload();
}
