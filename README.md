# OJ Coach Agent 第二版开发需求与实现计划

## 项目定位

OJ Coach Agent 是一个本地算法刷题陪练工具，目标是陪用户完成：

```text
读题 -> 分析题目 -> 写代码 -> 管理测试用例 -> 运行代码 -> 定位错误 -> 继续追问 -> 复盘总结
```

第一版已经完成终端可用链路。第二版的目标是把现有能力升级为“前端 + 本地后端 API + 可复用命令层 + 上下文压缩”的桌面式刷题工作台。

第二版不改变核心原则：

- 工具负责真实读取、运行、对比和结构化结果。
- LLM 负责解释错误、引导思路、回答追问和复盘。
- 不捏造运行结果，只有真实运行后才能说明运行状态。
- 默认本地运行，谨慎处理用户代码和文件。

## 当前已完成基线

### OJ 工具层

已存在 `oj_tools/`：

```text
oj_tools/
  __init__.py
  analyze_problem.py
  read_problem_file.py
  read_code_file.py
  run_oj_code.py
  compare_output.py
  summarize_practice.py
  _algorithm_rules.py
```

主要能力：

- 读取题目文本或题目文件。
- 读取 Python / C++ / Java 代码。
- 分析题目并提取样例。
- 统一测试用例 JSON。
- 运行 OJ 代码并返回结构化结果。
- 对比实际输出与期望输出。
- 生成规则版复盘。

### 会话层

已新增 `oj_coach/session.py`，核心类是 `OJCoachSession`。

它负责维护当前刷题状态：

```text
problem_text
analysis_result
language
code
test_cases
last_run_result
timeout_ms
```

它负责串联这些动作：

- `set_problem_text`
- `load_problem_file`
- `analyze_problem`
- `set_code`
- `load_code_file`
- `add_cases`
- `set_timeout`
- `run_code`
- `ask` / `ask_stream`
- `summarize`
- `status`

### 命令路由层

已新增 `oj_coach/commands.py`，核心类是 `OJCoachCommandRouter`。

这一层统一处理 `/` 命令：

- 解析命令和参数。
- 判断是否需要多行输入。
- 调用 `OJCoachSession`。
- 返回结构化 `CommandResponse`。
- 渲染运行结果、状态、帮助文本和复盘结果。

当前 CLI 和未来前端都应该复用这一层，避免在多个入口里重复实现 `/run`、`/ask`、`/summary` 等逻辑。

### CLI 薄壳

`oj_coach_main.py` 已经变成薄 CLI：

- 启动一个 `OJCoachCommandRouter`。
- 读取用户输入。
- 收集多行内容。
- 打印 `CommandResponse`。
- `/exit` 退出。

它不再维护旧状态，也不再直接编排工具调用。

### 测试基线

已有测试覆盖：

- `tests/test_oj_coach_session.py`
- `tests/test_oj_coach_commands.py`
- `oj_tools_test/` 下的 OJ 工具测试

当前环境如果没有 `pytest`，可以直接执行测试函数；后续第二版建议补齐标准测试入口。

## 第二版目标

第二版要在当前基线上实现一个本地 Web 工作台。

核心需求：

1. 提供前端界面。
2. 前端支持 `/` 命令，行为和 CLI 保持一致。
3. 前端底部是命令输入框。
4. 上方左侧包含题目框、代码框、测试用例框。
5. 上方右侧是对话框。
6. 题目框、代码框、测试用例框、对话框都可以拖动调整大小。
7. 支持流式回答。
8. 准备加入上下文压缩能力。
9. 保留 CLI，CLI 继续作为轻量调试入口。

## 第二版推荐架构

```text
前端 UI
  |
  | HTTP / SSE 或 WebSocket
  v
本地 API 层
  |
  v
OJCoachCommandRouter
  |
  v
OJCoachSession
  |
  v
oj_tools + LLMClient
```

关键原则：

