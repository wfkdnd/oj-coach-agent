"""
OJ Coach 专用终端入口。

这个入口与通用 main.py 分开：它不让模型自由选择工具，而是用明确的
`/` 命令维护刷题状态，再把状态交给 oj_tools 中的确定性工具处理。
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import shlex
import sys
from typing import Any

from oj_tools import build_oj_tools


END_MARKER = "END"
DEFAULT_TIMEOUT_MS = 3000
MAX_CONTEXT_CHARS = 6000

OJ_COACH_SYSTEM_PROMPT = """\
你是算法刷题陪练 Agent。

你的目标不是直接给最终答案，而是陪用户完成：
读题 -> 写代码 -> 运行 -> 定位错误 -> 修正 -> 复盘。

回答规范：
- 优先基于当前题目、代码、输入、期望输出和最近一次真实运行结果回答。
- 不要捏造运行结果；只有上下文里已有 run_oj_code 的结果时，才能称为运行结果。
- 对编译错误、运行错误、Wrong Answer、TLE 要翻译成人话。
- 默认先给方向、关键观察和定位建议；用户明确要求完整代码时再给完整代码。
- 不保存用户完整代码或敏感信息。
"""


@dataclass
class OJCoachState:
    problem_text: str = ""
    language: str = ""
    code: str = ""
    stdin: str = ""
    expected_output: str = ""
    test_cases: str = ""
    last_run_result: str = ""
    analysis_result: str = ""
    timeout_ms: int = DEFAULT_TIMEOUT_MS


def main() -> None:
    _configure_utf8_output()
    state = OJCoachState()
    tools = build_oj_tools()

    print("OJ Coach Agent")
    print("=" * 50)
    print("输入 /help 查看命令，输入 /exit 退出。")
    print("读取题目后会自动分析；题目样例和代码都就绪时会自动运行。")
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
            _handle_command(command, args, state, tools)
        except Exception as exc:
            print(f"错误：命令执行失败：{exc}")


def _handle_command(command: str, args: str, state: OJCoachState, tools: Any) -> None:
    if command in {"help", "h", "?"}:
        _print_help()
    elif command == "status":
        _print_status(state)
    elif command == "paste_problem":
        _cmd_paste_problem(state, tools)
    elif command == "load_problem":
        _cmd_load_problem(args, state, tools)
    elif command == "analyze":
        _cmd_analyze(state, tools)
    elif command == "paste_code":
        _cmd_paste_code(args, state, tools)
    elif command == "load_code":
        _cmd_load_code(args, state, tools)
    elif command == "set_stdin":
        _cmd_set_stdin(state)
    elif command == "set_expected":
        _cmd_set_expected(state)
    elif command == "set_cases":
        _cmd_set_cases(state)
    elif command == "set_timeout":
        _cmd_set_timeout(args, state)
    elif command == "run":
        _cmd_run(state, tools)
    elif command == "ask":
        _cmd_ask(args, state)
    elif command == "summary":
        _cmd_summary(args, state, tools)
    else:
        print(f"未知命令：/{command}。可用 /help 查看帮助。")


def _cmd_paste_problem(state: OJCoachState, tools: Any) -> None:
    text = _read_multiline("请粘贴题目文本，单独输入 END 结束：")
    result = _invoke_oj_tool(tools, "read_problem", {"problem_text": text})
    if _looks_like_error(result):
        print(result)
        return

    state.problem_text = result
    state.analysis_result = ""
    print(f"已读取题目文本，共 {len(state.problem_text)} 个字符。")
    _auto_analyze_problem(state, tools)
    _maybe_auto_run_problem_samples(state, tools, "题目已更新")


def _cmd_load_problem(args: str, state: OJCoachState, tools: Any) -> None:
    path = _require_single_arg(args, "用法：/load_problem path/to/problem.md")
    if not path:
        return

    result = _invoke_oj_tool(tools, "read_problem_file", {"file_path": path})
    if _looks_like_error(result):
        print(result)
        return

    state.problem_text = result
    state.analysis_result = ""
    print(f"已读取题目文件，共 {len(state.problem_text)} 个字符。")
    _auto_analyze_problem(state, tools)
    _maybe_auto_run_problem_samples(state, tools, "题目已更新")


def _cmd_analyze(state: OJCoachState, tools: Any) -> None:
    if not state.problem_text.strip():
        print("请先使用 /paste_problem 或 /load_problem 读取题目。")
        return

    result = _invoke_oj_tool(tools, "analyze_problem", {"problem_text": state.problem_text})
    if _looks_like_error(result):
        print(result)
        return

    state.analysis_result = result
    print("\n题目分析：")
    print(result)
    _maybe_auto_run_problem_samples(state, tools, "题目分析已更新")


def _cmd_paste_code(args: str, state: OJCoachState, tools: Any) -> None:
    language = args.strip()
    if not language:
        print("用法：/paste_code python|cpp|java")
        return

    code_text = _read_multiline("请粘贴完整 OJ 代码，单独输入 END 结束：")
    raw_result = _invoke_oj_tool(
        tools,
        "read_code",
        {"code_text": code_text, "language": language},
    )
    if _apply_code_payload(raw_result, state):
        _maybe_auto_run_problem_samples(state, tools, "代码已更新")


def _cmd_load_code(args: str, state: OJCoachState, tools: Any) -> None:
    path = _require_single_arg(args, "用法：/load_code path/to/main.py")
    if not path:
        return

    raw_result = _invoke_oj_tool(tools, "read_code_file", {"file_path": path})
    if _apply_code_payload(raw_result, state):
        _maybe_auto_run_problem_samples(state, tools, "代码已更新")


def _cmd_set_stdin(state: OJCoachState) -> None:
    state.stdin = _read_multiline("请粘贴测试输入 stdin，单独输入 END 结束：")
    print(f"已设置 stdin，共 {len(state.stdin)} 个字符。")


def _cmd_set_expected(state: OJCoachState) -> None:
    state.expected_output = _read_multiline("请粘贴期望输出，单独输入 END 结束：")
    print(f"已设置 expected_output，共 {len(state.expected_output)} 个字符。")


def _cmd_set_cases(state: OJCoachState) -> None:
    state.test_cases = _read_multiline(
        "请粘贴额外测试用例，支持 JSON 或“输入:/输出:”文本格式，单独输入 END 结束："
    )
    print(f"已设置额外测试用例文本，共 {len(state.test_cases)} 个字符。")


def _cmd_set_timeout(args: str, state: OJCoachState) -> None:
    value = args.strip()
    if not value:
        print(f"当前超时时间：{state.timeout_ms}ms。用法：/set_timeout 3000")
        return

    try:
        timeout_ms = int(value)
    except ValueError:
        print("错误：timeout_ms 必须是整数。")
        return

    if timeout_ms <= 0:
        print("错误：timeout_ms 必须大于 0。")
        return

    state.timeout_ms = timeout_ms
    print(f"已设置超时时间：{state.timeout_ms}ms。")


def _cmd_run(state: OJCoachState, tools: Any) -> None:
    if not state.code.strip():
        print("请先使用 /paste_code 或 /load_code 读取完整 OJ 代码。")
        return
    if not state.language.strip() or state.language == "未知":
        print("请先提供代码语言，例如 /paste_code python 或 /load_code main.cpp。")
        return

    print("正在运行当前代码...")
    result = _invoke_oj_tool(
        tools,
        "run_oj_code",
        {
            "language": state.language,
            "code": state.code,
            "stdin": state.stdin,
            "expected_output": state.expected_output,
            "timeout_ms": state.timeout_ms,
            "problem_text": state.problem_text,
            "test_cases": state.test_cases,
        },
    )
    state.last_run_result = result
    _print_run_result(result)

    # 自动 LLM 解释层
    llm = _try_create_llm()
    if llm is not None:
        print("\n--- LLM 分析 ---")
        _llm_explain_run(state, llm)


def _cmd_ask(args: str, state: OJCoachState) -> None:
    question = args.strip()
    if not question:
        print("用法：/ask 为什么这个用例过不了？")
        return

    llm = _try_create_llm()
    if llm is None:
        print("当前未能初始化 LLM。请确认 BASE_URL / API_KEY / MODEL_ID 已配置。")
        print("你仍然可以使用 /run 查看真实运行结果，或使用 /summary 生成规则版复盘。")
        return

    messages = [
        {"role": "system", "content": OJ_COACH_SYSTEM_PROMPT},
        {"role": "user", "content": _build_question_context(question, state)},
    ]

    print("\n回答：")
    for chunk in llm.chat_stream(messages):
        print(chunk, end="", flush=True)
    print()


def _cmd_summary(args: str, state: OJCoachState, tools: Any) -> None:
    if not state.problem_text.strip():
        print("请先使用 /paste_problem 或 /load_problem 读取题目。")
        return
    if not state.code.strip():
        print("请先使用 /paste_code 或 /load_code 读取代码。")
        return
    if not state.last_run_result.strip():
        print("请先使用 /run 运行一次代码，再做复盘。")
        return

    notes = args.strip()
    result = _invoke_oj_tool(
        tools,
        "summarize_practice",
        {
            "problem_text": state.problem_text,
            "code": state.code,
            "run_result": state.last_run_result,
            "notes": notes,
        },
    )
    print("\n规则版复盘总结：")
    print(result)

    llm = _try_create_llm()
    if llm is None:
        print("\n当前未能初始化 LLM，仅展示规则版复盘。请确认 BASE_URL / API_KEY / MODEL_ID 已配置。")
        return

    print("\n--- LLM 讲解版复盘 ---")
    _llm_explain_summary(state, result, notes, llm)


def _auto_analyze_problem(state: OJCoachState, tools: Any) -> bool:
    if not state.problem_text.strip():
        return False

    print("正在自动分析题目...")
    result = _invoke_oj_tool(tools, "analyze_problem", {"problem_text": state.problem_text})
    if _looks_like_error(result):
        print(result)
        return False

    state.analysis_result = result
    sample_count = _count_runnable_problem_cases(result)
    if sample_count:
        print(f"自动分析完成，提取到 {sample_count} 组可运行题目样例。")
    else:
        print("自动分析完成，但没有提取到可直接运行的题目样例。")
    return True


def _maybe_auto_run_problem_samples(state: OJCoachState, tools: Any, reason: str) -> bool:
    if not state.code.strip():
        return False
    if not state.language.strip() or state.language == "未知":
        return False
    if not state.problem_text.strip() or not state.analysis_result.strip():
        return False

    sample_count = _count_runnable_problem_cases(state.analysis_result)
    if sample_count <= 0:
        return False

    print(f"检测到{reason}，将自动运行 {sample_count} 组题目样例...")
    result = _invoke_oj_tool(
        tools,
        "run_oj_code",
        {
            "language": state.language,
            "code": state.code,
            "stdin": "",
            "expected_output": "",
            "timeout_ms": state.timeout_ms,
            "problem_text": state.problem_text,
            "test_cases": state.test_cases,
        },
    )
    state.last_run_result = result
    _print_run_result(result)
    return True


def _count_runnable_problem_cases(analysis_result: str) -> int:
    try:
        payload = json.loads(analysis_result)
    except json.JSONDecodeError:
        return 0

    cases = payload.get("测试用例", [])
    if not isinstance(cases, list):
        return 0

    runnable_count = 0
    for case in cases:
        if not isinstance(case, dict):
            continue
        stdin = str(case.get("stdin", "")).strip()
        expected_output = str(case.get("expected_output", "")).strip()
        if stdin and expected_output:
            runnable_count += 1
    return runnable_count


def _invoke_oj_tool(tools: Any, name: str, args: dict[str, Any]) -> str:
    return tools.invoke(name, args)


def _apply_code_payload(raw_result: str, state: OJCoachState) -> bool:
    if _looks_like_error(raw_result):
        print(raw_result)
        return False

    try:
        payload = json.loads(raw_result)
    except json.JSONDecodeError:
        print(f"错误：读取代码结果不是 JSON：{raw_result}")
        return False

    code = str(payload.get("code", ""))
    language = str(payload.get("language", ""))
    if not code.strip():
        print("错误：读取到的代码为空。")
        return False

    state.code = code
    state.language = language
    state.last_run_result = ""
    print(f"已读取 {language} 代码，共 {len(state.code)} 个字符。")
    return True


def _print_run_result(raw_result: str) -> None:
    try:
        result = json.loads(raw_result)
    except json.JSONDecodeError:
        print(raw_result)
        return

    status = result.get("status", "unknown")
    print("\n运行结果：")
    print(f"- status: {status}")
    print(f"- time_ms: {result.get('time_ms', 0)}")

    if "case_count" in result:
        print(
            f"- cases: {result.get('passed_count', 0)}/"
            f"{result.get('case_count', 0)} passed"
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


def _build_question_context(question: str, state: OJCoachState) -> str:
    return f"""\
