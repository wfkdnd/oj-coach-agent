---
name: create-agent
description: 基于一套可复用的底盘（LLM 客户端 + 工具注册表 + agent 主循环 + 上下文压缩 + 记忆 + 渐进式技能加载 + rich 终端 UI）脚手架式地生成一个全新的命令行 LLM agent。当用户想要为某个具体场景构建/创建一个新的 agent、聊天机器人或 CLI 助手时使用（例如「帮我做一个客服 agent」/「create an agent that ...」/「基于纯牛码底盘做一个新场景的 agent」）。该底盘与场景无关；换场景时只需修改 SYSTEM PROMPT 和注册的 tools。
---

# Create Agent（创建 Agent）

## 概述

本 skill 基于一套久经打磨、与场景无关的底盘，脚手架式地生成一个可直接运行的命令行 LLM agent。底盘（LLM 客户端、可自动生成 schema 的工具注册表、agent 的「思考→调工具→循环」主循环、上下文压缩、向量记忆、渐进式技能加载子系统，以及 rich 终端 UI）都打包在 `assets/agent_template/` 下。为一个新场景构建 agent 时，只需改动两处：**SYSTEM PROMPT** 和**注册的工具**。

## 何时使用

当用户想为某个领域或场景创建新的 agent / 聊天机器人 / CLI 助手时使用，尤其是当他们只需定义人设/目标（system prompt）和一组能力（工具）时。

## 核心思路：每个场景只需改两处

1. **SYSTEM PROMPT** —— 人设、目标、工作规则。位于 `core.py` 中的 `SYSTEM_PROMPT`（以及用于横幅的 `APP_NAME` / `APP_TAGLINE`）。
2. **注册的工具** —— 场景所需的能力。位于 `agent_tools/`；每个工具就是一个普通函数（带类型标注的参数 + 一行 docstring），在 `agent_tools/__init__.py` 中注册。

其余部分都是可复用底盘，通常保持不动。

## 工作流

### 第 1 步：交互式澄清需求（选择题）

**【强制 · 不可跳过】在脚手架生成之前，无论用户的初始需求看起来多么清晰，都必须先调用 `ask_followup_question` 工具完成至少一轮交互式选择题，等用户作答后才能进入第 2 步。** 严禁基于「需求已明确」或「想尽快生成」为由，跳过提问、直接用默认值脚手架。对于用户在初始需求中已经明确说清的项，可以不再重复发问，但只要还有任何一项（运行模式、工具能力、通用工具/记忆/技能开关、命名等）未明确，就必须通过 `ask_followup_question` 询问。**优先使用选择题（单选/多选）**，让用户以最低成本做决定；仅在选择题无法覆盖时（如命名）才用开放式提问。

请使用结构化的多选问答一次性抛出下列问题（能合并就合并成一组），已明确的项可跳过：

1. **应用场景 / 领域**（单选，附「其他」）
   - 客服 / 问答助手
   - 代码审查 / 编程助手
   - 数据查询 / 分析
   - 内容创作 / 文案
   - 运维 / 自动化脚本
   - 其他（请补充说明）

2. **运行模式**（单选）
   - 交互式对话（REPL）
   - 单次任务执行（`--solo`）
   - 两者都要

3. **需要哪些工具能力**（多选）
   - 读写本地文件
   - 执行 shell 命令
   - 发起网络请求 / 调用外部 API
   - 查询数据库
   - 纯对话，暂不需要工具

4. **是否启用通用文件/命令工具**（单选）—— 即内置的 `read_file` / `write_file` / `edit_file` / `list_dir` / `bash`
   - 需要（保留 `register_common_tools`）
   - 不需要（纯对话或自定义工具，移除之）

5. **是否启用向量记忆（memory）**（单选）
   - 启用（跨轮次记住信息）
   - 不启用

6. **是否启用渐进式技能加载（skills 子系统）**（单选）
   - 启用（agent 运行时可加载领域技能包）
   - 不启用

7. **项目命名与位置**（开放式，可给默认值）—— 目标目录、Python 包名、命令名；用户未指定时选取合理默认值并说明假设。

将以上答案映射为后续步骤的输入：

- **场景 + 运行模式** → SYSTEM PROMPT（人设 + 目标 + 规则）与 CLI 说明。
- **工具能力 + 通用工具开关** → `agent_tools/` 与 `build_agent()` 中 `register_common_tools()` 的保留/移除。对每个自定义工具进一步明确：名称、用途、参数。
- **memory / skills 开关** → 保留或移除 `core.py` 中相应引用及对应模块。
- **命名与位置** → 脚手架脚本的 `--dest` / `--package` / `--command`。

