"""测试 OJ Coach 统一命令路由层。"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from oj_coach import OJCoachCommandRouter, OJCoachSession
from oj_coach.commands import (
    CommandParseError,
    CommandResponse,
    ParsedCommand,
    parse_command_line,
    _render_run_result,
    _render_status,
    _local_status_explanation,
    _split_args,
    _strip_quotes,
    _single_arg,
    _yes_no_bool,
    _append_output,
    _render_session_result,
    HELP_TEXT,
    DEPRECATED_SINGLE_CASE_TEXT,
)


PROBLEM = """## A+B
给定两个整数 a 和 b，输出它们的和。

样例输入：
1 2

样例输出：
3
"""

PYTHON_AC_CODE = "a, b = map(int, input().split())\nprint(a + b)"


def _make_router(auto_run=True):
    session = OJCoachSession(llm_factory=lambda: None, auto_run=auto_run)
    return OJCoachCommandRouter(session)


def test_parse_command_line_requires_slash():
    try:
        parse_command_line("status")
    except CommandParseError as exc:
        assert "/help" in str(exc)
    else:
        raise AssertionError("非 / 开头的输入应该解析失败")

    parsed = parse_command_line("/load_code \"C:\\tmp\\main.py\"")
    assert parsed.command == "load_code"
    assert parsed.args == "\"C:\\tmp\\main.py\""


def test_router_declares_multiline_inputs():
    router = _make_router()

    assert "题目文本" in router.get_input_request("paste_problem").prompt
    assert "OJ 代码" in router.get_input_request("paste_code", "python").prompt
    assert router.get_input_request("paste_code", "") is None
    assert router.get_input_request("ask", "这题怎么想") is None


def test_router_executes_problem_code_and_renders_auto_run():
    router = _make_router()

    problem_result = router.execute("paste_problem", input_text=PROBLEM)
    code_result = router.execute("paste_code", "python", input_text=PYTHON_AC_CODE)

    assert problem_result.ok is True
    assert code_result.ok is True
    assert "运行通过" in code_result.output
    assert "accepted" in code_result.output


def test_router_renders_status_and_timeout():
    router = _make_router(auto_run=False)

    timeout_result = router.execute("set_timeout", "2000")
    status_result = router.execute("status")

    assert timeout_result.ok is True
    assert any("2000ms" in message for message in timeout_result.messages)
    assert "timeout_ms: 2000" in status_result.output


def test_router_ask_returns_stream():
    router = _make_router()

    empty_result = router.execute("ask", "", input_text="")
    stream_result = router.execute("ask", "这题怎么想")

    assert empty_result.ok is False
    assert "问题为空" in empty_result.output
    assert stream_result.stream is not None
    assert "当前未能初始化 LLM" in "".join(stream_result.stream)


def test_router_summary_shows_only_llm_version_when_available():
    class FakeLLM:
        def chat(self, messages, **kwargs):
            return "这是 LLM 讲解版"

    session = OJCoachSession(llm_factory=lambda: FakeLLM(), auto_run=False)
    session.state.problem_text = PROBLEM
    session.state.language = "python"
    session.state.code = PYTHON_AC_CODE
    session.state.last_run_result = json.dumps({"status": "accepted", "time_ms": 1})
    router = OJCoachCommandRouter(session)

    result = router.execute("summary", "关注边界")

    assert result.ok is True
    assert "这是 LLM 讲解版" in result.output
    assert "规则版复盘总结" not in result.output


# ═══════════════════════════════════════════════════════════════
# parse_command_line 边界测试
# ═══════════════════════════════════════════════════════════════

def test_parse_command_line_only_slash():
    """只有 / 没有命令名。"""
    parsed = parse_command_line("/")
    assert parsed.command == ""


def test_parse_command_line_with_trailing_spaces():
    parsed = parse_command_line("/status  ")
    assert parsed.command == "status"
    assert parsed.args == ""


def test_parse_command_line_empty_string():
    try:
        parse_command_line("")
    except CommandParseError:
        pass
    else:
        raise AssertionError("空字符串应该抛异常")

def test_parse_command_line_multi_args():
    parsed = parse_command_line("/set_timeout 5000 extra")
    assert parsed.command == "set_timeout"
    assert "5000" in parsed.args


# ═══════════════════════════════════════════════════════════════
# _render_run_result — 运行结果文本渲染
# ═══════════════════════════════════════════════════════════════

def test_render_run_result_accepted():
    raw = json.dumps({
        "status": "accepted",
        "time_ms": 42,
        "case_count": 3,
        "passed_count": 3,
    })
    output = _render_run_result(raw)
    assert "运行通过" in output
    assert "| 项目 | 结果 |" in output
    assert "accepted" in output
    assert "42ms" in output
    assert "3/3" in output


def test_render_run_result_wrong_answer():
    raw = json.dumps({
        "status": "wrong_answer",
        "time_ms": 100,
        "case_count": 5,
        "passed_count": 2,
    })
    output = _render_run_result(raw)
    assert "wrong_answer" in output
    assert "2/5" in output
    assert "说明" in output


def test_render_run_result_with_compile_error():
    raw = json.dumps({
        "status": "compile_error",
        "time_ms": 0,
        "compile_output": "SyntaxError: invalid syntax",
    })
    output = _render_run_result(raw)
    assert "compile_error" in output
    assert "SyntaxError" in output
    assert "编译输出" in output
    assert "```text" in output


def test_render_run_result_with_stderr():
    raw = json.dumps({
        "status": "runtime_error",
        "time_ms": 10,
        "stderr": "IndexError at line 5",
    })
    output = _render_run_result(raw)
    assert "runtime_error" in output
    assert "IndexError" in output
    assert "标准错误" in output


def test_render_run_result_time_limit_exceeded():
    raw = json.dumps({
        "status": "time_limit_exceeded",
        "time_ms": 3100,
    })
    output = _render_run_result(raw)
    assert "time_limit_exceeded" in output


def test_render_run_result_with_test_cases():
    raw = json.dumps({
        "status": "accepted",
        "time_ms": 15,
        "test_cases": [
            {"name": "示例1", "source": "题目", "status": "accepted"},
            {"name": "用例2", "source": "用户", "status": "wrong_answer"},
        ],
    })
    output = _render_run_result(raw)
    assert "示例1" in output
    assert "accepted" in output
    assert "用例2" in output
    assert "wrong_answer" in output
    assert "测试用例明细" in output
    assert "| 用例 | 来源 | 状态 |" in output


def test_render_run_result_non_json():
    """非 JSON 文本原样返回。"""
    output = _render_run_result("某工具返回的纯文本结果")
    assert "某工具返回的纯文本结果" in output


# ═══════════════════════════════════════════════════════════════
# _render_status — 状态渲染
# ═══════════════════════════════════════════════════════════════

def test_render_status():
    status = {
        "problem_text_set": True,
        "problem_text_chars": 100,
        "analysis_result_set": False,
        "language": "python",
        "code_set": True,
        "code_chars": 50,
        "test_cases_set": True,
        "runnable_case_count": 3,
        "test_case_sources": {"题目": 1, "用户": 2},
        "last_run_result_set": True,
        "timeout_ms": 3000,
    }
    output = _render_status(status)
    assert "python" in output
    assert "3000" in output
    assert "题目=1" in output
    assert "用户=2" in output

def test_render_status_empty_cases():
    status = {
        "problem_text_set": False,
        "problem_text_chars": 0,
        "analysis_result_set": False,
        "language": "未设置",
        "code_set": False,
        "code_chars": 0,
        "test_cases_set": False,
        "runnable_case_count": 0,
        "test_case_sources": {},
        "last_run_result_set": False,
        "timeout_ms": 3000,
    }
    output = _render_status(status)
    assert "未设置" in output
    assert "0 runnable" in output


# ═══════════════════════════════════════════════════════════════
# _local_status_explanation — 状态说明
# ═══════════════════════════════════════════════════════════════

def test_local_status_explanation_all_statuses():
    explanations = {
        "accepted": "输出与期望输出一致",
        "wrong_answer": "程序正常结束",
        "compile_error": "编译",
        "runtime_error": "异常退出",
        "time_limit_exceeded": "超时",
        "no_expected_output": "期望输出",
    }
    for status, expected_text in explanations.items():
        result = _local_status_explanation({"status": status})
        assert expected_text in result, f"状态 '{status}' 的说明应该包含 '{expected_text}'，实际：{result}"

def test_local_status_explanation_unknown():
    assert _local_status_explanation({"status": "unknown_status"}) == ""
    assert _local_status_explanation({}) == ""


# ═══════════════════════════════════════════════════════════════
# _split_args & _strip_quotes — 参数解析
# ═══════════════════════════════════════════════════════════════

def test_split_args_simple():
    assert _split_args("a b c") == ["a", "b", "c"]


def test_split_args_quoted():
    result = _split_args('python "my file.py"')
    assert result == ["python", "my file.py"]


def test_split_args_single_quoted():
    result = _split_args("python 'my file.py'")
    assert result == ["python", "my file.py"]


def test_split_args_empty():
    assert _split_args("") == []
    assert _split_args("   ") == []


def test_split_args_single_arg():
    assert _split_args("python") == ["python"]


def test_strip_quotes_double():
    assert _strip_quotes('"hello"') == "hello"


def test_strip_quotes_single():
    assert _strip_quotes("'hello'") == "hello"


def test_strip_quotes_no_quotes():
    assert _strip_quotes("hello") == "hello"


def test_strip_quotes_short_string():
    """太短的不是引号字符串。"""
    assert _strip_quotes('""') == ""


# ═══════════════════════════════════════════════════════════════
# _single_arg — 单参数提取
# ═══════════════════════════════════════════════════════════════

def test_single_arg_valid():
    arg, error = _single_arg("path/to/file.py", "用法提示")
    assert arg == "path/to/file.py"
    assert error is None


def test_single_arg_empty():
    arg, error = _single_arg("", "用法提示")
    assert arg == ""
    assert error is not None
    assert "用法提示" in error.output


def test_single_arg_multiple():
    arg, error = _single_arg("a b c", "需要一个参数")
    assert arg == ""
    assert error is not None


# ═══════════════════════════════════════════════════════════════
# _yes_no_bool & _append_output — 辅助渲染
# ═══════════════════════════════════════════════════════════════

def test_yes_no_bool():
    assert _yes_no_bool(True) == "已设置"
    assert _yes_no_bool(False) == "未设置"


def test_append_output_both_non_empty():
    assert _append_output("第一段", "第二段") == "第一段\n\n第二段"


def test_append_output_first_empty():
    assert _append_output("", "第二段") == "第二段"


def test_append_output_second_empty():
    assert _append_output("第一段", "") == "第一段"


def test_append_output_both_empty():
    assert _append_output("", "") == ""


# ═══════════════════════════════════════════════════════════════
# _render_session_result — 结果渲染
# ═══════════════════════════════════════════════════════════════

def test_render_session_result_success():
    result = {
        "ok": True,
        "messages": ["已完成"],
    }
    resp = _render_session_result(result)
    assert resp.ok is True
    assert resp.messages == ["已完成"]


def test_render_session_result_with_run_result():
    result = {
        "ok": True,
        "messages": ["已运行"],
        "run_result": json.dumps({"status": "accepted", "time_ms": 10}),
    }
    resp = _render_session_result(result)
    assert "accepted" in resp.output
    assert "10ms" in resp.output


def test_render_session_result_with_analysis():
    result = {
        "ok": True,
        "messages": ["分析完成"],
        "analysis_result": '{"知识点": ["数组", "循环"]}',
    }
    resp = _render_session_result(result, show_analysis=True)
    assert "知识点" in resp.output
    assert "数组" in resp.output


def test_render_session_result_failure():
    result = {
        "ok": False,
        "messages": ["操作失败"],
    }
    resp = _render_session_result(result)
    assert resp.ok is False


# ═══════════════════════════════════════════════════════════════
# HELP_TEXT 内容验证
# ═══════════════════════════════════════════════════════════════

def test_help_text_contains_all_commands():
    expected_commands = [
        "/paste_problem",
        "/load_problem",
        "/analyze",
        "/paste_code",
        "/load_code",
        "/set_cases",
        "/set_timeout",
        "/run",
        "/ask",
        "/summary",
        "/compress",
        "/status",
        "/exit",
    ]
    for cmd in expected_commands:
        assert cmd in HELP_TEXT, f"HELP_TEXT 缺少命令 {cmd}"


def test_deprecated_text_is_informative():
    assert "已统一为" in DEPRECATED_SINGLE_CASE_TEXT
    assert "/set_cases" in DEPRECATED_SINGLE_CASE_TEXT
    assert "输入" in DEPRECATED_SINGLE_CASE_TEXT
    assert "输出" in DEPRECATED_SINGLE_CASE_TEXT


# ═══════════════════════════════════════════════════════════════
# CommandResponse / ParsedCommand dataclass
# ═══════════════════════════════════════════════════════════════

def test_command_response_defaults():
    resp = CommandResponse(ok=True)
    assert resp.messages == []
    assert resp.output == ""
    assert resp.data == {}
    assert resp.stream is None
    assert resp.stream_title == ""


def test_parsed_command_dataclass():
    pc = ParsedCommand("status", "extra")
    assert pc.command == "status"
    assert pc.args == "extra"
