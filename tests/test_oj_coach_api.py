"""测试 OJ Coach 本地 API 支撑层。"""

import importlib.util
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from oj_coach.api import (
    ApiCommandRequest,
    LocalSessionStore,
    create_app,
    resolve_command_request,
    serialize_command_response,
)
from oj_coach.session import OJCoachSession


PROBLEM = """## A+B
给定两个整数 a 和 b，输出它们的和。

样例输入：
1 2

样例输出：
3
"""

PYTHON_AC_CODE = "a, b = map(int, input().split())\nprint(a + b)"


def _make_store(auto_run=True):
    return LocalSessionStore(
        session_factory=lambda: OJCoachSession(llm_factory=lambda: None, auto_run=auto_run)
    )


def test_resolve_command_request_supports_raw_and_split_form():
    assert resolve_command_request(ApiCommandRequest(raw="/run")) == ("run", "")
    assert resolve_command_request(ApiCommandRequest(command="/set_timeout", args="2000")) == (
        "set_timeout",
        "2000",
    )
    assert resolve_command_request(ApiCommandRequest(command="status")) == ("status", "")


def test_store_creates_session_and_executes_status_command():
    store = _make_store()
    session_info = store.create_session()

    response = store.execute_command(
        session_info["session_id"],
        ApiCommandRequest(command="status"),
    )

    assert response.ok is True
    assert "timeout_ms" in response.output
    assert store.describe_session(session_info["session_id"])["event_count"] == 2


def test_store_executes_problem_code_and_run_commands():
    store = _make_store(auto_run=False)
    session_id = store.create_session()["session_id"]

    problem_response = store.execute_command(
        session_id,
        ApiCommandRequest(command="paste_problem", input_text=PROBLEM),
    )
    code_response = store.execute_command(
        session_id,
        ApiCommandRequest(command="paste_code", args="python", input_text=PYTHON_AC_CODE),
    )
    run_response = store.execute_command(session_id, ApiCommandRequest(raw="/run"))

    assert problem_response.ok is True
    assert code_response.ok is True
    assert run_response.ok is True
    assert "accepted" in run_response.output


def test_event_log_does_not_store_full_input_text():
    store = _make_store(auto_run=False)
    session_id = store.create_session()["session_id"]

    store.execute_command(
        session_id,
        ApiCommandRequest(command="paste_code", args="python", input_text=PYTHON_AC_CODE),
    )
    events_text = str(store.recent_events(session_id, limit=10))

    assert "input_chars" in events_text
    assert PYTHON_AC_CODE not in events_text


def test_stream_response_is_serialized_without_generator_object():
    store = _make_store()
    session_id = store.create_session()["session_id"]

    response = store.execute_command(session_id, ApiCommandRequest(command="ask", args="这题怎么想"))
    serialized = serialize_command_response(response)

    assert serialized["has_stream"] is True
    assert "stream" not in serialized
    assert "当前未能初始化 LLM" in "".join(response.stream)


def test_create_app_reports_missing_dependency_or_builds_app():
    if importlib.util.find_spec("fastapi") is None:
        try:
            create_app(_make_store())
        except RuntimeError as exc:
            assert "fastapi" in str(exc).lower()
        else:
            raise AssertionError("缺少 FastAPI 时 create_app 应该给出明确错误")
    else:
        app = create_app(_make_store())
        assert app.title == "OJ Coach Local API"
