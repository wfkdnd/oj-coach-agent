"""
OJ Coach 专用终端入口。

这个文件只负责 CLI 交互：读取 `/` 命令、接收多行输入、打印结果。
刷题状态、工具调用、LLM 提示词和自动运行逻辑都放在 `OJCoachSession` 中。
"""

from __future__ import annotations

import json
import shlex
import sys
from typing import Any

from oj_coach import OJCoachSession


END_MARKER = "END"


def main() -> None:
    _configure_utf8_output()
    session = OJCoachSession()

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

        command, args = _parse_command(raw)
        if command in {"exit", "quit"}:
            print("已退出。")
            return

        try:
            _handle_command(command, args, session)
        except Exception as exc:
            print(f"错误：命令执行失败：{exc}")


def _handle_command(command: str, args: str, session: OJCoachSession) -> None:
    if command in {"help", "h", "?"}:
        _print_help()
    elif command == "status":
        _print_status(session)
    elif command == "paste_problem":
        _cmd_paste_problem(session)
    elif command == "load_problem":
        _cmd_load_problem(args, session)
    elif command == "analyze":
        _cmd_analyze(session)
    elif command == "paste_code":
        _cmd_paste_code(args, session)
    elif command == "load_code":
        _cmd_load_code(args, session)
    elif command in {"set_stdin", "set_expected"}:
        _cmd_deprecated_single_case()
    elif command == "set_cases":
        _cmd_set_cases(session)
    elif command == "set_timeout":
        _cmd_set_timeout(args, session)
    elif command == "run":
        _cmd_run(session)
    elif command == "ask":
        _cmd_ask(args, session)
    elif command == "summary":
        _cmd_summary(args, session)
    else:
        print(f"未知命令：/{command}。可用 /help 查看帮助。")


def _cmd_paste_problem(session: OJCoachSession) -> None:
    text = _read_multiline("请粘贴题目文本，单独输入 END 结束：")
    _print_session_result(session.set_problem_text(text))


def _cmd_load_problem(args: str, session: OJCoachSession) -> None:
    path = _require_single_arg(args, "用法：/load_problem path/to/problem.md")
    if not path:
        return
    _print_session_result(session.load_problem_file(path))


def _cmd_analyze(session: OJCoachSession) -> None:
    _print_session_result(session.analyze_problem(), show_analysis=True)


def _cmd_paste_code(args: str, session: OJCoachSession) -> None:
    language = args.strip()
    if not language:
        print("用法：/paste_code python|cpp|java")
        return

    code_text = _read_multiline("请粘贴完整 OJ 代码，单独输入 END 结束：")
    _print_session_result(session.set_code(code_text, language))


def _cmd_load_code(args: str, session: OJCoachSession) -> None:
    path = _require_single_arg(args, "用法：/load_code path/to/main.py")
    if not path:
        return
    _print_session_result(session.load_code_file(path))


def _cmd_deprecated_single_case() -> None:
    print("已统一为 /set_cases：请在一个用例里同时提供输入和期望输出。")
    print("示例格式：\n输入：\n1 2\n输出：\n3\nEND")


def _cmd_set_cases(session: OJCoachSession) -> None:
    raw_cases = _read_multiline(
        "请粘贴用户测试用例，支持 JSON 或“输入:/输出:”文本格式，单独输入 END 结束："
    )
    _print_session_result(session.add_cases(raw_cases))


def _cmd_set_timeout(args: str, session: OJCoachSession) -> None:
    value = args.strip()
    if not value:
        print(f"当前超时时间：{session.status()['timeout_ms']}ms。用法：/set_timeout 3000")
        return
    _print_session_result(session.set_timeout(value))


def _cmd_run(session: OJCoachSession) -> None:
    result = session.run_code()
    _print_session_result(result)
    llm_explanation = result.get("llm_explanation", "")
    if llm_explanation:
        print("\n--- LLM 分析 ---")
        print(llm_explanation)


def _cmd_ask(args: str, session: OJCoachSession) -> None:
    question = args.strip()
    if not question:
        question = _read_multiline("请粘贴你的问题，单独输入 END 结束：").strip()
    if not question:
        print("问题为空，已取消。")
        return

    print("\n回答：")
    for chunk in session.ask_stream(question):
        print(chunk, end="", flush=True)
    print()


def _cmd_summary(args: str, session: OJCoachSession) -> None:
    result = session.summarize(args.strip())
    _print_session_messages(result)
    if not result.get("ok"):
        return

    print("\n规则版复盘总结：")
    print(result.get("rule_summary", ""))

    llm_summary = result.get("llm_summary", "")
    if llm_summary:
        print("\n--- LLM 讲解版复盘 ---")
        print(llm_summary)
    else:
        print("\n当前未能初始化 LLM，仅展示规则版复盘。请确认 BASE_URL / API_KEY / MODEL_ID 已配置。")


def _print_session_result(result: dict[str, Any], show_analysis: bool = False) -> None:
    _print_session_messages(result)
    if show_analysis and result.get("analysis_result"):
        print("\n题目分析：")
        print(result["analysis_result"])
    if result.get("run_result"):
        _print_run_result(result["run_result"])


