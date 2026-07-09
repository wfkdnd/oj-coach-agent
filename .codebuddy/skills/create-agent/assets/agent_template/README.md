# agent-app

一个基于通用底盘搭建的命令行 Agent（LLM + Tools + Loop）。

## 快速开始

### CNB 云端

在 CNB 工作区内运行时，平台会自动注入 `CNB_API_ENDPOINT` / `CNB_REPO_SLUG` / `CNB_TOKEN`，通常不需要手动创建 `.env`：

```bash
uv sync
uv run agent-app                      # 交互式 REPL
uv run agent-app --solo "你的任务"     # 单兵模式（跑完即退）
echo "你的任务" | uv run agent-app --solo
```

### 本地 / 非 CNB 环境

```bash
# 1. 安装依赖（推荐 uv，也可用 pip -e .）
uv sync            # 或：pip install -e .

# 2. 配置环境变量（仅本地 / 非 CNB 环境需要）
cp .env.example .env
# 编辑 .env，填入 BASE_URL / API_KEY / MODEL_ID

# 3. 运行
uv run agent-app                      # 交互式 REPL
uv run agent-app --solo "你的任务"     # 单兵模式（跑完即退）
echo "你的任务" | uv run agent-app --solo
```

## 架构

```
src/agent_app/
├── core.py          ★ 换场景主要改这里：APP 信息 + SYSTEM_PROMPT + 工具组装
├── agent_tools/     ★ 你的场景工具（在这里写函数并注册）
├── common_tools/    通用文件/命令工具（读写改/列目录/bash），不需要可删
├── agent.py         Agent 主循环（底盘）
├── llm.py           LLM 客户端（底盘）
├── tools.py         ToolRegistry（底盘）
├── context.py       上下文压缩（底盘）
├── memory.py        向量记忆（底盘，可选）
├── skills/          Agent 自加载 skill 子系统（底盘，可选）
├── ui.py            rich 终端 UI（底盘）
└── cli.py           CLI 入口（底盘）
```

## 换场景只改两处

1. **SYSTEM_PROMPT**：编辑 `core.py` 顶部的 `SYSTEM_PROMPT`（以及 `APP_NAME` / `APP_TAGLINE`）。
2. **工具**：在 `agent_tools/` 里写工具函数，在 `agent_tools/__init__.py` 的
   `register_agent_tools()` 里注册。写工具函数只需：普通函数 + 类型注解 + 一行 docstring。

其余模块是与场景无关的底盘，通常无需改动。
