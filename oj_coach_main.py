"""OJ Coach 专用终端入口（Rich TUI 增强版）。

这个文件只负责 CLI 交互：读取用户输入、接收多行内容、打印命令结果。
命令解释、参数校验和展示文本都放在 `OJCoachCommandRouter` 中。

第二版增强：
- 使用 Rich 库提供流式输出面板
- 运行结果表格化展示
- 状态面板美观渲染
- 命令自动补全提示
"""

from __future__ import annotations

import sys
import json

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.text import Text
from rich.markdown import Markdown
from rich import box

from oj_coach import OJCoachCommandRouter, OJCoachSession, parse_command_line
from oj_coach.commands import CommandParseError, CommandResponse, END_MARKER, EXIT_COMMANDS

console = Console()


def main() -> None:
    _configure_utf8_output()
    router = OJCoachCommandRouter(OJCoachSession())

    # 欢迎界面
    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]OJ Coach Agent[/bold cyan]  [dim]v2.0 · Rich TUI[/dim]\n\n"
            "专为 OJ 刷题设计的本地陪练工具\n\n"
            "[yellow]/help[/yellow] 查看命令  [yellow]/status[/yellow] 查看状态  [yellow]/exit[/yellow] 退出\n\n"
            "[dim]读取题目后自动分析并提取样例，代码就绪后自动运行[/dim]",
            border_style="cyan",
            title="🏆 OJ Coach",
        )
    )
    console.print()

    while True:
        try:
            raw = console.input("[bold green]oj>[/bold green] ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]已退出。[/dim]")
            return

        if not raw:
            continue
        if not raw.startswith("/"):
            console.print("[yellow]请输入以 / 开头的命令。可用 /help 查看帮助。[/yellow]")
            continue

        try:
            parsed = parse_command_line(raw)
        except CommandParseError as exc:
            console.print(f"[red]{exc}[/red]")
            continue

        if parsed.command in EXIT_COMMANDS:
            console.print("[dim]已退出。[/dim]")
            return

        try:
            input_request = router.get_input_request(parsed.command, parsed.args)
            input_text = _read_multiline(input_request.prompt) if input_request else None
            response = router.execute(parsed.command, parsed.args, input_text=input_text)
        except Exception as exc:
            console.print(f"[red]错误：命令执行失败：{exc}[/red]")
            continue

        _print_response(response)


def _print_response(response: CommandResponse) -> None:
    """使用 Rich 渲染 CommandResponse。"""

    # 打印消息
    for message in response.messages:
        if message.strip():
            console.print(f"  [dim]{message}[/dim]")

    # 打印输出（运行结果、状态等）
    if response.output:
        # 尝试检测是否为运行结果 JSON
        if response.data.get("run_result") and response.output.strip():
            _print_run_result(response)
        elif response.data.get("status"):
            _print_status_panel(response.data["status"])
        elif "复盘总结" in response.output or "LLM 讲解版复盘" in response.output:
            _print_summary(response)
        else:
            console.print(Panel(response.output.strip(), border_style="blue"))

    # 流式输出
    if response.stream is not None:
        if response.stream_title:
            console.print(f"\n[bold cyan]{response.stream_title}[/bold cyan]")
        console.print()  # 空行
        # 使用 Live 实现打字机效果
        with Live(auto_refresh=False, console=console) as live:
            accumulated = ""
            for chunk in response.stream:
                accumulated += chunk
                live.update(Text(accumulated, style="white"), refresh=True)
            # 最终渲染
            live.update(Text(accumulated, style="white"), refresh=True)
        console.print()


