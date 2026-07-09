"""基于 rich 的命令行界面封装（底盘 · 通常无需修改）。

把 Agent 运行过程中的事件（思考 / 工具调用 / 结果 / 压缩 / 最终回答）
渲染成美观的终端输出。与 Agent 逻辑解耦，仅通过 `on_event` 回调驱动。
"""

from __future__ import annotations

from typing import Callable, Iterable

from rich.box import MINIMAL, ROUNDED
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

# prompt_toolkit 能正确处理中文（CJK 宽字符）的光标宽度与退格删除。
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.document import Document
    from prompt_toolkit.formatted_text import HTML

    _PT_AVAILABLE = True
except ImportError:  # 环境无 prompt_toolkit 时降级为 rich.Prompt
    _PT_AVAILABLE = False


# 工具名 → (图标, 主题色)。未列出的工具走 DEFAULT_TOOL_STYLE，可按需增删。
TOOL_STYLE: dict[str, tuple[str, str]] = {
    "read_file": ("📖", "cyan"),
    "write_file": ("✍️", "green"),
    "edit_file": ("✏️", "yellow"),
    "list_dir": ("📁", "blue"),
    "bash": ("⚡", "magenta"),
}
DEFAULT_TOOL_STYLE: tuple[str, str] = ("🔧", "white")


# ---------- 快捷指令补全器（仅 prompt_toolkit 可用时启用）----------
if _PT_AVAILABLE:

    class _SlashAtCompleter(Completer):
        """补全 `/xxx` 和 `@xxx` 两种前缀，只在「当前词首字符」生效。"""

        def __init__(
            self,
            slash_commands: list[tuple[str, str]],
            skill_provider: Callable[[], Iterable[tuple[str, str]]],
        ) -> None:
            self._slash = slash_commands
            self._skills = skill_provider

        def get_completions(self, document: Document, complete_event):  # noqa: D401
            word = document.get_word_before_cursor(WORD=True)
            if not word:
                return
            head = word[0]
            if head == "/":
                for cmd, desc in self._slash:
                    if cmd.startswith(word):
                        yield Completion(
                            cmd,
                            start_position=-len(word),
                            display=cmd,
                            display_meta=desc,
                        )
            elif head == "@":
                prefix = word[1:]  # 去掉 '@'
                try:
                    items = list(self._skills())
                except Exception:
                    items = []
                for name, brief in items:
                    if name.startswith(prefix):
                        yield Completion(
                            f"@{name}",
                            start_position=-len(word),
                            display=f"@{name}",
                            display_meta=brief,
                        )
else:
    _SlashAtCompleter = None  # type: ignore[assignment]