- 前端不直接实现刷题业务逻辑。
- API 不重复写 `/` 命令逻辑。
- CLI 和前端都走 `OJCoachCommandRouter`。
- 会话状态只由 `OJCoachSession` 管理。
- 上下文压缩只读会话状态和事件日志，不直接散落在 UI 中。

## 后端开发需求

### 1. 新增本地 API 层

建议新增：

```text
oj_coach/api.py
```

建议使用 FastAPI。

初始接口：

```text
POST /api/sessions
GET  /api/sessions/{session_id}/status
POST /api/sessions/{session_id}/command
POST /api/sessions/{session_id}/command/stream
```

可选拆分接口：

```text
POST /api/sessions/{session_id}/problem
POST /api/sessions/{session_id}/code
POST /api/sessions/{session_id}/cases
POST /api/sessions/{session_id}/run
POST /api/sessions/{session_id}/ask
POST /api/sessions/{session_id}/summary
```

第一阶段建议先做统一 `command` 接口，降低前端接入成本。

### 2. 会话管理

API 层需要维护多个本地会话：

```python
sessions: dict[str, OJCoachCommandRouter]
```

每个 session 持有独立的：

- `OJCoachSession`
- `OJCoachCommandRouter`
- 事件日志
- 上下文压缩状态

第一版 API 可以只做内存会话，不做持久化。

### 3. 命令请求格式

建议请求：

```json
{
  "command": "paste_code",
  "args": "python",
  "input_text": "a, b = map(int, input().split())\nprint(a + b)"
}
```

也可以允许前端直接传原始命令：

```json
{
  "raw": "/run"
}
```

API 内部使用 `parse_command_line(raw)` 转成命令和参数。

### 4. 命令响应格式

建议响应：

```json
{
  "ok": true,
  "messages": [],
  "output": "",
  "data": {},
  "status": {}
}
```

`CommandResponse.stream` 不能直接 JSON 序列化。流式回答应由 `/command/stream` 单独处理。

### 5. 流式输出

建议先用 SSE：

```text
POST /api/sessions/{session_id}/command/stream
```

适用命令：

- `/ask`
- 后续可能扩展到 `/run` 的 LLM 解释
- 后续可能扩展到 `/summary` 的 LLM 讲解

如果后面要做更复杂的双向交互，再升级为 WebSocket。

## 前端开发需求

### 1. 技术选型

建议：

```text
frontend/
  Vite
  React
  TypeScript
  Monaco Editor
  react-resizable-panels
```

原因：

- React 适合复杂交互面板。
- Monaco Editor 适合代码编辑。
- `react-resizable-panels` 适合实现可拖动布局。
- Vite 本地开发简单，适合当前阶段。

### 2. 页面布局

第一屏就是工作台，不做营销页。

建议布局：

```text
┌─────────────────────────────────────────────────────────────┐
│ 顶部工具栏：会话状态 / 运行状态 / 超时设置 / 语言选择        │
├───────────────────────────────┬─────────────────────────────┤
│ 左侧工作区                    │ 右侧对话区                  │
│                               │                             │
│ ┌───────────────────────────┐ │ ┌─────────────────────────┐ │
│ │ 题目框                    │ │ │ 对话消息                │ │
│ └───────────────────────────┘ │ │                         │ │
│ ┌───────────────────────────┐ │ │                         │ │
│ │ 代码框                    │ │ │                         │ │
│ └───────────────────────────┘ │ └─────────────────────────┘ │
│ ┌───────────────────────────┐ │                             │
│ │ 测试用例框                │ │                             │
│ └───────────────────────────┘ │                             │
├───────────────────────────────┴─────────────────────────────┤
│ 底部命令输入框：/run、/ask、/summary、/set_cases ...          │
└─────────────────────────────────────────────────────────────┘
```

所有主要区域需要支持拖动调整大小：

- 左右分栏可调。
- 左侧题目 / 代码 / 测试用例高度可调。
- 对话区随窗口变化自适应。
- 底部命令输入框高度可支持多行。

### 3. 题目框

功能：

- 粘贴或编辑题目文本。
- 调用 `/paste_problem`。
- 显示自动分析状态。
- 显示题目样例提取结果摘要。

