# OJ Coach Agent 需求与实现计划

## 省流版概要

这个项目要从现有 `my-agent` 最小 Coding Agent 框架，扩展出一个第一版终端算法刷题陪练 Agent。第一版只做命令行，不做前端，核心目标是让用户能在终端完成“读题 -> 写代码 -> 设置样例 -> 运行代码 -> 定位错误 -> 继续追问 -> 复盘总结”的完整练习流程。

建议不要把刷题工具混进现有 `coding_tools/`，而是新增独立的 `oj_tools/` 目录，并提供 `build_oj_tools()` 统一注册 OJ 陪练工具。这样可以保持通用 Coding Agent 和刷题陪练 Agent 的职责清晰，也能避免被当前尚未完成的 `coding_tools` 骨架阻塞。

第一版重点实现这些能力：

- 读题：支持粘贴题目文本，或从 `.txt` / `.md` / `.docx` 读取题目。
- 分析题目：提取题意、输入输出、约束、样例，并给出可能算法候选和判断依据。
- 读代码：支持粘贴完整普通 OJ 代码，或从 `.py` / `.cpp` / `.java` 文件读取代码。
- 运行代码：实现 `run_oj_code`，支持 Python、C++、Java，返回结构化运行结果。
- 对比输出：至少忽略末尾空白和换行差异，区分 AC、WA、编译错误、运行错误、超时、无期望输出。
- 错误解释：工具只负责真实运行和捕获错误，LLM 负责把错误翻译成人话。
- 继续追问：基于当前题目、代码、输入、期望输出、实际输出和最近一次运行结果回答问题。
- 复盘总结：总结算法、关键思路、复杂度、错误原因、易错点和下次识别信号。

建议新增的主要文件：

```text
oj_tools/
  __init__.py
  analyze_problem.py
  read_problem_file.py
  read_code_file.py
  run_oj_code.py
  compare_output.py
  summarize_practice.py

oj_coach_main.py
```

终端交互建议采用 `/` 命令式 REPL，例如 `/paste_problem`、`/load_problem`、`/analyze`、`/paste_code`、`/load_code`、`/set_stdin`、`/set_expected`、`/run`、`/ask`、`/summary`、`/exit`。

最大风险点是运行用户代码。实现时要使用临时目录、超时限制、输出长度限制和 `subprocess.run([...])` 参数数组，不要拼 shell 命令，不要让临时编译产物写进项目目录，也不要默认保存用户完整代码或敏感信息。

## 完整版

## 目标定位

在现有 `my-agent` 最小 Coding Agent 框架上，实现第一版终端算法刷题陪练 Agent。第一版不做前端，优先保证能在终端完成：

- 读题
- 读代码
- 设置测试输入和期望输出
- 运行普通 OJ 代码
- 解释编译错误、运行错误、输出错误和超时
- 支持继续追问
- 支持复盘总结

这个 Agent 面向通用 Online Judge / 算法题练习场景，不绑定某个平台。

## 当前项目只读分析

当前项目结构较小，核心模块如下：

- `llm.py`：封装 `LLMClient`，负责 `chat` / `chat_stream` / `count_tokens`。
- `tools.py`：实现 `ToolRegistry`，负责 `register` / `to_schemas` / `invoke`。
- `agent.py`：实现 Agent 主循环：LLM 产生工具调用，执行工具，再把工具结果回传 LLM。
- `main.py`：当前通用 Coding Agent 的终端 REPL 入口。
- `coding_tools/`：通用代码工具目录，当前包含 `read_file` / `write_file` / `edit_file` / `list_dir` / `bash`。
- `context.py`：预留 `ContextManager`，当前还未完成。
- `memory.py`：预留 `Memory`，当前还未完成。
- `interfaces.py`：接口说明文件，不是主运行逻辑。
- `tests/`：章节式测试文件。

观察到的关键点：

- `ToolRegistry` 当前 schema 生成能力比较轻量，只能根据 Python 类型注解生成基础参数类型。
- `Agent.run()` 当前会直接调用 OpenAI tool calling 流程，适合继续复用。
- `main.py` 当前是通用 Coding Agent REPL，不具备刷题状态管理。
- `coding_tools` 当前更像练习骨架，部分工具仍是 `NotImplementedError`，第一版 OJ 陪练不应依赖这些未完成工具。
- 第一版更稳妥的方式是新增独立工具目录和独立终端入口，减少对通用 Coding Agent 的破坏。

## 影响范围

建议新增：

```text
oj_tools/
  __init__.py
  analyze_problem.py
  read_problem_file.py
  read_code_file.py
  run_oj_code.py
  compare_output.py
  summarize_practice.py

oj_coach_main.py
```

建议尽量少改：

- `llm.py`：不改。
- `tools.py`：第一版尽量不改；如后续需要更精细 schema，再单独升级。
- `agent.py`：第一版尽量不改，复用现有主循环。
- `main.py`：不直接替换现有通用入口，避免破坏原 Coding Agent。
- `coding_tools/`：不混入 OJ 专用工具，保持职责清晰。
- `context.py` / `memory.py`：第一版可后置，不作为必需路径。

