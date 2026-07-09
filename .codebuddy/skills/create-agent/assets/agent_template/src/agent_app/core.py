"""
Agent 组装核心（★ 换场景主要改这里 ★）
=========================================

把 LLM + Tools + Context + Memory + Skills 组装成一个可运行的 Agent。
CLI（cli.py）等入口都调用 build_agent()，复用同一套核心与事件协议。

换一个场景，你通常只需要动本文件里的两处：
  1. SYSTEM_PROMPT   —— 人设 / 目标 / 工作规范
  2. build_agent 里注册的工具集
       - 通用文件/命令工具：register_common_tools（不需要就注释掉）
       - 你的场景工具：在 agent_tools/ 里写好并 register

事件协议（agent.run 的 on_event 回调，(event, data)）：
    thinking_start / thinking_end        —— 思考开始 / 结束
    stream_start / stream_delta / stream_end —— 流式输出
    compress                             —— 上下文被压缩
    assistant_text  {text}               —— 工具调用前的中间思考文字
    tool_call       {name, args}         —— 一次工具调用
    tool_result     {name, result}       —— 工具返回
"""

from __future__ import annotations

import os
from pathlib import Path

from .agent import Agent
from .agent_tools import register_agent_tools
from .common_tools import register_common_tools
from .context import ContextManager
from .llm import LLMClient
from .memory import Memory
from .skills import SkillLoader, register_skill_tools
from .tools import ToolRegistry

# ============================================================
# ★ 场景信息（显示在 CLI 欢迎横幅上）
# ============================================================
APP_NAME = "my-agent"
APP_TAGLINE = "一个基于通用底盘搭建的 Agent"

# ============================================================
# ★ SYSTEM PROMPT（换场景主要改这里）
# ============================================================
SYSTEM_PROMPT = """\
# 人设
你是一个专业、可靠的助手。

# 你的能力
你可以调用工具来完成任务。

# 工作规范
- 先理解需求，不确定就先澄清或调查，不要瞎猜
- 需要外部信息 / 副作用时，主动调用合适的工具
- 每一步都向用户说清你在做什么
"""

# 默认 skills 存放路径。可通过环境变量 SKILLS_DIR 覆盖。
# 若不使用「Agent 自加载 skill」子系统，可忽略此项。
DEFAULT_SKILLS_DIR = "~/.my-agent/skills"

# 渐进式 Skills 指令模板：只暴露一句话索引到 system prompt，
# 详细内容通过 load_skill 工具在需要时才拉取。
SKILLS_PROMPT_TEMPLATE = """\

## 可用 Skills（渐进式加载）
以下是可用的领域能力包（skills）。**当前上下文只包含它们的简介**，如需详细指令：
1. 判断哪个 skill 与当前任务相关（根据下方 brief）
2. 调用 `load_skill(name="...")` 拉取该 skill 的完整工作规范
3. 按规范执行；skill 内引用的脚本/资源可用 `read_file` 按需读取

如果都不相关，忽略本节即可。

{skill_index}
"""


def build_agent(
    *,
    max_tokens: int = 100_000,
    skills_dir: str | os.PathLike[str] | None = None,
) -> Agent:
    """组装并返回一个完整的 Agent。

    Args:
        max_tokens: 上下文管理器的压缩阈值
        skills_dir: skills 根目录。默认读环境变量 SKILLS_DIR，再回退到 DEFAULT_SKILLS_DIR。
                    目录不存在时静默视为「无 skill」。
    """
    llm = LLMClient()
    context = ContextManager(llm=llm, max_tokens=max_tokens)
    mem = Memory(llm=llm)

    # ------- 工具组装（★ 换场景在这里增删）-------
    tools = ToolRegistry()
    register_common_tools(tools)   # 通用文件/命令工具；纯对话场景可注释掉这行
    register_agent_tools(tools)    # 你的场景工具（见 agent_tools/）

    # ------- Skills：渐进式加载（可选，不需要可整段删除）-------
    skills_path = Path(
        skills_dir
        or os.environ.get("SKILLS_DIR")
        or DEFAULT_SKILLS_DIR
    ).expanduser()
    loader = SkillLoader(skills_path)
    register_skill_tools(tools, loader)

    system_prompt = _compose_system_prompt(loader)

    agent = Agent(
        llm=llm,
        tools=tools,
        system_prompt=system_prompt,
        context_manager=context,
        memory=mem,
    )
    # 挂载 SkillLoader，方便 UI 层读取 skill 数量等信息
    agent.skills = loader
    return agent


def _compose_system_prompt(loader: SkillLoader) -> str:
    """把 SYSTEM_PROMPT 与 Level 1 skill 索引拼起来。

    Level 1：仅把 name + 一句话 brief 装进 system prompt，token 极省。
    """
    metas = loader.list_metas()
    if not metas:
        return SYSTEM_PROMPT
    index_lines = "\n".join(f"- **{m.name}**: {m.brief}" for m in metas)
    return SYSTEM_PROMPT + SKILLS_PROMPT_TEMPLATE.format(skill_index=index_lines)