后续可加：

- 从文件加载题目。
- 题目分析 JSON 的可视化展示。

### 4. 代码框

功能：

- Monaco Editor 编辑代码。
- 语言选择：Python / C++ / Java。
- 调用 `/paste_code <language>`。
- 展示最近一次运行状态。

注意：

- 前端编辑代码不等于 session 已更新。
- 用户点击运行或发送命令前，需要把当前编辑器内容同步到后端。

### 5. 测试用例框

功能：

- 支持 JSON 格式。
- 支持“输入/输出”文本格式。
- 调用 `/set_cases`。
- 展示当前可运行用例数量。
- 区分来源：题目 / 用户。

### 6. 对话框

功能：

- 展示系统消息、运行结果、LLM 回复。
- 支持流式输出。
- 支持复制单条消息。
- 展示错误状态。

消息类型建议：

```text
system
user
assistant
tool
run_result
error
```

### 7. 底部命令输入框

功能：

- 支持 `/` 命令。
- 支持普通问题自动转成 `/ask`。
- 支持命令候选提示。
- 支持多行输入。
- Enter 发送，Shift+Enter 换行。

命令候选来自后端或前端常量，第一阶段可以前端写死：

```text
/paste_problem
/paste_code
/set_cases
/run
/ask
/summary
/status
/set_timeout
```

## 上下文压缩设计

第二版先预留上下文压缩，不要一开始就把压缩逻辑塞进前端。

建议新增：

```text
oj_coach/context.py
```

核心对象：

```python
class SessionEvent:
    type: str
    payload: dict
    created_at: str

class ContextSnapshot:
    problem_summary: str
    code_summary: str
    test_case_summary: str
    run_summary: str
    conversation_summary: str
    important_facts: list[str]

class ContextCompressor:
    def should_compress(...)
    def compress(...)
    def build_llm_context(...)
```

压缩输入：

- 当前题目。
- 题目分析。
- 当前代码摘要。
- 当前测试用例摘要。
- 最近运行结果。
- 用户追问和 LLM 回答。
- 关键错误定位结论。

压缩输出：

- 问题本质。
- 当前解法状态。
- 已发现错误。
- 已验证样例。
- 用户仍在追问的重点。
- 不应丢失的事实。

第一阶段可以只记录事件日志，不真正压缩：

```text
event log -> 未来压缩器输入
```

第二阶段再接入 LLM 压缩。

## 数据流设计

### 运行代码

```text
前端点击运行或输入 /run
  -> 如代码编辑器有未同步内容，先调用 /paste_code
  -> 调用 /run
  -> API 调用 OJCoachCommandRouter.execute("run")
  -> OJCoachSession.run_code()
  -> oj_tools.run_oj_code()
  -> 返回结构化结果
  -> 前端渲染运行结果和测试用例明细
```

### 追问

```text
用户输入问题
  -> 前端转成 /ask 或直接调用 /command/stream
  -> CommandRouter 调用 session.ask_stream()
  -> session 构造当前上下文
  -> LLM 流式返回
  -> 前端逐 token 追加到对话框
```

### 上下文压缩

```text
每次命令执行后记录事件
  -> 检查上下文长度或事件数量
  -> 达到阈值后生成 ContextSnapshot
  -> 后续 ask / summary 使用 snapshot + 当前最新状态
```

## 安全要求

> 【风险提示】
> 本项目会运行用户提供的代码。即使只在本地运行，也可能出现死循环、资源占用、读取本机文件、访问网络等风险。

当前行为：

- 第一版已经通过 `run_oj_code` 运行本地代码。
- CLI 会提醒 `/run` 会执行当前代码。
- 运行结果会结构化返回。

第二版预期：

- API 仍然只面向本地开发环境。
- 不开放远程公网服务。
- 不默认持久化用户完整代码。
- 不在前端保存 API Key、Token、私钥等敏感信息。
- 运行用户代码时继续保留超时限制。
- 不把临时编译产物写入项目目录。

后续如果要暴露到远程服务器，必须重新设计沙箱和权限隔离。

