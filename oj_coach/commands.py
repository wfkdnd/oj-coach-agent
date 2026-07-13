"""OJ Coach 的统一命令路由层。

CLI、后续 HTTP API 和前端命令面板都应该复用这一层，避免把 `/` 命令的
参数校验、会话调用和结果展示规则分散在多个入口里。
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import shlex
from typing import Any, Iterator

from oj_coach.session import OJCoachSession


END_MARKER = "END"
EXIT_COMMANDS = {"exit", "quit"}
COMPRESSION_COMMANDS = {"压缩", "compress", "compact"}


class CommandParseError(ValueError):
    """用户输入无法解析为 `/` 命令。"""


@dataclass(frozen=True)
class ParsedCommand:
    command: str
    args: str = ""


@dataclass(frozen=True)
class CommandInputRequest:
    prompt: str


@dataclass
class CommandResponse:
    ok: bool
    messages: list[str] = field(default_factory=list)
    output: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    stream: Iterator[str] | None = None
    stream_title: str = ""


class OJCoachCommandRouter:
    """把 `/` 命令转换为 `OJCoachSession` 调用和可展示结果。"""

    def __init__(self, session: OJCoachSession):
        self.session = session

    def get_input_request(self, command: str, args: str = "") -> CommandInputRequest | None:
        command = command.strip().lower()
        if command == "paste_problem":
            return CommandInputRequest("请粘贴题目文本，单独输入 END 结束：")
        if command == "paste_code" and args.strip():
            return CommandInputRequest("请粘贴完整 OJ 代码，单独输入 END 结束：")
        if command == "set_cases":
            return CommandInputRequest(
                "请粘贴用户测试用例，支持 JSON 或“输入:/输出:”文本格式，单独输入 END 结束："
            )
        if command == "ask" and not args.strip():
            return CommandInputRequest("请粘贴你的问题，单独输入 END 结束：")
        return None

    def execute(
        self,
        command: str,
        args: str = "",
        input_text: str | None = None,
    ) -> CommandResponse:
        command = command.strip().lower()
        args = args.strip()

        if command in {"help", "h", "?"}:
            return CommandResponse(True, output=HELP_TEXT, data={"command": command})
        if command == "status":
            status = self.session.status()
            return CommandResponse(True, output=_render_status(status), data={"status": status})
        if command == "paste_problem":
            return _render_session_result(self.session.set_problem_text(input_text or ""))
        if command == "load_problem":
            path, error = _single_arg(args, "用法：/load_problem path/to/problem.md")
            if error:
                return error
            return _render_session_result(self.session.load_problem_file(path))
        if command == "analyze":
            return _render_session_result(self.session.analyze_problem(), show_analysis=True)
        if command == "paste_code":
            language = args.strip()
            if not language:
                return CommandResponse(False, output="用法：/paste_code python|cpp|java")
            return _render_session_result(self.session.set_code(input_text or "", language))
        if command == "load_code":
            path, error = _single_arg(args, "用法：/load_code path/to/main.py")
            if error:
                return error
            return _render_session_result(self.session.load_code_file(path))
        if command in {"set_stdin", "set_expected"}:
            return CommandResponse(True, output=DEPRECATED_SINGLE_CASE_TEXT)
        if command == "set_cases":
            return _render_session_result(self.session.add_cases(input_text or ""))
        if command == "set_timeout":
            return self._execute_set_timeout(args)
        if command == "run":
            return self._execute_run()
        if command == "ask":
            return self._execute_ask(args, input_text)
        if command == "summary":
            return self._execute_summary(args)
        if command in COMPRESSION_COMMANDS:
            return CommandResponse(
                False,
                output="当前 CLI 没有接入上下文压缩器。请在前端或本地 API 中使用 /压缩。",
            )
        return CommandResponse(False, output=f"未知命令：/{command}。可用 /help 查看帮助。")

    def _execute_set_timeout(self, args: str) -> CommandResponse:
        if not args:
            return CommandResponse(
                True,
                output=f"当前超时时间：{self.session.status()['timeout_ms']}ms。用法：/set_timeout 3000",
            )
        return _render_session_result(self.session.set_timeout(args))

    def _execute_run(self) -> CommandResponse:
        result = self.session.run_code()
        response = _render_session_result(result)
        llm_explanation = str(result.get("llm_explanation") or "").strip()
        if llm_explanation:
            response.output = _append_output(response.output, "--- LLM 分析 ---\n" + llm_explanation)
        return response

    def _execute_ask(self, args: str, input_text: str | None) -> CommandResponse:
        question = args.strip() or (input_text or "").strip()
        if not question:
            return CommandResponse(False, output="问题为空，已取消。")
        return CommandResponse(
            True,
            data={"question": question},
            stream=self.session.ask_stream(question),
            stream_title="回答：",
        )

    def _execute_summary(self, args: str) -> CommandResponse:
        notes = args.strip()
        result = self.session.summarize_rules(notes)
        messages = [str(message) for message in result.get("messages", [])]
        if not result.get("ok"):
            return CommandResponse(False, messages=messages, data=result)

        rule_summary = str(result.get("rule_summary") or "")
        summary_stream = self.session.explain_summary_stream(rule_summary, notes)
        if summary_stream is not None:
            return CommandResponse(
                True,
                messages=messages,
                data=result,
                stream=summary_stream,
                stream_title="复盘：",
            )

        output = "\n\n".join(
            [
                "当前未能初始化 LLM，仅展示规则版复盘。请确认 BASE_URL / API_KEY / MODEL_ID 已配置。",
                "规则版复盘总结：\n" + rule_summary,
            ]
        )
        return CommandResponse(True, messages=messages, output=output, data=result)


def parse_command_line(raw: str) -> ParsedCommand:
    text = raw.strip()
    if not text:
        raise CommandParseError("命令为空。")
    if not text.startswith("/"):
        raise CommandParseError("请输入以 / 开头的命令。可用 /help 查看帮助。")

    without_slash = text[1:]
    if not without_slash:
        return ParsedCommand("")

    command, _, args = without_slash.partition(" ")
    return ParsedCommand(command.strip().lower(), args.strip())


def _render_session_result(result: dict[str, Any], show_analysis: bool = False) -> CommandResponse:
    messages = [str(message) for message in result.get("messages", [])]
    output_parts: list[str] = []

    if show_analysis and result.get("analysis_result"):
        output_parts.append("题目分析：\n" + str(result["analysis_result"]))
    if result.get("run_result"):
        output_parts.append(_render_run_result(str(result["run_result"])))

    return CommandResponse(
        ok=bool(result.get("ok")),
        messages=messages,
        output="\n\n".join(part for part in output_parts if part),
        data=result,
    )


def _render_run_result(raw_result: str) -> str:
    try:
        result = json.loads(raw_result)
    except json.JSONDecodeError:
        return raw_result

    status = str(result.get("status", "unknown"))
    lines = [_run_result_title(status), "", "| 项目 | 结果 |", "|---|---|"]
    lines.append(f"| 状态 | `{_escape_markdown_table_cell(status)}` |")
    lines.append(f"| 耗时 | `{_escape_markdown_table_cell(str(result.get('time_ms', 0)))}ms` |")

    if "case_count" in result:
        lines.append(
            f"| 用例 | `{_escape_markdown_table_cell(str(result.get('passed_count', 0)))}/"
            f"{_escape_markdown_table_cell(str(result.get('case_count', 0)))}` 通过 |"
        )

    explanation = _local_status_explanation(result)
    if explanation:
        lines.append(f"| 说明 | {_escape_markdown_table_cell(explanation)} |")

    for key, label in (
        ("compile_output", "编译输出"),
        ("stderr", "标准错误"),
        ("stdout", "标准输出"),
        ("diff_info", "差异信息"),
    ):
        value = str(result.get(key) or "").strip()
        if value:
            lines.append("")
            lines.append(f"#### {label}")
            lines.append("")
            lines.append("```text")
            lines.append(value)
            lines.append("```")

    test_cases = result.get("test_cases")
    if test_cases:
        lines.append("")
        lines.append("#### 测试用例明细")
        lines.append("")
        lines.append("| 用例 | 来源 | 状态 |")
        lines.append("|---|---|---|")
        for index, item in enumerate(test_cases, start=1):
            if not isinstance(item, dict):
                continue
            case_name = str(item.get("name") or f"用例 {index}")
            source = str(item.get("source") or "")
            case_status = str(item.get("status") or "")
            lines.append(
                f"| {_escape_markdown_table_cell(case_name)} "
                f"| {_escape_markdown_table_cell(source)} "
                f"| {_run_status_badge(case_status)} |"
            )

    return "\n".join(lines)


def _run_result_title(status: str) -> str:
    if status == "accepted":
        return "### ✅ 运行通过"
    if status == "wrong_answer":
        return "### ❌ 答案错误"
    if status == "compile_error":
        return "### 🧱 编译失败"
    if status == "runtime_error":
        return "### 💥 运行异常"
    if status == "time_limit_exceeded":
        return "### ⏱️ 运行超时"
    if status == "no_expected_output":
        return "### ℹ️ 已运行，缺少期望输出"
    return "### 运行结果"


def _run_status_badge(status: str) -> str:
    if status == "accepted":
        return "✅ `accepted`"
    if status == "wrong_answer":
        return "❌ `wrong_answer`"
    if status == "compile_error":
        return "🧱 `compile_error`"
    if status == "runtime_error":
        return "💥 `runtime_error`"
    if status == "time_limit_exceeded":
        return "⏱️ `time_limit_exceeded`"
    if not status:
        return ""
    return f"`{_escape_markdown_table_cell(status)}`"


def _escape_markdown_table_cell(value: str) -> str:
    return str(value).replace("|", "｜").replace("\n", "<br>")


def _render_status(status: dict[str, Any]) -> str:
    lines = [
        "当前状态：",
        f"- problem_text: {_yes_no_bool(status['problem_text_set'])} ({status['problem_text_chars']} chars)",
        f"- analysis_result: {_yes_no_bool(status['analysis_result_set'])}",
        f"- language: {status['language']}",
        f"- code: {_yes_no_bool(status['code_set'])} ({status['code_chars']} chars)",
        (
            f"- test_cases: {_yes_no_bool(status['test_cases_set'])} "
            f"({status['runnable_case_count']} runnable cases)"
        ),
    ]
    if status["test_case_sources"]:
        lines.append(
            "- test_case_sources: "
            + ", ".join(f"{source}={count}" for source, count in status["test_case_sources"].items())
        )
    lines.extend(
        [
            f"- last_run_result: {_yes_no_bool(status['last_run_result_set'])}",
            f"- timeout_ms: {status['timeout_ms']}",
        ]
    )
    return "\n".join(lines)


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


def _single_arg(args: str, usage: str) -> tuple[str, CommandResponse | None]:
    parts = _split_args(args)
    if len(parts) != 1:
        return "", CommandResponse(False, output=usage)
    return parts[0], None


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


def _yes_no_bool(value: bool) -> str:
    return "已设置" if value else "未设置"


def _append_output(existing: str, addition: str) -> str:
    if not existing:
        return addition
    if not addition:
        return existing
    return existing + "\n\n" + addition


DEPRECATED_SINGLE_CASE_TEXT = """\
已统一为 /set_cases：每组用例需提供期望输出；无输入题可将输入留空。
示例格式：
输入：
1 2
输出：
3
END"""


HELP_TEXT = """\
可用命令：
  /paste_problem              粘贴题目文本，直到 END；成功后会自动分析
  /load_problem <path>        从 .txt / .md / .docx 读取题目；成功后会自动分析
  /analyze                    重新分析当前题目
  /paste_code <language>      粘贴完整 OJ 代码，language 为 python/cpp/java
  /load_code <path>           从 .py / .cpp / .java 读取代码并识别语言
  /set_cases                  添加用户测试用例，直到 END；期望输出必填，输入可为空
  /set_timeout <ms>           设置运行超时时间
  /run                        运行当前代码
  /ask                        多行输入追问，直到 END；需要 LLM 环境变量
  /summary [notes]            生成规则版复盘总结，并交给 LLM 做人话讲解
  /compress                   手动压缩当前会话上下文（兼容 /压缩、/compact）
  /status                     查看当前状态
  /exit                       退出

多行粘贴时，单独输入 END 结束。
读取或分析题目后，会优先调用 LLM 把题目样例写入统一 test_cases JSON，source=题目。
/set_cases 添加的用户用例也写入同一个 JSON，source=用户。
/run 只读取统一 test_cases JSON；如果 LLM 不可用或 JSON 不合法，会从规则分析结果补充题目样例。
如果题目样例和当前代码都就绪，会自动运行题目样例。"""
