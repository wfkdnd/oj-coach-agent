# OJ Coach Agent

OJ Coach Agent 是一个面向 Online Judge / 算法刷题练习的本地陪练 Agent。第一版已经完成终端版能力：读题、分析题目、读取代码、管理测试用例、运行代码、解释运行结果、继续追问和复盘总结。

当前推荐入口是 `oj_coach_main.py`。它和通用 Coding Agent 入口 `main.py` 分开维护：`oj_coach_main.py` 使用明确的 `/` 命令管理刷题状态；`main.py` 仍是通用 Coding Agent，并额外注册了 OJ 工具。

> 【风险提示】
> `/run` 会在本机执行当前代码。项目已经使用临时目录、超时限制、输出截断和 `shell=False` 降低风险，但这不是完整沙箱。请只运行可信代码，不要运行来源不明或可能破坏本机环境的代码。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

如果需要更完整地读取 `.docx` 题目文件，可以额外安装：

```bash
pip install python-docx
```

未安装 `python-docx` 时，项目会尝试使用标准库解析 `.docx` 的正文内容。

### 2. 配置 LLM 环境变量

LLM 相关能力包括：样例 JSON 提取、运行结果解释、追问、讲解版复盘。

可以在 `.env` 或系统环境变量中配置：

```text
BASE_URL=你的 OpenAI-compatible API 地址
API_KEY=你的 API Key
MODEL_ID=你的模型名称
```

如果没有配置 LLM，仍然可以使用规则版题目分析、代码运行、输出对比和规则版复盘。

### 3. 启动 OJ Coach

```bash
python oj_coach_main.py
```

启动后输入：

```text
/help
```

查看可用命令。

## 典型流程

```text
/paste_problem
粘贴题目
END

/paste_code python
粘贴完整 OJ 代码
END

/run

/ask 为什么这个用例过不了？

/summary 记录一下这次错在边界条件
```

读取题目后，程序会自动做两件事：

- 调用规则分析器提取题意、约束、样例和算法候选。
- 尝试用 LLM 把题目样例提取成统一的 `test_cases` JSON。

当题目样例和代码都已经就绪时，终端版会自动运行已有测试用例。

## 终端命令

### `/help`

显示帮助信息。

### `/status`

查看当前刷题状态，包括题目、分析结果、语言、代码、测试用例、最近运行结果和超时时间。

### `/paste_problem`

粘贴题目文本，单独输入 `END` 结束。成功后会自动分析题目，并尝试提取样例。

### `/load_problem <path>`

从文件读取题目。支持：

- `.txt`
- `.md`
- `.docx`

示例：

```text
/load_problem oj_tools_test/cases/interval_cover/problem.md
```

### `/analyze`

重新分析当前题目。

分析结果是结构化 JSON，主要包含：

- `标题`
- `题意`
- `输入描述`
- `输出描述`
- `约束`
- `样例`
- `测试用例`
- `输入类型判断`
- `算法候选`
- `学习建议`

### `/paste_code <language>`

粘贴完整 OJ 代码，单独输入 `END` 结束。

支持语言：

- `python`
- `cpp`
- `java`

别名支持：

- `py` / `python3` -> `python`
- `c++` / `cc` -> `cpp`

第一版要求代码本身包含完整输入输出逻辑，也就是可以直接从 `stdin` 读取并输出到 `stdout`。暂不支持 LeetCode 风格 `class Solution` 自动驱动。

### `/load_code <path>`

从代码文件读取完整 OJ 代码，并根据扩展名识别语言。支持：

- `.py`
- `.cpp`
- `.java`

### `/set_cases`

添加用户测试用例。题目样例和用户用例会统一写入 `test_cases` JSON。

支持 JSON 格式：

```json
{
  "test_cases": [
    {
      "name": "自定义用例 1",
      "stdin": "1 2",
      "expected_output": "3"
    }
  ]
}
```

也支持文本格式：

```text
输入：
1 2
输出：
3
END
```

多组用例可以用 `---` 或 `===` 分隔：

