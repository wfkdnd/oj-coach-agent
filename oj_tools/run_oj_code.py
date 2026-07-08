"""
运行普通 OJ 代码。

支持 Python、C++、Java。运行时只在临时目录中写入代码和编译产物，
通过超时和返回内容截断降低风险，不把用户代码保存到项目目录。
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from oj_tools.analyze_problem import extract_problem_test_cases


DEFAULT_TIMEOUT_MS = 3000
MAX_TIMEOUT_MS = 30000
OUTPUT_LIMIT = 20000

LANGUAGE_ALIASES = {
    "py": "python",
    "python": "python",
    "python3": "python",
    "cpp": "cpp",
    "c++": "cpp",
    "cc": "cpp",
    "java": "java",
}


def run_oj_code(
    language: str,
    code: str,
    stdin: str = "",
    expected_output: str = "",
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    problem_text: str = "",
    test_cases: str = "",
) -> str:
    """编译或运行 OJ 代码，并返回结构化运行结果 JSON 字符串。"""
    started_at = time.perf_counter()
    normalized_language = _normalize_language(language)
    safe_timeout_ms = _safe_timeout_ms(timeout_ms)
    runnable_cases = _collect_test_cases(problem_text, test_cases, stdin, expected_output)

    if not normalized_language:
        return _to_json(
            _build_result(
                status="compile_error",
                stdout="",
                stderr=f"错误：不支持的语言：{language}。支持：Python、C++、Java。",
                exit_code=None,
                compile_output="",
                time_ms=_elapsed_ms(started_at),
                expected_output=expected_output,
            )
        )

    if not code.strip():
        return _to_json(
            _build_result(
                status="compile_error",
                stdout="",
                stderr="错误：请提供完整 OJ 代码。",
                exit_code=None,
                compile_output="",
                time_ms=_elapsed_ms(started_at),
                expected_output=expected_output,
            )
        )

    try:
        with tempfile.TemporaryDirectory(prefix="oj_code_") as temp_dir:
            temp_path = Path(temp_dir)
            runner = _prepare_runner(normalized_language, code, safe_timeout_ms, temp_path)
            if runner["status"] != "ready":
                runner["time_ms"] = _elapsed_ms(started_at)
                return _to_json(runner)

            case_results = []
            for case in runnable_cases:
                case_started_at = time.perf_counter()
                single_result = _run_process(
                    runner["command"],
                    case["stdin"],
                    safe_timeout_ms,
                    temp_path,
                    compile_output=runner["compile_output"],
                )
                single_result["time_ms"] = _elapsed_ms(case_started_at)
                single_result["status"] = _decide_status(single_result, case["expected_output"])
                single_result["normalized_stdout"] = _normalize_output(single_result["stdout"])
                single_result["normalized_expected_output"] = _normalize_output(case["expected_output"])
                case_results.append(_build_case_result(case, single_result))
    except Exception as exc:
        return _to_json(
            _build_result(
                status="runtime_error",
                stdout="",
                stderr=f"错误：运行工具内部异常：{exc}",
                exit_code=None,
                compile_output="",
                time_ms=_elapsed_ms(started_at),
                expected_output=expected_output,
            )
        )

    return _to_json(_build_batch_result(case_results, _elapsed_ms(started_at)))


def _prepare_runner(language: str, code: str, timeout_ms: int, temp_path: Path) -> dict:
    if language == "python":
        return _prepare_python_runner(code, temp_path)
    if language == "cpp":
        return _prepare_cpp_runner(code, timeout_ms, temp_path)
    return _prepare_java_runner(code, timeout_ms, temp_path)


def _prepare_python_runner(code: str, temp_path: Path) -> dict:
    source_path = temp_path / "main.py"
    source_path.write_text(_normalize_code(code), encoding="utf-8")
    return {
        "status": "ready",
        "command": [sys.executable, str(source_path)],
        "compile_output": "",
    }


def _prepare_cpp_runner(code: str, timeout_ms: int, temp_path: Path) -> dict:
    source_path = temp_path / "main.cpp"
    executable_path = temp_path / ("main.exe" if sys.platform.startswith("win") else "main")
    source_path.write_text(_normalize_code(code), encoding="utf-8")

    compile_command = ["g++", "main.cpp", "-std=c++17", "-O2", "-o", executable_path.name]
    compile_result = _run_process(compile_command, "", timeout_ms, temp_path, compile_output="")
    compile_output = _join_output(compile_result["stdout"], compile_result["stderr"])

    if compile_result["timed_out"]:
        return _build_result(
            status="time_limit_exceeded",
            stdout="",
            stderr="",
            exit_code=None,
            compile_output=_truncate_output("错误：C++ 编译超时。\n" + compile_output),
            time_ms=0,
        )
    if compile_result["missing_command"]:
        return _build_result(
            status="compile_error",
            stdout="",
            stderr="错误：找不到 g++，请确认本机已安装 C++ 编译器并配置 PATH。",
            exit_code=None,
            compile_output=compile_output,
            time_ms=0,
        )
    if compile_result["exit_code"] != 0:
        return _build_result(
            status="compile_error",
            stdout="",
            stderr="",
            exit_code=compile_result["exit_code"],
            compile_output=compile_output,
            time_ms=0,
        )

    return {
        "status": "ready",
        "command": [str(executable_path)],
        "compile_output": compile_output,
    }


def _prepare_java_runner(code: str, timeout_ms: int, temp_path: Path) -> dict:
    source_path = temp_path / "Main.java"
    source_path.write_text(_normalize_code(code), encoding="utf-8")

    compile_command = ["javac", "Main.java"]
    compile_result = _run_process(compile_command, "", timeout_ms, temp_path, compile_output="")
    compile_output = _join_output(compile_result["stdout"], compile_result["stderr"])

    if compile_result["timed_out"]:
        return _build_result(
            status="time_limit_exceeded",
            stdout="",
            stderr="",
            exit_code=None,
            compile_output=_truncate_output("错误：Java 编译超时。\n" + compile_output),
            time_ms=0,
        )
    if compile_result["missing_command"]:
        return _build_result(
            status="compile_error",
            stdout="",
            stderr="错误：找不到 javac，请确认本机已安装 JDK 并配置 PATH。",
            exit_code=None,
            compile_output=compile_output,
            time_ms=0,
        )
    if compile_result["exit_code"] != 0:
        return _build_result(
            status="compile_error",
            stdout="",
            stderr="",
            exit_code=compile_result["exit_code"],
            compile_output=compile_output,
            time_ms=0,
        )

    return {
        "status": "ready",
        "command": ["java", "Main"],
        "compile_output": compile_output,
    }


def _run_process(command: list[str], stdin: str, timeout_ms: int, cwd: Path, compile_output: str) -> dict:
    try:
        completed = subprocess.run(
            command,
            input=stdin,
            cwd=str(cwd),
            text=True,
            capture_output=True,
            timeout=timeout_ms / 1000,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        return _build_result(
            status="time_limit_exceeded",
            stdout=_decode_timeout_output(exc.stdout),
            stderr=_decode_timeout_output(exc.stderr),
            exit_code=None,
            compile_output=compile_output,
            time_ms=0,
            timed_out=True,
        )
    except FileNotFoundError as exc:
        return _build_result(
            status="runtime_error",
            stdout="",
            stderr=f"错误：找不到运行命令：{exc.filename}",
            exit_code=None,
            compile_output=compile_output,
            time_ms=0,
            missing_command=True,
        )

    return _build_result(
        status="runtime_error" if completed.returncode != 0 else "no_expected_output",
        stdout=completed.stdout,
        stderr=completed.stderr,
        exit_code=completed.returncode,
        compile_output=compile_output,
        time_ms=0,
    )


def _build_result(
    status: str,
    stdout: str,
    stderr: str,
    exit_code: int | None,
    compile_output: str,
    time_ms: int,
    expected_output: str = "",
    timed_out: bool = False,
    missing_command: bool = False,
) -> dict:
    return {
        "status": status,
        "stdout": _truncate_output(stdout),
        "stderr": _truncate_output(stderr),
        "exit_code": exit_code,
        "compile_output": _truncate_output(compile_output),
        "time_ms": time_ms,
        "normalized_stdout": _normalize_output(stdout),
        "normalized_expected_output": _normalize_output(expected_output),
        "timed_out": timed_out,
        "missing_command": missing_command,
    }


def _decide_status(result: dict, expected_output: str) -> str:
    if result["status"] in {"compile_error", "time_limit_exceeded"}:
        return result["status"]
    if result["timed_out"]:
        return "time_limit_exceeded"
    if result["missing_command"]:
        return result["status"]
    if result["exit_code"] not in (0, None):
        return "runtime_error"
    if expected_output == "":
        return "no_expected_output"
    if _normalize_output(result["stdout"]) == _normalize_output(expected_output):
        return "accepted"
    return "wrong_answer"


def _collect_test_cases(problem_text: str, test_cases: str, stdin: str, expected_output: str) -> list[dict[str, str]]:
    collected: list[dict[str, str]] = []

    # 题目样例优先，符合“先从题目中获得测试用例”的使用方式。
    collected.extend(_normalize_test_cases(extract_problem_test_cases(problem_text), default_source="题目样例"))
    collected.extend(_parse_user_test_cases(test_cases))

    if stdin or expected_output or not collected:
        collected.append(
            {
                "name": "用户手动用例",
                "source": "用户添加",
                "stdin": stdin,
                "expected_output": expected_output,
            }
        )

    return collected


def _parse_user_test_cases(test_cases: str) -> list[dict[str, str]]:
    text = test_cases.strip()
    if not text:
        return []

    parsed_json = _parse_test_cases_json(text)
    if parsed_json:
        return parsed_json
    return _parse_test_cases_text(text)


def _parse_test_cases_json(text: str) -> list[dict[str, str]]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []

    if isinstance(payload, dict):
        for key in ("test_cases", "cases", "测试用例", "样例"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
        else:
            payload = [payload]

    if not isinstance(payload, list):
        return []
    return _normalize_test_cases(payload, default_source="用户添加")


def _normalize_test_cases(raw_cases: list, default_source: str) -> list[dict[str, str]]:
    normalized_cases = []
    for index, item in enumerate(raw_cases, start=1):
        if not isinstance(item, dict):
            continue
        stdin = _first_text(item, ("stdin", "input", "输入"))
        expected_output = _first_text(item, ("expected_output", "expected", "output", "输出"))
        source = _first_text(item, ("source", "来源")) or default_source
        name = _first_text(item, ("name", "名称")) or f"{source} {index}"
        if stdin or expected_output:
            normalized_cases.append(
                {
                    "name": name,
                    "source": source,
                    "stdin": stdin,
                    "expected_output": expected_output,
                }
            )
    return normalized_cases


def _parse_test_cases_text(text: str) -> list[dict[str, str]]:
    cases: list[dict[str, str]] = []
    current = {"name": "", "source": "用户添加", "stdin": "", "expected_output": ""}
    current_key = ""

    for line in text.splitlines():
        heading_key, inline_value = _parse_case_heading(line)
        if heading_key == "stdin":
            if current["stdin"] or current["expected_output"]:
                cases.append(current)
                current = {"name": "", "source": "用户添加", "stdin": "", "expected_output": ""}
            current_key = "stdin"
            if inline_value:
                current[current_key] = _append_text(current[current_key], inline_value)
            continue
        if heading_key == "expected_output":
            current_key = "expected_output"
            if inline_value:
                current[current_key] = _append_text(current[current_key], inline_value)
            continue
        if line.strip() in {"---", "==="}:
            if current["stdin"] or current["expected_output"]:
                cases.append(current)
            current = {"name": "", "source": "用户添加", "stdin": "", "expected_output": ""}
            current_key = ""
            continue
        if current_key:
            current[current_key] = _append_text(current[current_key], line)

    if current["stdin"] or current["expected_output"]:
        cases.append(current)

    for index, item in enumerate(cases, start=1):
        item["name"] = item["name"] or f"用户添加 {index}"
    return cases


def _parse_case_heading(line: str) -> tuple[str, str]:
    stripped = line.strip().strip("#").strip()
    if "：" in stripped:
        raw_heading, inline_value = stripped.split("：", 1)
    elif ":" in stripped:
        raw_heading, inline_value = stripped.split(":", 1)
    else:
        raw_heading, inline_value = stripped, ""

    heading = raw_heading.strip().lower()
    if heading in {"输入", "stdin", "input"}:
        return "stdin", inline_value.strip()
    if heading in {"输出", "expected", "expected_output", "output"}:
        return "expected_output", inline_value.strip()
    return "", ""


def _build_case_result(case: dict[str, str], result: dict) -> dict:
    return {
        "name": case["name"],
        "source": case["source"],
        "stdin": case["stdin"],
        "expected_output": case["expected_output"],
        "status": result["status"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "exit_code": result["exit_code"],
        "compile_output": result["compile_output"],
        "time_ms": result["time_ms"],
        "normalized_stdout": result["normalized_stdout"],
        "normalized_expected_output": result["normalized_expected_output"],
    }


def _build_batch_result(case_results: list[dict], time_ms: int) -> dict:
    representative = _pick_representative_case(case_results)
    return {
        "status": _decide_batch_status(case_results),
        "stdout": representative.get("stdout", ""),
        "stderr": representative.get("stderr", ""),
        "exit_code": representative.get("exit_code"),
        "compile_output": representative.get("compile_output", ""),
        "time_ms": time_ms,
        "normalized_stdout": representative.get("normalized_stdout", ""),
        "normalized_expected_output": representative.get("normalized_expected_output", ""),
        "case_count": len(case_results),
        "passed_count": sum(1 for item in case_results if item["status"] == "accepted"),
        "failed_count": sum(1 for item in case_results if item["status"] not in {"accepted", "no_expected_output"}),
        "test_cases": case_results,
    }


def _decide_batch_status(case_results: list[dict]) -> str:
    statuses = [item["status"] for item in case_results]
    for status in ("compile_error", "time_limit_exceeded", "runtime_error", "wrong_answer"):
        if status in statuses:
            return status
    if statuses and all(status == "accepted" for status in statuses):
        return "accepted"
    return "no_expected_output"


def _pick_representative_case(case_results: list[dict]) -> dict:
    for item in case_results:
        if item["status"] not in {"accepted", "no_expected_output"}:
            return item
    return case_results[0] if case_results else {}


def _first_text(item: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = item.get(key)
        if value is not None:
            return str(value).replace("\r\n", "\n").replace("\r", "\n")
    return ""


def _append_text(existing: str, line: str) -> str:
    if not existing:
        return line
    return f"{existing}\n{line}"


def _normalize_language(language: str) -> str:
    return LANGUAGE_ALIASES.get(language.strip().lower(), "")


def _safe_timeout_ms(timeout_ms: int) -> int:
    try:
        value = int(timeout_ms)
    except (TypeError, ValueError):
        value = DEFAULT_TIMEOUT_MS
    return min(max(value, 1), MAX_TIMEOUT_MS)


def _normalize_code(code: str) -> str:
    return code.replace("\r\n", "\n").replace("\r", "\n").strip("\ufeff\n") + "\n"


def _normalize_output(output: str) -> str:
    return output.replace("\r\n", "\n").replace("\r", "\n").rstrip()


def _truncate_output(output: str) -> str:
    if len(output) <= OUTPUT_LIMIT:
        return output
    return output[:OUTPUT_LIMIT] + f"\n...（输出过长，已截断到 {OUTPUT_LIMIT} 字符）"


def _join_output(stdout: str, stderr: str) -> str:
    joined = "\n".join(part for part in (stdout.strip(), stderr.strip()) if part)
    return _truncate_output(joined)


def _decode_timeout_output(output: str | bytes | None) -> str:
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output


def _elapsed_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


def _to_json(result: dict) -> str:
    # 内部控制字段不暴露给 Agent，避免干扰 README 约定的结果结构。
    public_result = {
        "status": result["status"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "exit_code": result["exit_code"],
        "compile_output": result["compile_output"],
        "time_ms": result["time_ms"],
        "normalized_stdout": result["normalized_stdout"],
        "normalized_expected_output": result["normalized_expected_output"],
    }
    for key in ("case_count", "passed_count", "failed_count", "test_cases"):
        if key in result:
            public_result[key] = result[key]
    return json.dumps(public_result, ensure_ascii=False, indent=2)
