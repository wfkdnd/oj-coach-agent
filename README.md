# OJ Coach Agent

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white)![Rich CLI](https://img.shields.io/badge/Rich-CLI-8A2BE2)![Vanilla JS](https://img.shields.io/badge/Frontend-Vanilla%20JS-F7DF1E?logo=javascript&logoColor=black)![CodeMirror](https://img.shields.io/badge/Editor-CodeMirror-1F6FEB)![uv](https://img.shields.io/badge/uv-managed-654FF0)![pytest](https://img.shields.io/badge/tests-pytest-0A9EDC?logo=pytest&logoColor=white)![Local First](https://img.shields.io/badge/runtime-local%20first-2E8B57)

OJ Coach Agent 是一个本地算法刷题陪练工作台，覆盖从读题、分析、写代码、管理测试用例、运行判题、定位错误到复盘总结的完整练习流程。

当前 README 描述的是第二版当前实现，而不是开发计划。推荐入口是 WebUI；CLI 仍保留为轻量终端入口。

> 【风险提示】
> 本项目会在本机执行用户提供的 OJ 代码。当前实现使用临时目录、运行超时、输出截断和 `shell=False` 降低风险，但这不是完整沙箱。请只运行可信代码，不要把服务暴露到公网，也不要在题目或代码中放入密钥、Token、私钥等敏感信息。

## 当前能力

### WebUI 工作台

入口：`server.py` + `static/`

已实现：

- FastAPI 后端服务，根路径 `/` 直接提供静态前端。
- 原生 HTML/CSS/JavaScript 前端，无构建步骤。
- CodeMirror 代码/题目编辑器，支持 Python、C++、Java 语法高亮；CDN 不可用时回退到原生 textarea。
- 左侧题目、代码、测试用例标签页，右侧对话区，底部命令输入框。
- 左右工作区可拖动调整宽度。
- 题目和用例可以拖出为浮动面板，并支持拖动、缩放、放回。
- 题目/代码文件上传和拖拽加载，读取成功后会复用提交链路自动同步到当前会话。
- 题目 Markdown 预览。
- 题目、代码编辑器锁定/解锁。
- 测试用例卡片化编辑，题目用例受保护，用户用例可同步增删改。
- 长测试用例和长运行输出自动折叠。
- `/` 命令候选、命令历史、普通问题自动转 `/ask`。
- `/ask` 和 `/summary` 支持 SSE 流式输出。
- SSE 断线重连和 `stream_id` 级结果缓存，避免重连串到旧回答。
- LLM 配置状态检查；前端只显示 API Key 是否已配置，不会返回真实密钥。
- 多会话创建、切换和状态刷新。
- 连接状态检测、重连按钮。
- 明暗主题切换。
- 阶段 6/7 阅读日志抽屉：查看事件、上下文压缩状态和快照。
- 命令历史和主题保存到浏览器 `localStorage`；完整题目和代码仍由当前后端内存会话维护。

### Rich CLI

入口：`oj_coach_main.py`

已实现：

- Rich 面板化欢迎界面。
- 命令式交互，支持非 `/` 输入自动转为 `/ask`。
- 运行结果表格化展示。
- 测试用例明细表格。
- 编译输出、标准错误、差异信息分区展示。
- `/ask` 和 `/summary` 流式输出。
- 状态面板和复盘面板。

### 会话与命令层

核心模块：

- `oj_coach/session.py`
- `oj_coach/commands.py`
- `oj_coach/api.py`
- `oj_coach/context.py`

已实现：

- `OJCoachSession` 维护单次刷题状态：
  - `problem_text`
  - `analysis_result`
  - `language`
  - `code`
  - `test_cases`
  - `last_run_result`
  - `timeout_ms`
- `OJCoachCommandRouter` 统一处理 CLI、API、前端共用的 `/` 命令。
- 读取题目后自动分析，并尝试提取题目样例。
- 题目、代码、可运行测试用例都就绪时自动运行。
- `LocalSessionStore` 管理本地内存会话。
- `server.py` 通过 `create_app()` 复用统一 API 路由，并提供 30 分钟无活动会话清理。
- 事件日志默认只记录命令元信息和长度，不保存完整题目或完整代码。
- 支持手动 `/compress`、`/压缩`、`/compact` 上下文压缩。
- 支持达到阈值时在 `/ask`、`/summary` 前自动压缩。
- 压缩快照保留题目摘要、代码摘要、用例摘要、运行摘要、对话摘要和关键事实；最新代码和最新运行结果在构造 LLM 上下文时单独注入。

### OJ 工具层

核心模块：`oj_tools/`

已实现：

- 读取题目文本或本地题目文件。
- 支持题目文件：`.txt`、`.md`、`.docx`。
- 读取完整 OJ 代码。
- 支持代码文件：`.py`、`.cpp`、`.java`。
- 规则分析题目标题、题意、输入输出、约束、样例、输入类型、算法候选和学习建议。
- 规则提取题目样例为统一测试用例。
- LLM 可用时，优先用 LLM 抽取题目样例 JSON；失败则回退到规则提取。
- 支持 JSON 和“输入/输出”文本格式的用户测试用例。
- 支持 Python、C++、Java 代码运行。
- C++ 使用 `g++ -std=c++17 -O2` 编译。
- Java 使用 `javac Main.java` 编译，运行 `java Main`。
- 批量运行测试用例，返回结构化 JSON。
- 输出对比模式：
  - `strict`
  - `trailing`，默认
  - `relaxed`
  - `full_trim`
- 生成规则版复盘，并在 LLM 可用时生成讲解版复盘。

## 快速开始

### 1. 准备环境

要求：

- Python 3.10 或更高版本。
- 推荐使用 `uv` 管理依赖。
- 运行 C++ 需要本机可用 `g++`。
- 运行 Java 需要本机可用 JDK 和 `javac`。
- WebUI 的 CodeMirror/highlight.js 默认从 CDN 加载；离线环境下编辑器会降级。

安装依赖：

```bash
uv sync
```

如果本机有 `make`，也可以使用：

```bash
make install
```

### 2. 配置 LLM

LLM 是可选能力。没有配置 LLM 时，仍可使用题目规则分析、测试用例管理、代码运行、输出对比和规则版复盘。

在系统环境变量或项目根目录 `.env` 中配置：

```text
BASE_URL=你的 OpenAI-compatible API 地址
API_KEY=你的 API Key
MODEL_ID=你的模型名称
```

也支持 CNB 环境变量兜底：

```text
CNB_API_ENDPOINT=...
CNB_REPO_SLUG=...
CNB_TOKEN=...
```

`MODEL_ID` 未设置时默认使用 `glm-5.0`。Embedding 默认模型名来自 `EMBEDDING_MODEL`，未设置时为 `hunyuan-embedding`。

### 3. 启动 WebUI

推荐只监听本机地址：

```bash
uv run uvicorn server:app --host 127.0.0.1 --port 8866 --reload
```

然后打开：

```text
http://localhost:8866
```

也可以直接运行服务入口：

```bash
uv run python server.py
```

这个入口默认监听 `0.0.0.0:8866`，适合容器或云开发代理场景；本机自用时仍推荐上面的 `127.0.0.1` 命令。

如果使用 Makefile：

```bash
make web
```

注意：当前 Makefile 中 `make web` 使用 `0.0.0.0:8866`。如果电脑处在不可信网络，请优先使用上面的 `127.0.0.1` 命令。

如果已经把项目作为可编辑包安装，也可以使用 `pyproject.toml` 中声明的脚本入口：

```bash
oj-coach-web
oj-coach-cli
```

其中 `oj-coach-web` 同样默认监听 `0.0.0.0:8866`。

### 4. 启动 CLI

```bash
uv run python oj_coach_main.py
```

如果使用 Makefile：

```bash
make cli
```

## WebUI 使用流程

1. 打开 `http://localhost:8866`，页面会自动创建一个本地会话。
2. 在“题目”标签页粘贴题目，或拖入 `.txt` / `.md` / `.markdown` / `.json` / `.html` / `.htm` 文件。
3. 点击“提交”，或通过文件上传自动提交；后端会读取题目、自动分析并同步题目样例。
4. 在“代码”标签页选择语言并粘贴完整 OJ 代码，或拖入 `.py` / `.cpp` / `.cc` / `.cxx` / `.java` / `.txt` 文件。
5. 点击“提交”，或通过代码文件上传自动提交；如果题目样例已就绪，会自动运行。
6. 在“用例”标签页添加或修改用户测试用例；题目样例默认受保护，用户用例支持删除后同步。
7. 在底部输入 `/run` 运行，输入普通问题或 `/ask 问题` 继续追问。
8. 使用 `/summary` 复盘，使用 `/compress` 手动压缩当前上下文。

## CLI 命令

| 命令 | 说明 |
|---|---|
| `/help` | 查看帮助 |
| `/status` | 查看当前会话状态 |
| `/paste_problem` | 多行粘贴题目，单独输入 `END` 结束 |
| `/load_problem <path>` | 从 `.txt` / `.md` / `.docx` 读取题目 |
| `/analyze` | 重新分析当前题目 |
| `/paste_code <language>` | 多行粘贴完整 OJ 代码，语言为 `python` / `cpp` / `java` |
| `/load_code <path>` | 从 `.py` / `.cpp` / `.java` 读取代码 |
| `/set_cases` | 添加用户测试用例 |
| `/set_timeout <ms>` | 设置运行超时时间 |
| `/run` | 运行当前代码 |
| `/ask [question]` | 基于当前题目、代码和最近运行结果追问 |
| `/summary [notes]` | 生成复盘总结 |
| `/compress` | 在本地 API / WebUI 中压缩上下文 |
| `/exit` | 退出 CLI |

旧命令 `/set_stdin` 和 `/set_expected` 已废弃，统一使用 `/set_cases`。

## 测试用例格式

JSON 格式：

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

文本格式：

```text
输入：
1 2
输出：
3
END
```

多组用例可用 `---` 或 `===` 分隔：

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

无输入题可以把输入留空，但每组可运行用例必须提供期望输出。

## 运行结果状态

`run_oj_code` 返回结构化 JSON，主要字段包括：

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

常见状态：

| 状态 | 含义 |
|---|---|
| `accepted` | 实际输出与期望输出一致 |
| `wrong_answer` | 程序正常结束，但输出不一致 |
| `compile_error` | 编译失败或语言环境不可用 |
| `runtime_error` | 程序运行时异常退出 |
| `time_limit_exceeded` | 编译或运行超时 |
| `no_expected_output` | 已运行，但缺少期望输出，无法判题 |

输出展示最长保留 `20000` 字符，运行超时最大限制为 `30000ms`。

## 本地 API

推荐运行入口是 `server.py`：

```bash
uv run uvicorn server:app --host 127.0.0.1 --port 8866 --reload
```

主要接口：

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/` | WebUI 页面 |
| `GET` | `/api/status/llm` | LLM 配置状态，不返回真实 API Key |
| `POST` | `/api/sessions` | 创建会话 |
| `GET` | `/api/sessions` | 列出活跃会话 |
| `DELETE` | `/api/sessions/{session_id}` | 清理指定内存会话 |
| `GET` | `/api/sessions/{session_id}/status` | 获取会话状态 |
| `GET` | `/api/sessions/{session_id}/events` | 获取最近事件 |
| `GET` | `/api/sessions/{session_id}/context` | 获取上下文压缩状态 |
| `POST` | `/api/sessions/{session_id}/context/compress` | 手动压缩上下文 |
| `POST` | `/api/sessions/{session_id}/command` | 执行非流式命令 |
| `POST` | `/api/sessions/{session_id}/command/stream` | 通过 SSE 执行流式命令 |
| `GET` | `/api/health` | 本地 API 健康检查 |

命令请求支持原始命令：

```json
{
  "raw": "/run"
}
```

也支持结构化请求：

```json
{
  "command": "paste_code",
  "args": "python",
  "input_text": "a, b = map(int, input().split())\nprint(a + b)"
}
```

非 `/` 开头的问题会自动转为 `/ask`。

流式命令会返回 SSE 事件：

- `result`：命令元信息、`stream_id`、是否有流式内容。
- `token`：LLM 或降级回答的增量文本。
- `error`：流式过程中出现的错误。
- `done`：本次流式响应结束。

断线重连时需要带上同一个 `stream_id`：

```json
{
  "resume": true,
  "stream_id": "同一次请求的 stream_id"
}
```

如果缺少 `stream_id` 或缓存不存在，服务端会返回明确错误，而不会重新执行原命令。

## 项目结构

```text
.
├── server.py                  # 推荐 WebUI/FastAPI 入口
├── oj_coach_main.py           # Rich CLI 入口
├── oj_coach/
│   ├── api.py                 # 本地会话仓库、API 支撑层、事件日志
│   ├── commands.py            # / 命令解析和路由
│   ├── context.py             # OJ 专用上下文压缩快照
│   ├── prompts.py             # OJ Coach LLM 提示词
│   └── session.py             # OJCoachSession 状态与编排
├── oj_tools/
│   ├── analyze_problem.py     # 规则题目分析
│   ├── compare_output.py      # 输出对比
│   ├── read_code_file.py      # 代码读取
│   ├── read_problem_file.py   # 题目读取
│   ├── run_oj_code.py         # Python/C++/Java 运行器
│   └── summarize_practice.py  # 规则版复盘
├── static/
│   ├── index.html             # WebUI 页面
│   ├── style.css              # WebUI 样式
│   ├── app.js                 # 前端入口
│   └── modules/               # session/chat/ui/theme 模块
├── tests/                     # 会话、API、WebUI、工具测试
├── oj_tools_test/             # OJ 工具测试与样例数据
├── coding_tools/              # 通用 Coding Agent 工具
├── llm.py                     # OpenAI-compatible LLMClient
├── _env.py                    # 环境变量读取
├── pyproject.toml             # uv 依赖配置
└── Makefile                   # web / cli / install 快捷命令
```

## 测试

推荐执行：

```bash
uv run pytest tests oj_tools_test
```

也可以分别运行：

```bash
uv run pytest tests
uv run pytest oj_tools_test
```

C++ / Java 相关测试依赖本机已安装对应编译器或 JDK。FastAPI 相关测试依赖 `fastapi`、`uvicorn`、`sse-starlette` 等 Web 依赖。

## 当前限制

- 当前代码执行不是完整沙箱，不能运行不可信代码。
- Web/API 会话保存在内存中，服务重启后会话消失。
- 会话 30 分钟无活动会被后台任务清理。
- 不做公网部署、多用户权限和远程代码执行服务。
- 不默认持久化完整题目和完整代码。
- 不支持 JavaScript 运行。
- 不支持 LeetCode 风格 `class Solution` 自动驱动。
- C++ 依赖本机 `g++`，Java 依赖本机 JDK。
- WebUI 编辑器能力依赖 CDN；离线时会降级，语法高亮可能不可用。
- CLI/API 的 `/load_problem` 支持 `.txt`、`.md`、`.docx`；WebUI 文件上传是浏览器侧文本读取，支持的扩展名更多。
- CLI/API 的 `/load_code` 支持 `.py`、`.cpp`、`.java`；WebUI 上传还会识别 `.cc`、`.cxx`，`.txt` 保留当前语言选择。
- `main.py` 和 `coding_tools/` 仍保留通用 Coding Agent 课程示例能力，但 OJ 刷题推荐使用 `server.py` 或 `oj_coach_main.py`。

## 安全约定

- `.env` 可以放本地配置，但不要提交真实密钥。
- 后端 `/api/status/llm` 只返回 API Key 是否已配置，不返回真实值。
- 事件日志默认记录命令、输入长度、输出长度和状态，不记录完整题目或完整代码。
- 运行代码只写入临时目录，不把用户代码保存到项目目录。
- 如果未来要部署到远程服务器或开放给他人使用，必须先补充真正的沙箱、资源隔离、认证和权限控制。