class AgentUI:
    """封装终端渲染。用法：ui.banner() → ui.ask() → agent.run(..., on_event=ui.on_event) → ui.final()。"""

    def __init__(self) -> None:
        self.console = Console()
        self._status = None
        self._tool_seq = 0  # 本轮工具调用计数
        self._pending_call = None  # 暂存工具调用信息，与结果合并成单行
        self._session = PromptSession() if _PT_AVAILABLE else None
        self._completer = None

    # ---------- 快捷指令自动补全 ----------
    def set_completions(
        self,
        *,
        slash_commands: list[tuple[str, str]],
        skill_provider: Callable[[], Iterable[tuple[str, str]]],
    ) -> None:
        """启用 `/xxx` 与 `@name` 的 Tab / 边打边补全。无 prompt_toolkit 时静默忽略。"""
        if not _PT_AVAILABLE or self._session is None or _SlashAtCompleter is None:
            return
        self._completer = _SlashAtCompleter(slash_commands, skill_provider)

    # ---------- 欢迎 / 输入 / 结束 ----------
    def banner(
        self,
        *,
        title: str = "Agent",
        subtitle: str = "",
        model: str | None = None,
        cwd: str | None = None,
        skills: int | None = None,
    ) -> None:
        """欢迎横幅。title/subtitle 由入口从 core.APP_NAME/APP_TAGLINE 传入。"""
        info = Table.grid(padding=(0, 2))
        info.add_column(style="dim", justify="left")
        info.add_column(style="white", justify="left")
        if cwd:
            info.add_row("📂 目录", cwd)
        if model:
            info.add_row("🧠 模型", model)
        if skills is not None:
            info.add_row("🧩 Skills", f"{skills} 个" if skills > 0 else "(无)")

        body = Group(
            Text(title, style="bold cyan"),
            Text(subtitle, style="dim"),
            Text(""),
            info,
            Text(""),
            Text(
                "快捷指令：/skills 列出所有 skill · @name <任务> 用指定 skill 工作",
                style="dim",
            ),
            Text("输入你的任务，或输入 exit / quit 退出", style="dim italic"),
        )
        self.console.print(
            Panel(
                body,
                box=ROUNDED,
                border_style="cyan",
                padding=(1, 4),
                title="🤖",
                title_align="left",
            )
        )

    def ask(self) -> str:
        self.console.print()
        self._tool_seq = 0  # 新一轮对话，重置工具计数
        if self._session is not None:
            return self._session.prompt(
                HTML("<b><ansigreen>你</ansigreen></b> <ansigreen>▶</ansigreen> "),
                completer=self._completer,
                complete_while_typing=bool(self._completer),
            )
        return Prompt.ask("[bold green]你[/bold green] [green]▶[/green]")

    def goodbye(self) -> None:
        self._stop_status()
        self.console.print("\n[dim]再见 👋[/dim]")

    # ---------- 本地消息（不走 Agent）----------
    def local_reply(self, text: str) -> None:
        """展示一段本地生成的消息（如 /skills 的列表）。"""
        self._stop_status()
        self.console.print(
            Panel(
                Markdown(text or "_(空)_"),
                title="[bold]本地[/bold]",
                title_align="left",
                border_style="dim cyan",
                box=MINIMAL,
                padding=(0, 1),
            )
        )

    def notice(self, text: str) -> None:
        """轻量提示：比如「已加载 skill: xxx」。"""
        self._stop_status()
        self.console.print(f"[dim cyan]› {text}[/dim cyan]")

    # ---------- Agent 事件回调 ----------
    def on_event(self, event: str, data: dict) -> None:
        if event == "thinking_start":
            self._start_status("[cyan]思考中…[/cyan]")
        elif event == "thinking_end":
            self._stop_status()
        elif event == "compress":
            self._stop_status()
            self.console.print("[dim yellow]↺ 上下文超长，已自动压缩历史对话[/dim yellow]")
        elif event == "stream_start":
            self._stop_status()
            self._streaming = True
            self.console.print("[bold cyan]Agent[/bold cyan] ", end="")
        elif event == "stream_delta":
            piece = data.get("text") or ""
            if piece:
                self.console.print(piece, end="", highlight=False, markup=False)
        elif event == "stream_end":
            if getattr(self, "_streaming", False):
                self.console.print()  # 换行收尾
            self._streaming = False
        elif event == "assistant_text":
            if getattr(self, "_streaming", False):
                return
            self._stop_status()
            text = (data.get("text") or "").strip()
            if text:
                self.console.print(
                    Panel(Markdown(text), border_style="dim", box=MINIMAL, padding=(0, 1))
                )
        elif event == "tool_call":
            self._stop_status()
            self._render_tool_call(data.get("name", ""), data.get("args", {}) or {})
        elif event == "tool_result":
            self._render_tool_result(data.get("result", ""))

    # ---------- 最终回答 / 错误 ----------
    def final(self, text: str) -> None:
        self._stop_status()
        self.console.print(
            Panel(
                Markdown(text or "_(无内容)_"),
                title="[bold cyan]Agent[/bold cyan]",
                title_align="left",
                border_style="cyan",
                box=ROUNDED,
                padding=(1, 2),
            )
        )

    def error(self, msg: str) -> None:
        self._stop_status()
        self.console.print(
            Panel(Text(msg, style="red"), title="出错了", border_style="red", box=ROUNDED)
        )

    # ---------- 内部实现 ----------
    def _start_status(self, text: str) -> None:
        self._stop_status()
        self._status = self.console.status(text, spinner="dots")
        self._status.start()

    def _stop_status(self) -> None:
        if self._status is not None:
            self._status.stop()
            self._status = None

    def _render_tool_call(self, name: str, args: dict) -> None:
        self._tool_seq += 1
        icon, color = TOOL_STYLE.get(name, DEFAULT_TOOL_STYLE)
        if args:
            arg_str = "  ".join(
                f"[dim]{k}[/dim]=[white]{_short(v)}[/white]" for k, v in args.items()
            )
        else:
            arg_str = "[dim](无参数)[/dim]"
        self._pending_call = (
            f"[bold]#{self._tool_seq}[/bold] {icon} [bold {color}]{name}[/bold {color}]  {arg_str}"
        )

    def _render_tool_result(self, result) -> None:
        text = str(result)
        n_lines = text.count("\n") + 1 if text else 0
        head = self._pending_call or ""
        self._pending_call = None
        self.console.print(
            f"  {head}  [green]✓[/green] [dim]{n_lines} 行 / {len(text)} 字符[/dim]"
        )


def _short(value, limit: int = 60) -> str:
    """把参数值压成单行短字符串，便于在一行内展示工具调用。"""
    s = str(value).replace("\n", "⏎")
    return s if len(s) <= limit else s[:limit] + "…"