用户问题：
{question}

当前题目：
{_clip(state.problem_text)}

题目分析：
{_clip(state.analysis_result)}

当前语言：
{state.language or "未设置"}

当前代码：
{_clip(state.code)}

当前 stdin：
{_clip(state.stdin)}

当前 expected_output：
{_clip(state.expected_output)}

额外测试用例：
{_clip(state.test_cases)}

最近一次 run_oj_code 结果：
{_clip(state.last_run_result)}
"""


def _build_run_analysis_prompt(state: OJCoachState) -> str:
    """构建用于 LLM 解释运行结果的上下文提示词。"""
    try:
        run_result = json.loads(state.last_run_result)
    except json.JSONDecodeError:
        run_result = {}
    status = run_result.get("status", "unknown")

    return f"""\
请分析以下运行结果并给出调试建议：

运行状态：{status}
运行详情：
{_clip(state.last_run_result)}

当前题目：
{_clip(state.problem_text)}

题目分析：
{_clip(state.analysis_result)}

当前语言：{state.language}

当前代码：
{_clip(state.code, limit=MAX_CONTEXT_CHARS * 2)}

当前输入（stdin）：
{_clip(state.stdin)}

期望输出：
{_clip(state.expected_output)}

请根据以上信息：
1. 如果运行出错（compile_error / runtime_error / time_limit_exceeded / wrong_answer），请具体指出错误原因和修复方向
2. 如果运行通过（accepted），可以给出代码优化建议或考察的知识点总结
3. 不要直接给出完整代码，而是引导用户自己思考和修改
"""


def _llm_explain_run(state: OJCoachState, llm) -> None:
    """使用 LLM 流式解读 /run 的运行结果。"""
    messages = [
        {"role": "system", "content": OJ_COACH_SYSTEM_PROMPT},
        {"role": "user", "content": _build_run_analysis_prompt(state)},
    ]
    try:
        for chunk in llm.chat_stream(messages):
            print(chunk, end="", flush=True)
    except Exception as exc:
        print(f"\n（LLM 解释生成失败：{exc}）")
    print()


def _build_summary_explanation_prompt(state: OJCoachState, summary_result: str, notes: str) -> str:
    return f"""\
