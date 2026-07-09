"""第10章 测试：read_code_file — 读代码"""

import sys
import os
import tempfile
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from oj_tools.read_code_file import read_code, read_code_file


PYTHON_CODE = "def solve():\n    a, b = map(int, input().split())\n    print(a + b)\n\nsolve()"
CPP_CODE = "#include <iostream>\nint main() {\n    int a, b;\n    std::cin >> a >> b;\n    std::cout << a + b;\n    return 0;\n}"
JAVA_CODE = "import java.util.*;\npublic class Main {\n    public static void main(String[] args) {\n        Scanner sc = new Scanner(System.in);\n        int a = sc.nextInt();\n        int b = sc.nextInt();\n        System.out.println(a + b);\n    }\n}"


def _parse_code_result(raw: str) -> dict:
    return json.loads(raw)


def test_read_code_from_paste():
    """粘贴代码读取"""
    result = _parse_code_result(read_code(code_text=PYTHON_CODE, language="python"))
    assert result["language"] == "python"
    assert "def solve" in result["code"]
    assert result["source"] == "粘贴文本"


def test_read_code_with_language_alias():
    """语言别名：py -> python, c++ -> cpp"""
    r1 = _parse_code_result(read_code(code_text=PYTHON_CODE, language="py"))
    assert r1["language"] == "python"

    r2 = _parse_code_result(read_code(code_text=CPP_CODE, language="c++"))
    assert r2["language"] == "cpp"

    r3 = _parse_code_result(read_code(code_text=JAVA_CODE, language="java"))
    assert r3["language"] == "java"


def test_read_code_from_py_file():
    """从 .py 文件读取，自动识别语言"""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8")
    tmp.write(PYTHON_CODE)
    tmp.close()

    try:
        result = _parse_code_result(read_code_file(tmp.name))
        assert result["language"] == "python"
        assert "def solve" in result["code"]
        assert result["source"] == "文件"
    finally:
        os.unlink(tmp.name)


def test_read_code_from_cpp_file():
    """从 .cpp 文件读取，自动识别语言"""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".cpp", delete=False, encoding="utf-8")
    tmp.write(CPP_CODE)
    tmp.close()

    try:
        result = _parse_code_result(read_code_file(tmp.name))
        assert result["language"] == "cpp"
        assert "int main" in result["code"]
    finally:
        os.unlink(tmp.name)


def test_read_code_from_java_file():
    """从 .java 文件读取，自动识别语言"""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".java", delete=False, encoding="utf-8")
    tmp.write(JAVA_CODE)
    tmp.close()

    try:
        result = _parse_code_result(read_code_file(tmp.name))
        assert result["language"] == "java"
        assert "public class Main" in result["code"]
    finally:
        os.unlink(tmp.name)


def test_file_not_found():
    """代码文件不存在"""
    result = read_code_file("/nonexistent/code.py")
    assert "不存在" in result or "错误" in result


def test_unsupported_extension():
    """不支持的文件类型"""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False)
    tmp.write("console.log('hello')")
    tmp.close()

    try:
        result = read_code_file(tmp.name)
        assert "不支持" in result or "错误" in result
    finally:
        os.unlink(tmp.name)


def test_both_text_and_file():
    """同时提供粘贴和文件路径"""
    result = read_code(code_text="print(1)", file_path="test.py")
    assert "只能提供其中一个" in result or "错误" in result


def test_neither_text_nor_file():
    """都不提供"""
    result = read_code(code_text="", file_path="")
    assert "请提供" in result or "错误" in result


def test_unknown_language():
    """未知语言"""
    result = _parse_code_result(read_code(code_text=PYTHON_CODE, language=""))
    assert result["language"] == "未知"


def test_code_normalization():
    """\\r\\n 换行符标准化 + BOM 移除"""
    result = _parse_code_result(read_code(code_text="print(1)\r\nprint(2)\r\n", language="python"))
    assert "\r" not in result["code"], "\\r 应被移除"


if __name__ == "__main__":
    test_read_code_from_paste()
    print("  [OK] test_read_code_from_paste")
    test_read_code_with_language_alias()
    print("  [OK] test_read_code_with_language_alias")
    test_read_code_from_py_file()
    print("  [OK] test_read_code_from_py_file")
    test_read_code_from_cpp_file()
    print("  [OK] test_read_code_from_cpp_file")
    test_read_code_from_java_file()
    print("  [OK] test_read_code_from_java_file")
    test_file_not_found()
    print("  [OK] test_file_not_found")
    test_unsupported_extension()
    print("  [OK] test_unsupported_extension")
    test_both_text_and_file()
    print("  [OK] test_both_text_and_file")
    test_neither_text_nor_file()
    print("  [OK] test_neither_text_nor_file")
    test_unknown_language()
    print("  [OK] test_unknown_language")
    test_code_normalization()
    print("  [OK] test_code_normalization")
    print("\n[PASS] 第10章 read_code_file 全部测试通过")
