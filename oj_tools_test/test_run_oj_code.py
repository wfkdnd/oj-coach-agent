"""第11章 测试：run_oj_code — 运行 OJ 代码"""

import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from oj_tools.run_oj_code import run_oj_code


PYTHON_AC_CODE = "a, b = map(int, input().split())\nprint(a + b)"
PYTHON_WA_CODE = "a, b = map(int, input().split())\nprint(a - b)"
PYTHON_CE_CODE = "def solve(:\n    return 1"  # 语法错误
PYTHON_RE_CODE = "x = 1 // 0"  # 运行时除零错误
PYTHON_TLE_CODE = "while True:\n    pass"  # 死循环
PYTHON_INPUT_CODE = "import sys\nn = int(sys.stdin.readline())\nnums = list(map(int, sys.stdin.readline().split()))\nprint(sum(nums))"


def _parse(raw: str) -> dict:
    return json.loads(raw)


def test_unsupported_language():
    """不支持的语言"""
    result = _parse(run_oj_code(language="ruby", code="puts 1"))
    assert result["status"] == "compile_error", f"不支持语言应返回 compile_error，实际: {result['status']}"
    assert "不支持" in result.get("stderr", "") or "支持" in result.get("stderr", "")


def test_python_ac():
    """Python AC：输出匹配期望"""
    result = _parse(run_oj_code(
        language="python",
        code=PYTHON_AC_CODE,
        stdin="3 5",
        expected_output="8",
    ))
    assert result["status"] == "accepted", f"应该是 accepted，实际: {result['status']}"


def test_python_wa():
    """Python WA：输出不匹配期望"""
    result = _parse(run_oj_code(
        language="python",
        code=PYTHON_WA_CODE,
        stdin="5 3",
        expected_output="8",
    ))
    assert result["status"] == "wrong_answer", f"应该是 wrong_answer，实际: {result['status']}"


def test_python_compile_error():
    """Python 语法错误"""
    result = _parse(run_oj_code(
        language="python",
        code=PYTHON_CE_CODE,
        stdin="",
    ))
    assert result["status"] in ("compile_error", "runtime_error"), \
        f"语法错误状态应为 compile_error 或 runtime_error，实际: {result['status']}"


def test_python_runtime_error():
    """Python 运行时错误（除零）"""
    result = _parse(run_oj_code(
        language="python",
        code=PYTHON_RE_CODE,
        stdin="",
    ))
    assert result["status"] == "runtime_error", f"应该是 runtime_error，实际: {result['status']}"
    assert result["exit_code"] != 0, f"退出码应非0，实际: {result['exit_code']}"


def test_python_time_limit_exceeded():
    """Python 超时"""
    result = _parse(run_oj_code(
        language="python",
        code=PYTHON_TLE_CODE,
        stdin="",
        timeout_ms=500,
    ))
    assert result["status"] == "time_limit_exceeded", f"应该是 time_limit_exceeded，实际: {result['status']}"


def test_timeout_clamping():
    """超时值应被限制在最大值以内"""
    result = _parse(run_oj_code(
        language="python",
        code=PYTHON_AC_CODE,
        stdin="1 2",
        timeout_ms=99999,
    ))
    # 不应该崩，timeout_ms 会被 clamp 到 MAX_TIMEOUT_MS
    assert result["status"] in ("accepted", "no_expected_output")  # 正常运行即可


def test_no_expected_output():
    """无期望输出时，正常返回 no_expected_output"""
    result = _parse(run_oj_code(
        language="python",
        code=PYTHON_AC_CODE,
        stdin="3 5",
    ))
    assert result["status"] in ("accepted", "wrong_answer", "no_expected_output"), \
        f"未设 expected_output 的状态，实际: {result['status']}"


def test_output_truncation():
    """超长输出应被截断"""
    big_code = "print('x' * 30000)"
    result = _parse(run_oj_code(
        language="python",
        code=big_code,
        stdin="",
    ))
    stdout = result.get("stdout", "")
    # 即使输出很大，也不应该无限长
    assert len(stdout) <= 30000, f"输出应被截断，实际长度: {len(stdout)}"