def _print_run_result(response: CommandResponse) -> None:
    """表格化渲染运行结果。"""
    run_result = response.data.get("run_result", "")
    llm_explanation = response.data.get("llm_explanation", "")

    # 尝试解析 run_result JSON
    try:
        result = json.loads(run_result) if isinstance(run_result, str) else run_result
    except (json.JSONDecodeError, TypeError):
        console.print(Panel(run_result.strip(), border_style="blue", title="运行结果"))
        return

    # 状态表格
    status = result.get("status", "unknown")
    status_style = {
        "accepted": "green",
        "wrong_answer": "red",
        "compile_error": "red",
        "runtime_error": "yellow",
        "time_limit_exceeded": "yellow",
        "no_expected_output": "dim",
    }.get(status, "white")

    table = Table(title="运行结果", box=box.ROUNDED, border_style="blue")
    table.add_column("项目", style="cyan", no_wrap=True)
    table.add_column("值", style="white")

    table.add_row("状态", f"[bold {status_style}]{status}[/bold {status_style}]")
    table.add_row("耗时", f"{result.get('time_ms', 0)}ms")

    if "case_count" in result:
        table.add_row(
            "通过/总数",
            f"[green]{result.get('passed_count', 0)}[/green]/"
            f"{result.get('case_count', 0)}",
        )

    # 本地说明
    status_desc = _status_explanation(status)
    if status_desc:
        table.add_row("说明", f"[dim]{status_desc}[/dim]")

    console.print(table)

    # 测试用例明细
    test_cases = result.get("test_cases")
    if test_cases and isinstance(test_cases, list):
        case_table = Table(title="测试用例明细", box=box.SIMPLE)
        case_table.add_column("#", style="dim", justify="right")
        case_table.add_column("名称")
        case_table.add_column("来源", style="dim")
        case_table.add_column("状态")
        case_table.add_column("耗时", justify="right")

        for i, tc in enumerate(test_cases, 1):
            if not isinstance(tc, dict):
                continue
            case_status = tc.get("status", "")
            case_style = {
                "accepted": "green",
                "wrong_answer": "red",
                "runtime_error": "yellow",
                "time_limit_exceeded": "yellow",
                "compile_error": "red",
            }.get(case_status, "white")

            case_table.add_row(
                str(i),
                tc.get("name", ""),
                tc.get("source", ""),
                f"[{case_style}]{case_status}[/{case_style}]",
                f"{tc.get('time_ms', 0)}ms",
            )

        console.print(case_table)

    # 编译/错误输出
    for key, title in [
        ("compile_output", "编译输出"),
        ("stderr", "标准错误"),
        ("diff_info", "差异对比"),
    ]:
        value = str(result.get(key, "")).strip()
        if value:
            console.print(
                Panel(value, border_style="yellow", title=f"[bold yellow]{title}[/bold yellow]")
            )

    # LLM 解释
    if llm_explanation:
        console.print()
        console.print(
            Panel(
                Markdown(llm_explanation.strip()),
                border_style="green",
                title="[bold green]LLM 分析[/bold green]",
            )
        )


def _print_status_panel(status: dict) -> None:
    """面板化渲染状态。"""
    table = Table(title="当前状态", box=box.ROUNDED, border_style="cyan")
    table.add_column("项目", style="cyan")
    table.add_column("状态", style="white")

    table.add_row("题目文本", _yes_no(status.get("problem_text_set", False), status.get("problem_text_chars", 0)))
    table.add_row("题目分析", _yes_no(status.get("analysis_result_set", False)))
    table.add_row("语言", status.get("language", "未设置"))
    table.add_row("代码", _yes_no(status.get("code_set", False), status.get("code_chars", 0)))
    table.add_row("测试用例", f"{_yes_no(status.get('test_cases_set', False))} ({status.get('runnable_case_count', 0)} 组可运行)")

    sources = status.get("test_case_sources", {})
    if sources:
        table.add_row("用例来源", ", ".join(f"{k}: {v}" for k, v in sources.items()))

    table.add_row("最近运行", _yes_no(status.get("last_run_result_set", False)))
    table.add_row("超时", f"{status.get('timeout_ms', 0)}ms")

    console.print(table)


def _print_summary(response: CommandResponse) -> None:
    """渲染复盘总结。"""
    rule_summary = response.data.get("rule_summary", "")
    llm_summary = response.data.get("llm_summary", "")

    if rule_summary:
        console.print(
            Panel(rule_summary.strip(), border_style="blue", title="[bold blue]规则版复盘[/bold blue]")
        )

    if llm_summary:
        console.print()
        console.print(
            Panel(
                Markdown(llm_summary.strip()),
                border_style="green",
                title="[bold green]LLM 讲解[/bold green]",
            )
        )


def _read_multiline(prompt: str) -> str:
    console.print(f"\n[dim]{prompt}[/dim]")
    console.print("[dim]（单独输入 [bold]END[/bold] 结束）[/dim]")
    lines: list[str] = []
    while True:
        try:
            line = console.input("  ")
        except (EOFError, KeyboardInterrupt):
            break
        if line.strip() == END_MARKER:
            break
        lines.append(line)
    return "\n".join(lines).replace("\r\n", "\n").replace("\r", "\n")


def _configure_utf8_output() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def _yes_no(value: bool, chars: int | None = None) -> str:
    if value:
        base = "[green]✓ 已设置[/green]"
        if chars is not None:
            base += f" ({chars} 字符)"
        return base
    return "[red]✗ 未设置[/red]"


def _status_explanation(status: str) -> str:
    if status == "accepted":
        return "输出与期望输出一致"
    if status == "wrong_answer":
        return "程序正常结束，但实际输出与期望输出不一致"
    if status == "compile_error":
        return "代码没有通过编译或语言环境不可用"
    if status == "runtime_error":
        return "程序运行时异常退出"
    if status == "time_limit_exceeded":
        return "程序超过超时限制"
    if status == "no_expected_output":
        return "程序已运行，但没有可对比的期望输出"
    return ""


if __name__ == "__main__":
    main()
