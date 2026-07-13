"""测试可复用的 OJCoachSession 工作流层。"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from oj_coach import OJCoachSession


PROBLEM = """## A+B
给定两个整数 a 和 b，输出它们的和。

样例输入：
1 2

样例输出：
3
"""

PYTHON_AC_CODE = "a, b = map(int, input().split())\nprint(a + b)"
PYTHON_NO_INPUT_CODE = 'print("YES")'


def _make_session(auto_run=True):
    return OJCoachSession(llm_factory=lambda: None, auto_run=auto_run)


def test_set_problem_text_falls_back_to_rule_cases():
    session = _make_session()

    result = session.set_problem_text(PROBLEM)
    status = session.status()

    assert result["ok"] is True
    assert status["problem_text_set"] is True
    assert status["analysis_result_set"] is True
    assert status["runnable_case_count"] == 1
    assert status["test_case_sources"] == {"题目": 1}
    assert status["test_cases"][0]["expected_output"] == "3"


def test_llm_test_case_extraction_accepts_stream_collected_json():
    """LLM 客户端收集流式 JSON 后，题目样例仍应写入统一用例结构。"""
    class FakeLLM:
        def chat(self, messages, **kwargs):
            return json.dumps(
                {
                    "test_cases": [
                        {"stdin": "4 5", "expected_output": "9"},
                        {"stdin": "", "expected_output": "YES"},
                    ]
                },
                ensure_ascii=False,
            )

    session = OJCoachSession(llm_factory=lambda: FakeLLM(), auto_run=False)
    result = session.set_problem_text("输出 4 与 5 的和，并额外输出 YES。")
    status = session.status()

    assert result["ok"] is True
    assert status["runnable_case_count"] == 2
    assert status["test_case_sources"] == {"题目": 2}
    assert status["test_cases"][1]["stdin"] == ""
    assert status["test_cases"][1]["expected_output"] == "YES"


def test_set_code_auto_runs_existing_problem_case():
    session = _make_session()
    session.set_problem_text(PROBLEM)

    result = session.set_code(PYTHON_AC_CODE, "python")
    run_result = json.loads(result["run_result"])

    assert result["ok"] is True
    assert run_result["status"] == "accepted"
    assert run_result["case_count"] == 1
    assert run_result["passed_count"] == 1
    assert session.status()["last_run_result_set"] is True


def test_add_cases_and_run_code_without_auto_run():
    session = _make_session(auto_run=False)
    session.set_code(PYTHON_AC_CODE, "python")

    add_result = session.add_cases("输入：\n5 7\n输出：\n12")
    run_result = session.run_code()
    parsed = json.loads(run_result["run_result"])

    assert add_result["ok"] is True
    assert run_result["ok"] is True
    assert parsed["status"] == "accepted"
    assert parsed["case_count"] == 1


def test_add_cases_ignores_problem_and_repeated_user_duplicates():
    session = _make_session(auto_run=False)
    session.set_problem_text(PROBLEM)
    submitted = json.dumps(
        {
            "test_cases": [
                {"stdin": "1 2", "expected_output": "3"},
                {"stdin": "5 7", "expected_output": "12"},
            ]
        },
        ensure_ascii=False,
    )

    first = session.add_cases(submitted)
    second = session.add_cases(submitted)
    status = session.status()

    assert first["ok"] is True
    assert second["ok"] is True
    assert "忽略 2 组重复用例" in second["messages"][0]
    assert status["runnable_case_count"] == 2
    assert status["test_case_sources"] == {"题目": 1, "用户": 1}


def test_output_only_case_runs_without_stdin():
    session = _make_session(auto_run=False)
    session.set_code(PYTHON_NO_INPUT_CODE, "python")

    add_result = session.add_cases("输出：\nYES")
    run_result = session.run_code()
    parsed = json.loads(run_result["run_result"])

    assert add_result["ok"] is True
    assert session.status()["runnable_case_count"] == 1
    assert parsed["status"] == "accepted"
    assert parsed["case_count"] == 1


def test_summary_rule_version_without_llm():
    session = _make_session()
    session.set_problem_text(PROBLEM)
    session.set_code(PYTHON_AC_CODE, "python")

    result = session.summarize("测试通过")
    summary = json.loads(result["rule_summary"])

    assert result["ok"] is True
    assert result["llm_summary"] == ""
    assert summary["运行状态"] == "accepted"
    assert summary["用户备注"] == "测试通过"


def test_ask_reports_missing_llm():
    session = _make_session()

    result = session.ask("这题怎么做？")

    assert result["ok"] is False
    assert any("LLM" in message for message in result["messages"])


def test_ask_falls_back_to_rule_summary_without_llm_when_ready():
    session = _make_session()
    session.set_problem_text(PROBLEM)
    session.set_code(PYTHON_AC_CODE, "python")

    result = session.ask("帮我复盘一下")

    assert result["ok"] is True
    assert result["llm_available"] is False
    assert "规则版复盘总结" in result["answer"]
    assert "```json" in result["answer"]
    assert json.loads(result["rule_summary"])["运行状态"] == "accepted"


def test_build_question_context_uses_context_provider_when_available():
    session = OJCoachSession(
        llm_factory=lambda: None,
        context_provider=lambda question: f"压缩上下文：{question}",
    )

    assert session.build_question_context("这题怎么想？") == "压缩上下文：这题怎么想？"


def test_build_question_context_falls_back_when_context_provider_empty():
    session = OJCoachSession(
        llm_factory=lambda: None,
        context_provider=lambda question: "",
    )
    session.state.code = "print(1)"

    context = session.build_question_context("这题怎么想？")

    assert "用户问题" in context
    assert "print(1)" in context


def test_summary_explanation_includes_compressed_context_snapshot():
    class CapturingLLM:
        def __init__(self):
            self.messages = []

        def chat(self, messages, **kwargs):
            self.messages = messages
            return "复盘完成"

    llm = CapturingLLM()
    session = OJCoachSession(
        llm_factory=lambda: llm,
        context_provider=lambda purpose: f"上下文快照：{purpose}",
    )

    result = session.explain_summary('{"运行状态":"accepted"}', "关注边界")

    assert result == "复盘完成"
    prompt = llm.messages[-1]["content"]
    assert "阶段 6/7 上下文快照" in prompt
    assert "上下文快照：" in prompt
