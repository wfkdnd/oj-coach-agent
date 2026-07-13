"""run_oj_code 长输出判题回归测试。"""

import json

from oj_tools.run_oj_code import (
    OUTPUT_LIMIT,
    _build_result,
    _compare_and_decide,
    _to_json,
)


def test_long_exact_output_is_compared_before_display_truncation():
    output = "A" * (OUTPUT_LIMIT + 50)
    result = _build_result(
        status="no_expected_output",
        stdout=output,
        stderr="",
        exit_code=0,
        compile_output="",
        time_ms=1,
    )

    comparison = _compare_and_decide(result, output)

    assert comparison["status"] == "accepted"
    assert "已截断" in result["stdout"]
    assert "已截断" in comparison["normalized_stdout"]


def test_difference_after_display_limit_is_still_detected():
    expected_output = "A" * OUTPUT_LIMIT + "X"
    actual_output = "A" * OUTPUT_LIMIT + "Y"
    result = _build_result(
        status="no_expected_output",
        stdout=actual_output,
        stderr="",
        exit_code=0,
        compile_output="",
        time_ms=1,
    )

    comparison = _compare_and_decide(result, expected_output)

    assert comparison["status"] == "wrong_answer"


def test_private_full_stdout_is_not_exposed_in_public_json():
    output = "B" * (OUTPUT_LIMIT + 1)
    result = _build_result(
        status="accepted",
        stdout=output,
        stderr="",
        exit_code=0,
        compile_output="",
        time_ms=1,
    )

    public_result = json.loads(_to_json(result))

    assert "_raw_stdout" not in public_result
    assert "已截断" in public_result["stdout"]