请把下面的规则版复盘总结翻译成适合刷题者理解的自然语言讲解。

要求：
1. 先说明这题主要考察什么，以及应该抓住的关键观察。
2. 再说明当前代码和运行状态，重点解释错误原因或通过原因。
3. 如果有错误，只给定位思路和修改方向，不要直接给完整代码。
4. 最后总结下次遇到类似题时的识别信号。
5. 不要捏造运行结果；所有结论都必须来自下面的上下文。

用户备注：
{notes or "（无）"}

规则版复盘总结：
{_clip(summary_result)}

最近一次真实运行结果：
{_clip(state.last_run_result)}

题目分析：
{_clip(state.analysis_result)}

当前题目：
{_clip(state.problem_text)}

当前语言：{state.language or "未设置"}

当前代码：
{_clip(state.code, limit=MAX_CONTEXT_CHARS * 2)}
"""


def _llm_explain_summary(state: OJCoachState, summary_result: str, notes: str, llm) -> None:
    """使用 LLM 把规则版复盘总结解释成人话。"""
    messages = [
        {"role": "system", "content": OJ_COACH_SYSTEM_PROMPT},
        {"role": "user", "content": _build_summary_explanation_prompt(state, summary_result, notes)},
    ]
    try:
        for chunk in llm.chat_stream(messages):
            print(chunk, end="", flush=True)
    except Exception as exc:
        print(f"\n（LLM 复盘讲解生成失败：{exc}）")
    print()


def _print_status(state: OJCoachState) -> None:
    print("当前状态：")
    print(f"- problem_text: {_yes_no(state.problem_text)} ({len(state.problem_text)} chars)")
    print(f"- analysis_result: {_yes_no(state.analysis_result)}")
    print(f"- language: {state.language or '未设置'}")
    print(f"- code: {_yes_no(state.code)} ({len(state.code)} chars)")
    print(f"- stdin: {_yes_no(state.stdin)} ({len(state.stdin)} chars)")
    print(f"- expected_output: {_yes_no(state.expected_output)} ({len(state.expected_output)} chars)")
    print(f"- test_cases: {_yes_no(state.test_cases)} ({len(state.test_cases)} chars)")
    print(f"- last_run_result: {_yes_no(state.last_run_result)}")
    print(f"- timeout_ms: {state.timeout_ms}")


def _print_help() -> None:
    print(
        """