## 风险提示

> 【风险提示】
> 当前需求涉及运行用户提交的代码。即使第一版只在本地临时目录中运行，也仍然存在死循环、消耗资源、访问本机文件、发起网络请求等风险。实现时必须默认采用超时、临时目录、参数数组执行命令、限制输出长度等防护措施。

当前行为：

- 项目只有通用 Coding Agent REPL。
- 没有 OJ 题目状态。
- 没有专用代码运行沙箱。
- 没有编译错误、运行错误、Wrong Answer、TLE 的结构化结果。

预期变更：

- 新增 OJ Coach 专用 REPL。
- 新增 OJ 工具注册入口 `build_oj_tools()`。
- 新增读取题目、读取代码、分析题目、比较输出、运行代码、复盘总结工具。
- 运行用户代码时只在临时目录中写入临时代码文件和编译产物。
- 不保存敏感信息或完整代码，除非用户明确确认。

## 第一版功能需求

### 1. 读题

支持：

- 用户直接粘贴题目文本。
- 从本地 `.txt` / `.md` / `.docx` 文件读取题目。
- 解析题意、输入输出、约束、样例。
- 判断可能用到的算法，例如哈希表、双指针、滑动窗口、二分、栈、BFS、DFS / 回溯、DP、贪心、图论、并查集、堆等。
- 输出算法候选、判断依据、学习提示。

### 2. 读取代码

支持：

- 用户直接粘贴完整普通 OJ 代码。
- 从本地 `.py` / `.java` / `.cpp` 文件读取代码。

第一版限制：

- 暂不支持平台专属的 `class Solution` 自动驱动。
- 代码必须完整包含输入输出逻辑，可以直接从 `stdin` 读、向 `stdout` 写。

### 3. 运行代码

实现 `run_oj_code` 工具。

输入：

- `language: str`
- `code: str`
- `stdin: str`
- `expected_output: str = ""`
- `timeout_ms: int = 3000`

输出：

- `status`
- `stdout`
- `stderr`
- `exit_code`
- `compile_output`
- `time_ms`
- `normalized_stdout`
- `normalized_expected_output`

`status` 包括：

- `accepted`
- `wrong_answer`
- `compile_error`
- `runtime_error`
- `time_limit_exceeded`
- `no_expected_output`

语言支持：

- Python：直接运行。
- C++：先编译 `g++ main.cpp -std=c++17 -O2 -o main`，再运行。
- Java：先编译 `javac Main.java`，再运行 `java Main`。
- JavaScript：可选，后续视本地 Node.js 环境决定。

安全要求：

- 不用字符串拼 shell 命令。
- 使用 `subprocess.run([...])` 参数数组。
- 运行目录使用临时目录，不在项目目录中生成编译产物。
- 设置超时时间。
- 限制输出长度。
- 默认不提供删除文件、系统破坏、危险命令能力。
- 不保存用户完整代码，除非用户明确确认。

### 4. 错误解释和追问

职责划分：

- 工具负责真实运行和捕获错误。
- LLM 负责把编译错误、运行错误、Wrong Answer、TLE 翻译成人话。

用户可以继续问：

- 为什么超时？
- 为什么这个用例过不了？
- 我的思路哪里有问题？
- 怎么优化？

回答时需要结合：

- 当前题目
- 当前代码
- 当前 `stdin`
- 当前 `expected_output`
- 当前 `stdout`
- 当前 `stderr`
- 最近一次运行结果

回答策略：

- 不要一上来直接给完整答案。
- 默认分层提示：方向 -> 关键观察 -> 伪代码 -> 完整代码。
- 用户明确要求完整代码时再给完整代码。
- 不要捏造运行结果，只有 `run_oj_code` 返回后才能说“运行结果”。

### 5. 复盘总结

实现 `summarize_practice`。

输入建议：

- `problem_text: str`
- `code: str`
- `run_result: str`
- `notes: str = ""`

输出建议：

- 本题算法
- 关键思路
- 时间复杂度
- 空间复杂度
- 用户错误
- 易错点
- 下次识别信号

Memory 第一版可以后置。若轻量实现，只保存结构化 JSON，不默认保存完整代码：

```json
{
  "problem_title": "",
  "algorithms": [],
  "mistakes": [],
  "status": "",
  "review_note": "",
  "last_practiced_at": ""
}
```

## 建议新增工具目录

```text
oj_tools/
  __init__.py
  analyze_problem.py
  read_problem_file.py
  read_code_file.py
  run_oj_code.py
  compare_output.py
  summarize_practice.py
```

`oj_tools/__init__.py` 提供：

```python
def build_oj_tools() -> ToolRegistry:
    ...
```

它负责创建 `ToolRegistry` 并注册 OJ 刷题陪练工具，类似现有 `coding_tools.build_coding_tools()`。

