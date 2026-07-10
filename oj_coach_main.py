"""OJ Coach 专用终端入口。

这个文件只负责 CLI 交互：读取用户输入、接收多行内容、打印命令结果。
命令解释、参数校验和展示文本都放在 `OJCoachCommandRouter` 中。
"""

from __future__ import annotations

import sys

from oj_coach import OJCoachCommandRouter, OJCoachSession, parse_command_line
from oj_coach.commands import CommandParseError, CommandResponse, END_MARKER, EXIT_COMMANDS


def main() -> None:
    _configure_utf8_output()
    router = OJCoachCommandRouter(OJCoachSession())

    print("OJ Coach Agent")
    print("=" * 50)
    print("输入 /help 查看命令，输入 /exit 退出。")
    print("读取题目后会自动分析，并尝试用 LLM 提取样例 JSON。")
    print("题目样例和代码都就绪时会自动运行。")
    print("安全提示：/run 会执行当前代码，请只运行可信代码。")

    while True:
        try:
            raw = input("\noj> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n已退出。")
            return

        if not raw:
            continue
        if not raw.startswith("/"):
            print("请输入以 / 开头的命令。可用 /help 查看帮助。")
            continue

        try:
            parsed = parse_command_line(raw)
        except CommandParseError as exc:
            print(str(exc))
            continue

        if parsed.command in EXIT_COMMANDS:
            print("已退出。")
            return

        try:
            input_request = router.get_input_request(parsed.command, parsed.args)
            input_text = _read_multiline(input_request.prompt) if input_request else None
            response = router.execute(parsed.command, parsed.args, input_text=input_text)
        except Exception as exc:
            print(f"错误：命令执行失败：{exc}")
            continue

        _print_response(response)


def _print_response(response: CommandResponse) -> None:
    for message in response.messages:
        print(message)
    if response.output:
        print(response.output)
    if response.stream is not None:
        if response.stream_title:
            print(f"\n{response.stream_title}")
        for chunk in response.stream:
            print(chunk, end="", flush=True)
        print()


def _read_multiline(prompt: str) -> str:
    print(prompt)
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
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


if __name__ == "__main__":
    main()
