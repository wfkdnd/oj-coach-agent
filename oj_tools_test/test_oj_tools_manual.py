"""oj_tools 的手动测试脚本。

通过环境变量提供测试用例路径，然后任选一种方式运行：

    python oj_tools_test/test_oj_tools_manual.py
    pytest oj_tools_test -s

脚本会打印 read_problem_file、read_code_file 和 run_oj_code 的原始结果，
方便你在自己提供测试用例时直接看到工具行为。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


def _configure_utf8_output() -> None:
    """让 Windows/PowerShell 下的中文测试输出尽量按 UTF-8 写出。"""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


_configure_utf8_output()

try:
    import pytest
except ImportError:  # 允许在没有安装 pytest 时直接作为普通脚本运行。
    pytest = None  # type: ignore[assignment]


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from oj_tools import analyze_problem, read_code_file, read_problem_file, run_oj_code


VALID_RUN_STATUSES = {
    "accepted",
    "wrong_answer",
    "compile_error",
    "runtime_error",
    "time_limit_exceeded",
    "no_expected_output",
}
TEXT_ENCODINGS = ("utf-8", "utf-8-sig", "gb18030")
TOOL_ERROR_PREFIXES = ("error", "Error", "ERROR", "\u9519\u8bef")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _skip_or_raise(message: str) -> None:
    if pytest is not None:
        pytest.skip(message)
    raise RuntimeError(message)


def _read_env_text(value_name: str, file_name: str) -> str:
    file_path = _env(file_name)
    if file_path:
        return _read_text_file(Path(file_path).expanduser())
    return _env(value_name)


def _read_text_file(path: Path) -> str:
    last_error: UnicodeDecodeError | None = None
    for encoding in TEXT_ENCODINGS:
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
    raise UnicodeDecodeError(
        last_error.encoding if last_error else "unknown",
        last_error.object if last_error else b"",
        last_error.start if last_error else 0,
        last_error.end if last_error else 0,
        f"无法解码文件：{path}",
    )


def _print_section(title: str, content: str) -> None:
    print(f"\n===== {title} =====")
    print(content)


def _looks_like_error(result: str) -> bool:
    stripped = result.lstrip()
    return stripped.startswith(TOOL_ERROR_PREFIXES)


def _parse_json_object(tool_name: str, raw_result: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw_result)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"{tool_name} 没有返回 JSON：{raw_result}") from exc

    assert isinstance(payload, dict), f"{tool_name} 返回的 JSON 不是对象：{payload!r}"
    return payload


def _load_code_payload(raw_result: str) -> dict[str, Any]:
    payload = _parse_json_object("read_code_file", raw_result)
    assert payload.get("code", "").strip(), "read_code_file 返回了空代码"
    assert payload.get("language") in {"python", "cpp", "java"}, (
        f"识别到不支持的语言：{payload.get('language')!r}"
    )
    return payload


def _has_manual_run_input() -> bool:
    return any(
        _env(name)
        for name in (
            "OJ_STDIN",
            "OJ_STDIN_FILE",
            "OJ_EXPECTED_OUTPUT",
            "OJ_EXPECTED_OUTPUT_FILE",
            "OJ_TEST_CASES",
            "OJ_TEST_CASES_FILE",
        )
    )


def _should_use_problem_sample() -> bool:
    flag = _env("OJ_USE_PROBLEM_SAMPLE").strip().lower()
    if flag:
        return flag not in {"0", "false", "no", "off", "否"}
    return not _has_manual_run_input()


def check_read_problem_file() -> str:
    problem_file = _env("OJ_PROBLEM_FILE")
    if not problem_file:
        _skip_or_raise("请把 OJ_PROBLEM_FILE 设置为你的 .txt、.md 或 .docx 题目文件。")

    result = read_problem_file(problem_file)
    _print_section("read_problem_file 返回结果", result)

    assert result.strip(), "read_problem_file 返回了空文本"
    assert not _looks_like_error(result), result
    return result


def check_analyze_problem(problem_text: str | None = None) -> dict[str, Any]:
    if problem_text is None:
        problem_text = check_read_problem_file()

    raw_result = analyze_problem(problem_text)
    _print_section("analyze_problem 返回结果", raw_result)

    assert raw_result.strip(), "analyze_problem 返回了空结果"
    assert not _looks_like_error(raw_result), raw_result

    payload = _parse_json_object("analyze_problem", raw_result)
    test_cases = payload.get("测试用例", [])
    if test_cases:
        _print_section("从题目分析得到的测试用例", json.dumps(test_cases, ensure_ascii=False, indent=2))
    else:
        _print_section("从题目分析得到的测试用例", "未提取到测试用例")

    return payload


def check_read_code_file() -> dict[str, Any]:
    code_file = _env("OJ_CODE_FILE")
    if not code_file:
        _skip_or_raise("请把 OJ_CODE_FILE 设置为你的 .py、.cpp 或 .java 代码文件。")

    raw_result = read_code_file(code_file)
    _print_section("read_code_file 返回结果", raw_result)

    assert not _looks_like_error(raw_result), raw_result
    return _load_code_payload(raw_result)


def check_run_oj_code(problem_text: str = "") -> dict[str, Any]:
    code_payload = check_read_code_file()
    language = _env("OJ_LANGUAGE") or str(code_payload["language"])
    stdin = _read_env_text("OJ_STDIN", "OJ_STDIN_FILE")
    expected_output = _read_env_text("OJ_EXPECTED_OUTPUT", "OJ_EXPECTED_OUTPUT_FILE")
    test_cases = _read_env_text("OJ_TEST_CASES", "OJ_TEST_CASES_FILE")
    timeout_ms = int(_env("OJ_TIMEOUT_MS", "3000"))
    selected_problem_text = problem_text if _should_use_problem_sample() else ""

    if selected_problem_text:
        _print_section("run_oj_code 测试用例来源", "已传入 problem_text，工具会优先从题目中提取样例。")
    elif test_cases:
        _print_section("run_oj_code 测试用例来源", "使用 OJ_TEST_CASES 或 OJ_TEST_CASES_FILE 提供的手动测试用例。")
    else:
        _print_section("run_oj_code 测试用例来源", "使用 OJ_STDIN/OJ_EXPECTED_OUTPUT 或对应文件提供的手动输入。")

    raw_result = run_oj_code(
        language=language,
        code=str(code_payload["code"]),
        stdin=stdin,
        expected_output=expected_output,
        timeout_ms=timeout_ms,
        problem_text=selected_problem_text,
        test_cases=test_cases,
    )
    _print_section("run_oj_code 返回结果", raw_result)

    try:
        result = json.loads(raw_result)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"run_oj_code 没有返回 JSON：{raw_result}") from exc

    assert result.get("status") in VALID_RUN_STATUSES, (
        f"运行状态不在预期范围内：{result.get('status')!r}"
    )

    required_status = _env("OJ_REQUIRE_STATUS")
    if required_status:
        assert result["status"] == required_status, (
            f"期望运行状态是 {required_status!r}，实际是 {result['status']!r}"
        )

    return result


def test_read_problem_file_manual() -> None:
    check_read_problem_file()


def test_analyze_problem_manual() -> None:
    check_analyze_problem()


def test_read_code_file_manual() -> None:
    check_read_code_file()


def test_run_oj_code_manual() -> None:
    check_run_oj_code()


def main() -> int:
    problem_text = check_read_problem_file()
    check_analyze_problem(problem_text)
    check_run_oj_code(problem_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
