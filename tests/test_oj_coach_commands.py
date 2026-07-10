"""测试 OJ Coach 统一命令路由层。"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from oj_coach import OJCoachCommandRouter, OJCoachSession
from oj_coach.commands import CommandParseError, parse_command_line


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
    assert "运行结果：" in code_result.output
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