> 重要：本步骤为强制环节。即使用户说「你看着办」「随便」「尽快生成」，也必须先用 `ask_followup_question` 抛出选择题（可在选项中提供「全部用推荐默认值」这一项让用户一键确认），拿到用户的选择后再进入第 2 步。不得在未调用 `ask_followup_question` 的情况下直接开始脚手架。

### 第 2 步：脚手架生成项目

运行内置脚本复制模板并重命名包名/命令名。请勿手动逐个复制文件。

```bash
python3 <skill_dir>/scripts/scaffold.py --dest <target_dir> --package <py_pkg_name> [--command <cli_name>]
```

- `<py_pkg_name>` 必须是合法的 Python 标识符（例如 `support_bot`）。
- `--command` 默认取包名并把下划线替换为连字符。
- 若目标目录非空，脚本会拒绝写入。

示例：

```bash
python3 <skill_dir>/scripts/scaffold.py --dest ./support-bot --package support_bot --command support-bot
```

### 第 3 步：定制 SYSTEM PROMPT

编辑 `src/<package>/core.py`：

- 设置 `APP_NAME` 和 `APP_TAGLINE`（显示在 CLI 横幅上）。
- 重写 `SYSTEM_PROMPT`，为该场景定义 agent 的人设、目标和工作规则。保持工具调用行为的确定性（人设不应破坏正确的工具使用）。

### 第 4 步：实现并注册工具

对场景所需的每项能力：

1. 在 `src/<package>/agent_tools/` 中创建一个函数（一个工具一个文件，或将相关工具分组）。遵循工具编写约定：
   - 普通函数，每个参数都有类型标注（`str`/`int`/`float`/`bool`）。
   - docstring 的第一行会成为工具描述 —— 清楚说明它**做什么**以及**何时使用**。
   - 没有默认值的参数被视为必填。
   - 返回值会被字符串化后回喂给模型。
2. 在 `src/<package>/agent_tools/__init__.py` 的 `register_agent_tools()` 中注册它。
3. 一旦有了真实工具，删除示例 `example_tool.py` 及其注册。

如需包含或排除通用文件/命令工具，在 `core.py` 的 `build_agent()` 中保留或注释掉 `register_common_tools(tools)`。对于纯对话型 agent，可直接移除。

### 第 5 步：配置并运行

```bash
cd <target_dir>
uv sync                   # 或：pip install -e .
uv run <cli_name>                    # 交互式 REPL
uv run <cli_name> --solo "任务"       # 单次执行模式
```

底盘的 `llm.py` 会自动读取 LLM 配置，优先级如下：

1. **CNB 云端环境**：自动使用注入的 `CNB_API_ENDPOINT` / `CNB_REPO_SLUG` / `CNB_TOKEN`，**无需任何手动配置即可直接运行**。
2. **本地/非 CNB 环境**：才需要 `cp .env.example .env` 并填写 `BASE_URL` / `API_KEY` / `MODEL_ID`。

因此在 CNB 内运行时不要求用户配置 `.env`。仅当用户明确在本地且未配置 CNB 变量时，才提示其复制 `.env.example` 并填值（不清楚端点则保留占位符让用户自行填写）。

## 模板结构（供参考）

```
assets/agent_template/
├── pyproject.toml            # 依赖 + [project.scripts] 入口
├── .env.example              # BASE_URL / API_KEY / MODEL_ID
├── README.md
└── src/agent_app/
    ├── core.py               # ★ SYSTEM_PROMPT + APP 信息 + 工具组装
    ├── agent_tools/          # ★ 场景工具（在此编写并注册）
    ├── common_tools/         # 通用 read/write/edit/list_dir/bash（可选）
    ├── agent.py              # 底盘：思考→调工具→循环
    ├── llm.py                # 底盘：OpenAI 兼容客户端（流式）
    ├── tools.py              # 底盘：ToolRegistry（自动生成 schema）
    ├── context.py            # 底盘：上下文压缩
    ├── memory.py             # 底盘：向量记忆（可选）
    ├── skills/               # 底盘：渐进式技能加载（可选）
    ├── ui.py                 # 底盘：rich 终端 UI
    ├── cli.py                # 底盘：REPL + --solo 入口
    └── __main__.py           # python -m <package>
```

## 注意事项

- 包内所有导入均为相对导入，因此重命名包名（由脚手架脚本完成）不会破坏 import。
- 底盘使用 OpenAI 兼容的流式 API，且仅从环境变量读取配置（切勿硬编码密钥）。
- 可选的 `skills/` 子系统让生成的 agent 自身能在运行时加载领域技能包；若不需要，可移除它及 `core.py` 中的相关引用。
