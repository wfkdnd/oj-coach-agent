"""测试 OJ Coach 本地 API 支撑层。"""

import importlib.util
import json
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


def test_session_list_uses_lightweight_summaries():
    store = _make_store()
    session_id = store.create_session()["session_id"]

    sessions = store.list_sessions()

    assert sessions == [store.session_summary(session_id)]
    assert sessions[0]["title"].startswith("会话 ")
    assert "status" not in sessions[0]
    assert "context" not in sessions[0]


def test_create_session_does_not_eagerly_initialize_llm():
    llm_factory_calls = []
    store = LocalSessionStore(
        session_factory=lambda: OJCoachSession(
            llm_factory=lambda: llm_factory_calls.append("created"),
            auto_extract_with_llm=False,
            auto_run=False,
        )
    )

    store.create_session()

    assert llm_factory_calls == []


def test_store_keeps_session_workspaces_and_llm_contexts_isolated():
    store = _make_store(auto_run=False)
    first_id = store.create_session()["session_id"]
    second_id = store.create_session()["session_id"]

    store.execute_command(
        first_id,
        ApiCommandRequest(command="paste_problem", input_text=PROBLEM),
    )
    store.execute_command(
        first_id,
        ApiCommandRequest(command="paste_code", args="python", input_text=PYTHON_AC_CODE),
    )
    store.execute_command(
        second_id,
        ApiCommandRequest(command="paste_problem", input_text="# 仅输出\n输出：\nYES"),
    )
    first_answer = store.execute_command(
        first_id,
        ApiCommandRequest(command="ask", args="如何优化？"),
    )
    assert first_answer.stream is not None
    "".join(first_answer.stream)

    first_workspace = store.workspace_state(first_id)
    second_workspace = store.workspace_state(second_id)

    assert first_workspace["problem_text"] == PROBLEM.strip()
    assert first_workspace["code"] == PYTHON_AC_CODE
    assert second_workspace["problem_text"].startswith("# 仅输出")
    assert second_workspace["code"] == ""
    assert store.describe_session(first_id)["conversation_message_count"] == 2
    assert store.describe_session(second_id)["conversation_message_count"] == 0
    assert store.get_router(first_id).session is not store.get_router(second_id).session


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


def test_context_state_and_manual_compress_are_available():
    store = _make_store(auto_run=False)
    session_id = store.create_session()["session_id"]

    store.execute_command(
        session_id,
        ApiCommandRequest(command="paste_problem", input_text=PROBLEM),
    )
    context_before = store.context_state(session_id)
    context_after = store.compress_context(session_id)

    assert context_before["snapshot"]["is_empty"] is True
    assert context_after["snapshot"]["is_empty"] is False
    assert "A+B" in context_after["snapshot"]["problem_summary"]
    assert context_after["event_count"] >= context_after["snapshot"]["source_event_count"]


def test_compress_command_generates_context_snapshot():
    store = _make_store(auto_run=False)
    session_id = store.create_session()["session_id"]

    store.execute_command(
        session_id,
        ApiCommandRequest(command="paste_problem", input_text=PROBLEM),
    )
    response = store.execute_command(session_id, ApiCommandRequest(raw="/压缩"))
    context = response.data["context"]

    assert response.ok is True
    assert "已压缩" in response.messages[0]
    assert "上下文压缩完成" in response.output
    assert context["snapshot"]["is_empty"] is False
    assert "A+B" in context["snapshot"]["problem_summary"]


def test_english_compress_command_alias_generates_snapshot():
    store = _make_store(auto_run=False)
    session_id = store.create_session()["session_id"]
    store.execute_command(
        session_id,
        ApiCommandRequest(command="paste_problem", input_text=PROBLEM),
    )

    response = store.execute_command(session_id, ApiCommandRequest(raw="/compress"))

    assert response.ok is True
    assert response.data["context"]["snapshot"]["is_empty"] is False


def test_ask_auto_compresses_before_llm_call_when_context_is_large():
    store = _make_store(auto_run=False)
    session_id = store.create_session()["session_id"]

    store.execute_command(
        session_id,
        ApiCommandRequest(command="paste_problem", input_text="# 大题\n" + "很长的题面" * 4000),
    )
    response = store.execute_command(session_id, ApiCommandRequest(command="ask", args="这题怎么想"))
    context = store.context_state(session_id)
    events_text = str(store.recent_events(session_id, limit=20))

    assert response.stream is not None
    assert context["snapshot"]["is_empty"] is False
    assert "context_auto_compressed" in events_text
    assert context["events_since_last_compress"] >= 1


def test_context_provider_uses_snapshot_after_compress():
    store = _make_store(auto_run=False)
    session_id = store.create_session()["session_id"]

    store.execute_command(
        session_id,
        ApiCommandRequest(command="paste_problem", input_text=PROBLEM),
    )
    store.compress_context(session_id)
    record = store._get_record(session_id)

    context = record.coach_session.build_question_context("这题怎么想？")

    assert "上下文快照" in context
    assert "这题怎么想？" in context
    assert "A+B" in context


def test_stream_response_is_serialized_without_generator_object():
    store = _make_store()
    session_id = store.create_session()["session_id"]

    response = store.execute_command(session_id, ApiCommandRequest(command="ask", args="这题怎么想"))
    serialized = serialize_command_response(response)

    assert serialized["has_stream"] is True
    assert "stream" not in serialized
    assert "当前未能初始化 LLM" in "".join(response.stream)
    description = store.describe_session(session_id)
    events = store.recent_events(session_id, limit=20)
    assert description["conversation_message_count"] == 2
    assert any(event["type"] == "assistant_response" for event in events)


def test_summary_stream_is_recorded_for_context_compression():
    class FakeLLM:
        def chat_stream(self, messages, **kwargs):
            yield "流式"
            yield "复盘"

    store = LocalSessionStore(
        session_factory=lambda: OJCoachSession(
            llm_factory=lambda: FakeLLM(),
            auto_extract_with_llm=False,
            auto_run=False,
        )
    )
    session_id = store.create_session()["session_id"]
    state = store._get_record(session_id).coach_session.state
    state.problem_text = PROBLEM
    state.language = "python"
    state.code = PYTHON_AC_CODE
    state.last_run_result = json.dumps({"status": "accepted", "time_ms": 1})

    response = store.execute_command(
        session_id,
        ApiCommandRequest(command="summary", args="检查边界"),
    )

    assert response.stream is not None
    assert "".join(response.stream) == "流式复盘"
    assert store.describe_session(session_id)["conversation_message_count"] == 2
    assert any(
        event["type"] == "assistant_response"
        for event in store.recent_events(session_id, limit=20)
    )


def test_summary_checks_auto_compression_threshold():
    store = _make_store(auto_run=False)
    session_id = store.create_session()["session_id"]
    store.execute_command(
        session_id,
        ApiCommandRequest(command="paste_problem", input_text="# 大题\n" + "长题面" * 5000),
    )

    store.execute_command(session_id, ApiCommandRequest(command="summary", args="检查边界"))

    context = store.context_state(session_id)
    events = store.recent_events(session_id, limit=20)
    assert context["snapshot"]["is_empty"] is False
    assert any(event["type"] == "context_auto_compressed" for event in events)


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