## 实施计划

### 阶段 0：当前已完成

- 新增 `OJCoachSession`。
- 新增 `OJCoachCommandRouter`。
- `oj_coach_main.py` 已变成薄 CLI。
- 已补充 session 和 command router 测试。

### 阶段 1：本地 API 层

新增：

```text
oj_coach/api.py
```

任务：

- 引入 FastAPI 依赖。
- 实现内存 session 管理。
- 实现 `/api/sessions`。
- 实现 `/api/sessions/{session_id}/status`。
- 实现 `/api/sessions/{session_id}/command`。
- 实现 `/api/sessions/{session_id}/command/stream`。
- 给 API 层补测试。

验收标准：

- CLI 不受影响。
- API 可以执行 `/status`、`/paste_problem`、`/paste_code`、`/run`。
- `/ask` 可以走流式输出。

### 阶段 2：前端工程骨架

新增：

```text
frontend/
```

任务：

- 初始化 Vite + React + TypeScript。
- 建立 API client。
- 建立全局 session 状态。
- 实现顶部工具栏。
- 实现底部命令输入框。
- 实现基础对话消息列表。

验收标准：

- 页面启动后自动创建 session。
- 输入 `/status` 能看到后端返回。
- 普通问题能转成 `/ask`。

### 阶段 3：可拖动工作台布局

任务：

- 引入 `react-resizable-panels`。
- 实现左右分栏。
- 实现左侧题目 / 代码 / 测试用例三块可调高度。
- 对话框占右侧完整区域。
- 底部命令输入框固定在底部。

验收标准：

- 桌面宽屏下布局稳定。
- 面板拖动不会遮挡文本。
- 窗口缩放后仍可使用。

### 阶段 4：题目、代码、测试用例联动

任务：

- 题目框接 `/paste_problem`。
- 代码框接 `/paste_code <language>`。
- 测试用例框接 `/set_cases`。
- 运行按钮或 `/run` 同步当前代码后运行。
- 渲染测试用例通过情况。

验收标准：

- 粘贴 A+B 题目和 Python AC 代码后可以运行通过。
- Wrong Answer、Runtime Error、Compile Error 至少能在 UI 中清楚展示。

### 阶段 5：流式对话和复盘

任务：

- `/ask` 使用 SSE 流式渲染。
- `/summary` 渲染规则版复盘和 LLM 讲解版复盘。
- 对话框记录用户问题、系统消息、运行结果和 LLM 回复。

验收标准：

- 用户追问时能看到流式输出。
- LLM 不可用时 UI 能显示明确提示。

### 阶段 6：事件日志和上下文压缩预留

任务：

- 增加 session event log。
- 每次命令执行后记录事件。
- 新增 `ContextCompressor` 骨架。
- `ask` 构造上下文时预留 snapshot 注入位置。

验收标准：

- 不影响现有问答和运行。
- 可以查看当前事件数量和最近事件。
- 压缩功能关闭时行为与当前一致。

### 阶段 7：上下文压缩正式接入

任务：

- 设置压缩触发阈值。
- 用 LLM 生成 `ContextSnapshot`。
- 后续追问使用 snapshot + 最新状态。
- 为压缩结果补测试或可回放用例。

验收标准：

- 长对话后仍能保留题目、代码、错误定位和关键结论。
- 压缩不会覆盖最新代码和最新运行结果。
- 压缩失败时自动回退到未压缩上下文。

## 暂不做

- 不做公网部署。
- 不做多用户权限系统。
- 不做远程代码执行服务。
- 不做平台专属 `class Solution` 自动驱动。
- 不做完整持久化题库。
- 不默认保存完整用户代码。
- 不在前端保存敏感凭据。

## 下一步建议

下一步优先做阶段 1：本地 API 层。

理由：

- 前端需要稳定的本地接口。
- CLI 已经足够薄，可以继续保留。
- `OJCoachCommandRouter` 已经统一了 `/` 命令，API 只需要包装它。
- API 打通后，前端可以快速接入 `/status`、`/run`、`/ask`。