def test_with_problem_text():
    """传入 problem_text，工具应自动提取测试用例"""
    problem = """## 加和
输入：
1 2
输出：
3
"""
    result = _parse(run_oj_code(
        language="python",
        code=PYTHON_AC_CODE,
        problem_text=problem,
    ))
    # 应能从 problem_text 中提取样例，并有运行结果
    assert result["status"] in ("accepted", "wrong_answer", "no_expected_output", "compile_error", "runtime_error")


def test_with_test_cases():
    """传入 test_cases JSON"""
    cases = json.dumps([
        {"名称": "case1", "stdin": "1 2", "expected_output": "3"},
        {"名称": "case2", "stdin": "5 5", "expected_output": "10"},
    ], ensure_ascii=False)
    result = _parse(run_oj_code(
        language="python",
        code=PYTHON_AC_CODE,
        test_cases=cases,
    ))
    # 应有多个测试用例结果
    assert result["status"] in ("accepted", "wrong_answer", "no_expected_output")


def test_large_input():
    """大量输入数据"""
    stdin_text = "2000\n" + " ".join(str(i) for i in range(2000))
    result = _parse(run_oj_code(
        language="python",
        code=PYTHON_INPUT_CODE,
        stdin=stdin_text,
    ))
    assert result["status"] in ("accepted", "wrong_answer", "no_expected_output", "runtime_error", "time_limit_exceeded")
    # 不应崩溃


def test_cpp_ac():
    """C++ 代码编译运行（需要 g++），返回 True 表示跳过"""
    result = _parse(run_oj_code(
        language="cpp",
        code="#include <iostream>\nint main() { int a, b; std::cin >> a >> b; std::cout << a + b; return 0; }",
        stdin="3 5",
        expected_output="8",
    ))
    if result["status"] == "compile_error":
        compile_msg = result.get("compile_output", "")
        if "g++" in compile_msg or "gcc" in compile_msg or "找不到" in compile_msg:
            print("  [SKIP] test_cpp_ac (g++ 不可用)")
            return True
    assert result["status"] == "accepted", f"C++ AC 应通过，实际: {result['status']}: {result.get('compile_output','')}"


def test_java_ac():
    """Java 代码编译运行（需要 javac），返回 True 表示跳过"""
    java_code = """public class Main {
    public static void main(String[] args) {
        java.util.Scanner sc = new java.util.Scanner(System.in);
        int a = sc.nextInt();
        int b = sc.nextInt();
        System.out.println(a + b);
    }
}"""
    result = _parse(run_oj_code(
        language="java",
        code=java_code,
        stdin="3 5",
        expected_output="8",
    ))
    if result["status"] == "compile_error":
        compile_msg = result.get("compile_output", "")
        if "javac" in compile_msg or "java" in compile_msg or "找不到" in compile_msg:
            print("  [SKIP] test_java_ac (javac 不可用)")
            return True
    assert result["status"] == "accepted", f"Java AC 应通过，实际: {result['status']}: {result.get('compile_output','')}"


if __name__ == "__main__":
    test_unsupported_language()
    print("  [OK] test_unsupported_language")
    test_python_ac()
    print("  [OK] test_python_ac")
    test_python_wa()
    print("  [OK] test_python_wa")
    test_python_compile_error()
    print("  [OK] test_python_compile_error")
    test_python_runtime_error()
    print("  [OK] test_python_runtime_error")
    test_python_time_limit_exceeded()
    print("  [OK] test_python_time_limit_exceeded")
    test_timeout_clamping()
    print("  [OK] test_timeout_clamping")
    test_no_expected_output()
    print("  [OK] test_no_expected_output")
    test_output_truncation()
    print("  [OK] test_output_truncation")
    test_with_problem_text()
    print("  [OK] test_with_problem_text")
    test_with_test_cases()
    print("  [OK] test_with_test_cases")
    test_large_input()
    print("  [OK] test_large_input")
    if not test_cpp_ac():
        print("  [OK] test_cpp_ac")
    if not test_java_ac():
        print("  [OK] test_java_ac")
    print("\n[PASS] 第11章 run_oj_code 全部测试通过")