```text
输入：
1 2
输出：
3
---
输入：
10 20
输出：
30
END
```

说明：旧命令 `/set_stdin` 和 `/set_expected` 已废弃。现在统一使用 `/set_cases`，一组用例中同时包含输入和期望输出。

### `/set_timeout <ms>`

设置运行超时时间，单位是毫秒。

示例：

```text
/set_timeout 5000
```

工具层会把超时时间限制在安全范围内，最大为 `30000ms`。

### `/run`

运行当前代码。

运行器会返回结构化结果，主要字段包括：

- `status`
- `stdout`
- `stderr`
- `exit_code`
- `compile_output`
- `time_ms`
- `normalized_stdout`
- `normalized_expected_output`
- `diff_info`
- `case_count`
- `passed_count`
- `failed_count`
- `test_cases`

`status` 可能是：

- `accepted`
- `wrong_answer`
- `compile_error`
- `runtime_error`
- `time_limit_exceeded`
- `no_expected_output`

如果 LLM 可用，`/run` 后会自动生成一段调试建议。

### `/ask [question]`

基于当前代码、题目分析和最近一次真实运行结果继续追问。

可以单行提问：

```text
/ask 为什么这个用例过不了？
```

也可以输入 `/ask` 后多行提问，单独输入 `END` 结束。

### `/summary [notes]`

生成规则版复盘总结，并在 LLM 可用时生成讲解版复盘。

规则版复盘包含：

- 题目
- 语言
- 运行状态
- 算法推测
- 时间复杂度
- 空间复杂度
- 错误分析
- 易错点
- 下次识别信号
- 用户备注
- 复盘时间

### `/exit`

退出终端。

## 已实现能力

### 题目读取

实现位置：

- `oj_tools/read_problem_file.py`

能力：

- `read_problem(problem_text="", file_path="")`
- `read_problem_file(file_path)`
- 支持粘贴文本。
- 支持读取 `.txt` / `.md` / `.docx`。
- 文本编码尝试 `utf-8`、`utf-8-sig`、`gb18030`。
- `.docx` 优先使用 `python-docx`，失败时使用标准库解析正文 XML。

### 题目分析

实现位置：

- `oj_tools/analyze_problem.py`
- `oj_tools/_algorithm_rules.py`

能力：

- 规则提取标题、题意、输入输出、约束、样例。
- 从样例构建可运行测试用例。
- 根据关键词推测输入类型。
- 根据关键词匹配算法候选。
- 生成学习建议。

当前算法候选规则包括：

- 哈希表
- 双指针
- 滑动窗口
- 二分
- 栈
- BFS
- DFS / 回溯
- 动态规划
- 贪心
- 图论
- 并查集
- 堆 / 优先队列

### 代码读取

实现位置：

- `oj_tools/read_code_file.py`

能力：

- `read_code(code_text="", file_path="", language="")`
- `read_code_file(file_path)`
- 支持粘贴完整代码。
- 支持读取 `.py` / `.cpp` / `.java`。
- 根据扩展名推断语言。
- 返回结构化 JSON，包含 `source`、`file_path`、`language`、`code`。

### 输出对比

实现位置：

- `oj_tools/compare_output.py`

能力：

- `strict`：逐字符比较。
- `trailing`：忽略每行末尾空白和首尾空行，默认模式。
- `relaxed`：合并连续空白后比较。
- `full_trim`：去掉每行首尾空白和首尾空行后比较。
- 失败时返回首个差异位置或行数差异。

### 代码运行

实现位置：

- `oj_tools/run_oj_code.py`

能力：

- 支持 Python、C++、Java。
- Python 使用当前 Python 解释器运行。
- C++ 使用 `g++ main.cpp -std=c++17 -O2 -o main` 编译后运行。
- Java 使用 `javac Main.java` 编译后运行 `java Main`。
- 使用临时目录保存代码和编译产物。
- 使用 `subprocess.run([...], shell=False)` 执行。
- 支持超时。
- 输出最长保留 `20000` 字符。
- 支持批量测试用例。

运行状态优先级：

