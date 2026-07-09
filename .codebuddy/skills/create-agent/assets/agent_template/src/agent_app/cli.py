"""
TUI 入口（底盘 · 通常无需修改）
================================

命令行交互界面。复用 core.build_agent() 组装 Agent，
用 ui.AgentUI（rich）消费 Agent 运行事件。

支持两个本地快捷指令（在送入 LLM 前拦截 / 改写）：
    /skills            列出所有 skill（不消耗 tokens）
    @name <task>       预加载指定 skill 后再让 Agent 执行任务

运行模式：
    交互式 REPL（默认）：
        agent-app
    单兵模式（--solo）：执行一个任务后直接退出，适合脚本 / 管道：
        agent-app --solo "你的任务"
        echo "你的任务" | agent-app --solo

也可以：python -m agent_app
"""

from __future__ import annotations

import argparse
import os
import sys

from .core import APP_NAME, APP_TAGLINE, build_agent
from .skills import Reply, Rewrite, preprocess
from .ui import AgentUI


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description=APP_TAGLINE,
    )
    parser.add_argument(
        "-s",
        "--solo",
        action="store_true",
        help='单兵模式：执行一个任务后直接退出（非交互）。'
        '任务可作为参数传入，或从标准输入读取。',
    )
    parser.add_argument(
        "task",
        nargs="*",
        help="（solo 模式下）任务描述，可用引号包裹为一句话",
    )
    return parser


def _run_task(ui: AgentUI, agent, loader, user_input: str) -> None:
    """处理单条输入：先过本地快捷指令，再交给 Agent 执行。"""
    parsed = preprocess(user_input, loader)
    if isinstance(parsed, Reply):
        ui.local_reply(parsed.text)
        return
    if isinstance(parsed, Rewrite):
        if parsed.notice:
            ui.notice(parsed.notice)
        message = parsed.message
    else:
        message = user_input
    result = agent.run(message, max_iterations=100, on_event=ui.on_event)
    ui.final(result)


def _run_solo(ui: AgentUI, agent, loader, task: str) -> None:
    """单兵模式：执行一个任务后退出。"""
    ui.notice(f"单兵模式 · {agent.llm.model}")
    try:
        _run_task(ui, agent, loader, task)
    except Exception as e:  # noqa: BLE001
        ui.error(str(e))
        raise SystemExit(1)


def _run_repl(ui: AgentUI, agent, loader) -> None:
    """交互式 REPL：循环读取输入，直到用户退出。"""
    skills_count = len(loader.list_metas()) if loader is not None else 0
    ui.banner(
        title=APP_NAME,
        subtitle=APP_TAGLINE,
        model=agent.llm.model,
        cwd=os.getcwd(),
        skills=skills_count,
    )

    while True:
        try:
            user_input = ui.ask().strip()
        except (KeyboardInterrupt, EOFError):
            break

        if not user_input or user_input.lower() in ("exit", "quit", "/exit", "/quit"):
            break

        try:
            _run_task(ui, agent, loader, user_input)
        except Exception as e:  # noqa: BLE001
            ui.error(str(e))

    ui.goodbye()


def main(argv: list[str] | None = None) -> None:
    args = _build_arg_parser().parse_args(argv)

    ui = AgentUI()

    # 组装 Agent
    agent = build_agent(max_tokens=100_000)
    loader = getattr(agent, "skills", None)

    # ---------- 单兵模式：跑完即退，不进入 REPL ----------
    if args.solo:
        task = " ".join(args.task).strip()
        # 未在命令行给出任务时，尝试从标准输入（管道）读取
        if not task and not sys.stdin.isatty():
            task = sys.stdin.read().strip()
        if not task:
            ui.error('单兵模式需要一个任务，例如：agent-app --solo "你的任务"')
            raise SystemExit(2)
        _run_solo(ui, agent, loader, task)
        return

    # ---------- 交互式 REPL（默认）----------
    ui.set_completions(
        slash_commands=[
            ("/skills", "列出所有 skill"),
            ("/list", "列出所有 skill（别名）"),
            ("/exit", "退出"),
            ("/quit", "退出"),
        ],
        skill_provider=(
            (lambda: [(m.name, m.brief) for m in loader.list_metas()])
            if loader is not None
            else (lambda: [])
        ),
    )

    _run_repl(ui, agent, loader)


if __name__ == "__main__":
    main()
