"""用户输入的「快捷指令」解析器（TUI / WebUI 共用）。

支持两种语法（都在真正调用 LLM 之前本地拦截 / 改写）：

1. `/skills`（别名 `/list`）
       本地直接列出所有 skill 的 name + 一句话 brief，不走 LLM。

2. `@<skill-name> <你的任务>`
       先把该 skill 的 SKILL.md 全文注入到 user message 前面，
       让 Agent 一次拿到完整规范，然后正常执行任务。

设计为纯函数，方便测试与在多入口复用。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .loader import SkillLoader

# `@name` 中 name 允许的字符（与 loader 内部校验保持一致）
_AT_RE = re.compile(r"^@([A-Za-z0-9_.\-]{1,64})(?:\s+(.*))?$", re.DOTALL)


# ---------- 结果类型 ----------
@dataclass(frozen=True)
class Reply:
    """本地直接回复用户（不调用 Agent）。"""

    text: str


@dataclass(frozen=True)
class Rewrite:
    """改写后的 user message，仍需送 Agent 执行。"""

    message: str
    notice: str = ""  # 可选：给 UI 层显示一条提示


@dataclass(frozen=True)
class Passthrough:
    """原样送 Agent。"""


CommandResult = Reply | Rewrite | Passthrough


# ---------- 主入口 ----------
def preprocess(user_input: str, loader: SkillLoader | None) -> CommandResult:
    """解析用户输入，返回处理结果。

    未接入 loader（None）时，`/skills` 与 `@x` 也能给出友好提示而不会崩。
    """
    text = (user_input or "").strip()
    if not text:
        return Passthrough()

    # /skills 或 /list —— 列出全部 skill
    if _is_list_command(text):
        return Reply(_format_skill_list(loader))

    # @name [task] —— 预加载 skill 后执行
    if text.startswith("@"):
        return _handle_at_command(text, loader)

    return Passthrough()


# ---------- /skills ----------
def _is_list_command(text: str) -> bool:
    head = text.split(maxsplit=1)[0].lower()
    return head in ("/skills", "/list")


def _format_skill_list(loader: SkillLoader | None) -> str:
    if loader is None:
        return "(未启用 skills)"
    metas = loader.list_metas()
    if not metas:
        return (
            "当前没有可用的 skill。\n"
            "可以在 skills 目录下建立子目录并放入 SKILL.md，或设置环境变量 SKILLS_DIR。"
        )
    lines = ["可用 skills（用 `@<name> 你的任务` 直接调用）：", ""]
    lines.extend(f"  • {m.name}  —  {m.brief}" for m in metas)
    lines.append("")
    lines.append(f"共 {len(metas)} 个。输入 /skills 可再次查看。")
    return "\n".join(lines)


# ---------- @name ----------
def _handle_at_command(text: str, loader: SkillLoader | None) -> CommandResult:
    m = _AT_RE.match(text)
    if not m:
        return Reply("❌ 语法错误：`@` 指令格式为 `@<skill-name> <你的任务>`。")

    name, task = m.group(1), (m.group(2) or "").strip()

    if loader is None:
        return Reply("❌ 当前未启用 skills，无法使用 `@` 指令。")

    try:
        skill = loader.load(name)
    except FileNotFoundError:
        return Reply(
            f"❌ 找不到 skill: {name!r}。用 `/skills` 查看当前所有可用 skill。"
        )
    except ValueError:
        return Reply(f"❌ 非法 skill 名: {name!r}。")
    except Exception as e:  # noqa: BLE001
        return Reply(f"❌ 加载 skill 出错：{e}")

    if not task:
        # 只 @了名字没给任务：本地展示 skill 内容，让用户先看看
        return Reply(
            f"已加载 skill **{skill.meta.name}**（未提供具体任务，仅展示内容）：\n\n"
            f"---\n{skill.content}"
        )

    # 把 skill 全文作为「前置规范」拼进 user message
    rewritten = (
        f"[请按以下 skill 规范完成任务]\n"
        f"# Skill: {skill.meta.name}\n"
        f"# 目录: {skill.path}\n"
        f"# 提示: 其中引用的辅助文件可用 read_file 工具按需读取。\n"
        f"---\n"
        f"{skill.content}\n"
        f"---\n\n"
        f"[任务]\n{task}"
    )
    return Rewrite(
        message=rewritten,
        notice=f"已加载 skill: {skill.meta.name}",
    )


__all__ = [
    "CommandResult",
    "Passthrough",
    "Reply",
    "Rewrite",
    "preprocess",
]