1. `compile_error`
2. `time_limit_exceeded`
3. `runtime_error`
4. `wrong_answer`
5. `accepted`
6. `no_expected_output`

### 复盘总结

实现位置：

- `oj_tools/summarize_practice.py`

能力：

- 解析 `run_oj_code` 的 JSON 结果。
- 推测题目算法。
- 根据代码粗略推测复杂度。
- 根据运行状态分析错误。
- 检测常见易错点。
- 生成下次识别信号。
- 提供 `build_summary_memory(summary_json)`，可把复盘结果转为不包含完整代码的轻量记忆格式。

## 项目结构

```text
.
├── agent.py                    # 通用 Agent 主循环
├── llm.py                      # LLMClient
├── tools.py                    # ToolRegistry
├── context.py                  # 基础上下文压缩管理器
├── memory.py                   # 基础向量记忆
├── main.py                     # 通用 Coding Agent 入口
├── oj_coach_main.py            # OJ Coach 终端入口
├── coding_tools/               # 通用代码工具
├── oj_tools/                   # OJ 专用工具
│   ├── __init__.py
│   ├── _algorithm_rules.py
│   ├── analyze_problem.py
│   ├── compare_output.py
│   ├── read_code_file.py
│   ├── read_problem_file.py
│   ├── run_oj_code.py
│   └── summarize_practice.py
├── tests/                      # 通用 Agent / 工具测试
└── oj_tools_test/              # OJ 工具测试
```

## 工具注册

`oj_tools/__init__.py` 提供：

```python
from oj_tools import build_oj_tools

tools = build_oj_tools()
```

当前注册的 OJ 工具有：

- `read_problem`
- `read_problem_file`
- `analyze_problem`
- `read_code`
- `read_code_file`
- `run_oj_code`
- `compare_output`
- `summarize_practice`

`main.py` 会把通用 `coding_tools` 和 `oj_tools` 合并到同一个工具注册表中。

## 上下文与记忆现状

`context.py` 已有基础 `ContextManager`：

- 根据 token 数判断是否需要压缩。
- 保留 system 消息和最近若干条消息。
- 使用 LLM 把中间对话压缩成中文摘要。

但第一版 OJ Coach 终端入口还没有把 `ContextManager` 接入主流程。

`memory.py` 已有基础 `Memory`：

- 使用 embedding 存储文本记忆。
- 支持相似度检索。
- 支持 JSON 保存和加载。

但第一版 OJ Coach 默认不保存完整代码，也没有把向量记忆接入刷题流程。

## 当前限制

- 还没有前端。
- 还没有完整系统级沙箱。
- 不支持 JavaScript。
- 不支持 LeetCode 风格 `class Solution` 自动驱动。
- 不默认保存用户完整代码。
- 不默认持久化刷题会话。
- 上下文压缩和向量记忆已有基础模块，但尚未接入 OJ Coach 主流程。
- C++ 运行依赖本机可用 `g++`。
- Java 运行依赖本机可用 JDK 和 `javac`。

## 测试

项目包含两组测试：

```bash
pytest tests
pytest oj_tools_test
```

其中 C++ / Java 相关测试依赖本机已安装对应编译器或 JDK。

## 第二版方向

第二版建议在保留当前终端能力的前提下，先抽出可复用的 OJ 会话层，再做前端。

建议目标：

- 增加 Web 前端。
- 前端支持 `/` 命令和命令补全。
- 左侧提供题目框、代码框、测试用例框。
- 右侧提供对话框。
- 底部提供输出框和命令输入框。
- 面板支持拖动和大小调整。
- 接入上下文压缩。

推荐演进顺序：

1. 从 `oj_coach_main.py` 抽出 `OJCoachSession`，让终端和前端复用同一套状态管理。
2. 增加 FastAPI 后端接口。
3. 增加 React 前端。
4. 接入 Monaco Editor、可拖拽分栏和结构化运行结果面板。
5. 把 `ContextManager` 接入 `/ask`、`/run` 解释和 `/summary` 讲解流程。