## 工具清单

### `read_problem_file(file_path: str) -> str`

支持：

- `.txt`
- `.md`
- `.docx`

行为：

- `.txt` / `.md` 直接读取文本。
- `.docx` 使用 `python-docx` 读取段落和表格。
- 返回题目文本。

### `read_code_file(file_path: str) -> str`

支持：

- `.py`
- `.java`
- `.cpp`

行为：

- 返回代码文本。
- 根据扩展名推断语言。

### `analyze_problem(problem_text: str) -> dict | str`

行为：

- 提取标题。
- 提取输入输出描述。
- 提取约束。
- 提取样例。
- 判断输入类型。
- 给出算法候选。
- 给出判断依据和学习建议。

### `compare_output(stdout: str, expected_output: str) -> dict | str`

行为：

- 标准化输出后比较。
- 至少忽略末尾空白和换行差异。
- 后续可支持忽略多余空格、浮点误差等模式。

### `run_oj_code(language: str, code: str, stdin: str, expected_output: str = "", timeout_ms: int = 3000) -> dict | str`

行为：

- 编译或运行代码。
- 传入 `stdin`。
- 捕获 `stdout` / `stderr` / 退出码 / 编译输出 / 耗时。
- 根据期望输出给出状态。

### `summarize_practice(problem_text: str, code: str, run_result: str, notes: str = "") -> str`

行为：

- 可先作为 LLM prompt 层能力。
- 第一版不强依赖持久化记忆。

## 终端 REPL 命令设计

建议采用命令式 REPL，命令以 `/` 开头。

### `/paste_problem`

多行粘贴题目，直到 `END`。

### `/load_problem path/to/problem.docx`

从文件读取题目。

### `/analyze`

分析当前题目。

### `/paste_code python|cpp|java`

多行粘贴代码，直到 `END`。

### `/load_code path/to/main.cpp`

读取代码文件，并根据扩展名推断语言。

### `/set_stdin`

多行粘贴测试输入，直到 `END`。

### `/set_expected`

多行粘贴期望输出，直到 `END`。

### `/run`

运行当前代码并解释结果。

### `/ask 为什么这个用例过不了？`

基于当前题目、代码、测试、最近一次运行结果回答问题。

### `/summary`

总结算法和复盘。

### `/exit`

退出。

## REPL 状态设计

```python
state = {
    "problem_text": "",
    "language": "",
    "code": "",
    "stdin": "",
    "expected_output": "",
    "last_run_result": None,
    "analysis_result": None,
}
```

## OJ Coach 系统提示词要求

Agent 人设：

- 你是算法刷题陪练 Agent。
- 你的目标不是直接给答案，而是陪用户完成“读题 -> 写代码 -> 运行 -> 定位错误 -> 修正 -> 复盘”。

回答规范：

- 对编译错误要翻译成人话。
- 对运行错误要指出可能触发原因。
- 对 Wrong Answer 要结合实际输出和期望输出解释。
- 对 TLE 要结合题目约束和复杂度解释。
- 默认不要直接给完整代码，先给提示和定位。
- 用户明确要求完整代码时再给。
- 不要捏造运行结果，只有 `run_oj_code` 工具返回后才能说“运行结果”。
- 注意安全，不执行删除文件、系统破坏、危险命令，不保存敏感信息。

## 实施计划

### 第一步：新增需求文档

- 新增 `oj-coach-agent.md`。
- 将平台绑定命名替换为通用 OJ 命名。
- 不修改业务代码。

### 第二步：新增 OJ 工具目录

- 新增 `oj_tools/`。
- 实现 `read_problem_file`、`read_code_file`、`compare_output`、`run_oj_code`。
- `analyze_problem` 和 `summarize_practice` 第一版可做规则版和 prompt 辅助版。

### 第三步：新增 OJ Coach REPL

- 新增 `oj_coach_main.py`。
- 维护内存状态。
- 支持 `/paste_problem`、`/load_problem`、`/analyze`、`/paste_code`、`/load_code`、`/set_stdin`、`/set_expected`、`/run`、`/ask`、`/summary`、`/exit`。

### 第四步：接入 LLM 解释层

- 复用 `LLMClient`。
- 对 `/run` 的结果调用 LLM 做解释。
- 对 `/ask` 组合当前上下文和用户问题。
- 对 `/summary` 生成复盘。

### 第五步：验证

- 增加或手工验证 Python / C++ / Java 的最小 OJ 示例。
- 验证 `accepted`、`wrong_answer`、`compile_error`、`runtime_error`、`time_limit_exceeded`、`no_expected_output`。
- 不跑破坏性命令。
- 不写入项目目录中的临时编译产物。

## 暂不做的内容

- 不做前端。
- 不做平台专属 `class Solution` 自动驱动。
- 不做完整向量记忆。
- 不默认保存完整代码。
- 不改造生产环境或远程环境。
- 不做危险命令执行能力。