def _print_session_messages(result: dict[str, Any]) -> None:
    for message in result.get("messages", []):
        print(message)


def _print_run_result(raw_result: str) -> None:
    try:
        result = json.loads(raw_result)
    except json.JSONDecodeError:
        print(raw_result)
        return

    status = result.get("status", "unknown")
    print("\n运行结果：")
    print(f"- 状态: {status}")
    print(f"- 耗时: {result.get('time_ms', 0)}ms")

    if "case_count" in result:
        print(
            f"- 用例: {result.get('passed_count', 0)}/"
            f"{result.get('case_count', 0)} 通过"
        )

    explanation = _local_status_explanation(result)
    if explanation:
        print(f"- 说明: {explanation}")

    for key, label in (
        ("compile_output", "编译输出"),
        ("stderr", "标准错误"),
        ("stdout", "标准输出"),
        ("diff_info", "差异信息"),
    ):
        value = str(result.get(key) or "").strip()
        if value:
            print(f"\n{label}：")
            print(value)

    if result.get("test_cases"):
        print("\n测试用例明细：")
        for index, item in enumerate(result["test_cases"], start=1):
            print(
                f"{index}. {item.get('name', '')} "
                f"[{item.get('source', '')}] -> {item.get('status', '')}"
            )


def _local_status_explanation(result: dict[str, Any]) -> str:
    status = result.get("status", "")
    if status == "accepted":
        return "输出与期望输出一致。"
    if status == "wrong_answer":
        return "程序正常结束，但实际输出与期望输出不一致。"
    if status == "compile_error":
        return "代码没有通过编译或语言环境不可用。"
    if status == "runtime_error":
        return "程序运行时异常退出，请优先查看 stderr 和退出码。"
    if status == "time_limit_exceeded":
        return "程序超过超时限制，可能是死循环或复杂度过高。"
    if status == "no_expected_output":
        return "程序已运行，但没有可对比的期望输出。"
    return ""


def _print_status(session: OJCoachSession) -> None:
    status = session.status()
    print("当前状态：")
    print(f"- problem_text: {_yes_no_bool(status['problem_text_set'])} ({status['problem_text_chars']} chars)")
    print(f"- analysis_result: {_yes_no_bool(status['analysis_result_set'])}")
    print(f"- language: {status['language']}")
    print(f"- code: {_yes_no_bool(status['code_set'])} ({status['code_chars']} chars)")
    print(
        f"- test_cases: {_yes_no_bool(status['test_cases_set'])} "
        f"({status['runnable_case_count']} runnable cases)"
    )
    if status["test_case_sources"]:
        print(
            "- test_case_sources: "
            + ", ".join(f"{source}={count}" for source, count in status["test_case_sources"].items())
        )
    print(f"- last_run_result: {_yes_no_bool(status['last_run_result_set'])}")
    print(f"- timeout_ms: {status['timeout_ms']}")


def _print_help() -> None:
    print(
        """
可用命令：
  /paste_problem              粘贴题目文本，直到 END；成功后会自动分析
  /load_problem <path>        从 .txt / .md / .docx 读取题目；成功后会自动分析
  /analyze                    重新分析当前题目
  /paste_code <language>      粘贴完整 OJ 代码，language 为 python/cpp/java
  /load_code <path>           从 .py / .cpp / .java 读取代码并识别语言
  /set_cases                  添加用户测试用例，直到 END；每组用例需同时包含输入和输出
  /set_timeout <ms>           设置运行超时时间
  /run                        运行当前代码
  /ask                        多行输入追问，直到 END；需要 LLM 环境变量
  /summary [notes]            生成规则版复盘总结，并交给 LLM 做人话讲解
  /status                     查看当前状态
  /exit                       退出

多行粘贴时，单独输入 END 结束。
读取或分析题目后，会优先调用 LLM 把题目样例写入统一 test_cases JSON，source=题目。
/set_cases 添加的用户用例也写入同一个 JSON，source=用户。
/run 只读取统一 test_cases JSON；如果 LLM 不可用或 JSON 不合法，会从规则分析结果补充题目样例。
如果题目样例和当前代码都就绪，会自动运行题目样例。
""".strip()
    )


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


def _parse_command(raw: str) -> tuple[str, str]:
    without_slash = raw[1:]
    if not without_slash:
        return "", ""
    command, _, args = without_slash.partition(" ")
    return command.strip().lower(), args.strip()


def _require_single_arg(args: str, usage: str) -> str:
    parts = _split_args(args)
    if len(parts) != 1:
        print(usage)
        return ""
    return parts[0]


def _split_args(args: str) -> list[str]:
    if not args.strip():
        return []

    lexer = shlex.shlex(args, posix=False)
    lexer.whitespace_split = True
    lexer.commenters = ""
    return [_strip_quotes(part) for part in lexer]


def _strip_quotes(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {"'", '"'}:
        return stripped[1:-1]
    return stripped


def _configure_utf8_output() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def _yes_no_bool(value: bool) -> str:
    return "已设置" if value else "未设置"


if __name__ == "__main__":
    main()