可用命令：
  /paste_problem              粘贴题目文本，直到 END；成功后会自动分析
  /load_problem <path>        从 .txt / .md / .docx 读取题目；成功后会自动分析
  /analyze                    重新分析当前题目
  /paste_code <language>      粘贴完整 OJ 代码，language 为 python/cpp/java
  /load_code <path>           从 .py / .cpp / .java 读取代码并识别语言
  /set_stdin                  粘贴测试输入，直到 END
  /set_expected               粘贴期望输出，直到 END
  /set_cases                  粘贴额外测试用例，直到 END
  /set_timeout <ms>           设置运行超时时间
  /run                        运行当前代码
  /ask <question>             基于当前上下文追问，需要 LLM 环境变量
  /summary [notes]            生成规则版复盘总结，并交给 LLM 做人话讲解
  /status                     查看当前状态
  /exit                       退出

多行粘贴时，单独输入 END 结束。
如果题目分析结果里提取到了可运行样例，并且当前已有代码，会自动运行题目样例。
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


def _looks_like_error(result: str) -> bool:
    stripped = result.lstrip()
    return stripped.startswith(("错误", "执行错误", "未知工具", "error", "Error", "ERROR"))


def _try_create_llm():
    try:
        from llm import LLMClient

        return LLMClient()
    except Exception:
        return None


def _clip(text: str, limit: int = MAX_CONTEXT_CHARS) -> str:
    if len(text) <= limit:
        return text or "（空）"
    return text[:limit] + f"\n...（内容过长，已截断到 {limit} 字符）"


def _yes_no(value: str) -> str:
    return "已设置" if value.strip() else "未设置"


def _configure_utf8_output() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    main()
