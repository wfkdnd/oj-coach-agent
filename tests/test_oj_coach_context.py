"""测试 OJ Coach 上下文压缩预留层。"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from oj_coach.context import ContextCompressor, SessionEvent
from oj_coach.session import OJCoachState


class FakeGenericContextManager:
    def __init__(self):
        self.called = False

    def compress(self, messages):
        self.called = True
        return [
            messages[0],
            {"role": "system", "content": "[对话摘要] 已压缩中间对话"},
            messages[-1],
        ]


def test_context_compressor_reuses_generic_context_manager():
    generic = FakeGenericContextManager()
    compressor = ContextCompressor(generic_context_manager=generic)

    summary = compressor.compress_conversation_messages(
        [
            {"role": "system", "content": "你是刷题陪练。"},
            {"role": "user", "content": "这题怎么想？"},
            {"role": "assistant", "content": "先看输入约束。"},
        ]
    )

    assert generic.called is True
    assert "对话摘要" in summary


def test_context_snapshot_summarizes_state_without_full_code():
    state = OJCoachState(
        problem_text="# A+B\n给定两个整数，输出和。",
        language="python",
        code="a, b = map(int, input().split())\nprint(a + b)",
        test_cases='{"test_cases":[{"source":"题目","stdin":"1 2","expected_output":"3"}]}',
        last_run_result='{"status":"accepted","time_ms":12,"case_count":1,"passed_count":1}',
    )
    events = [SessionEvent("command_executed", {"command": "run", "ok": True})]

    snapshot = ContextCompressor().compress(state, events)

    assert snapshot.is_empty is False
    assert "A+B" in snapshot.problem_summary
    assert "代码长度" in snapshot.code_summary
    assert state.code not in snapshot.code_summary
    assert "accepted" in snapshot.run_summary
    assert snapshot.source_event_count == 1


def test_should_compress_uses_event_count_or_state_size():
    compressor = ContextCompressor(max_events_before_compress=2, max_chars_before_compress=1000)
    state = OJCoachState()

    assert compressor.should_compress([SessionEvent("a", {})], state) is False
    assert compressor.should_compress([SessionEvent("a", {}), SessionEvent("b", {})], state) is True

    large_state = OJCoachState(problem_text="x" * 1200)
    assert compressor.should_compress([], large_state) is True
