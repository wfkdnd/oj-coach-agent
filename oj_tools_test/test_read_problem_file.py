"""第9章 测试：read_problem_file — 读题"""

import sys
import os
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from oj_tools.read_problem_file import read_problem, read_problem_file


PROBLEM_TEXT = "## 两数之和\n给定一个数组，找出和为 target 的两个数。"


def test_read_problem_from_text():
    """粘贴文本读取题目"""
    result = read_problem(problem_text=PROBLEM_TEXT)
    assert "两数之和" in result, f"应包含题目内容，实际: {result}"
    assert "target" in result


def test_read_problem_from_txt_file():
    """从 .txt 文件读取"""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
    tmp.write(PROBLEM_TEXT)
    tmp.close()

    try:
        result = read_problem_file(tmp.name)
        assert "两数之和" in result, f"应读取文件内容，实际: {result}"
    finally:
        os.unlink(tmp.name)


def test_read_problem_from_md_file():
    """从 .md 文件读取"""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
    tmp.write("# 测试题\n输入一个整数。")
    tmp.close()

    try:
        result = read_problem_file(tmp.name)
        assert "测试题" in result, f"应读取 md 文件内容，实际: {result}"
    finally:
        os.unlink(tmp.name)


def test_read_problem(text_only=True):
    """read_problem 统一入口：粘贴文本"""
    # paste path
    result = read_problem(problem_text=PROBLEM_TEXT)
    assert "两数之和" in result
    assert "错误" not in result[:2], f"不应返回错误，实际: {result}"


def test_file_not_found():
    """文件不存在"""
    result = read_problem_file("/nonexistent/path/to/file.txt")
    assert "不存在" in result or "错误" in result, f"应报错，实际: {result}"


def test_unsupported_extension():
    """不支持的文件类型"""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".pdf", delete=False)
    tmp.write("test")
    tmp.close()

    try:
        result = read_problem_file(tmp.name)
        assert "不支持" in result or "错误" in result, f"应报错不支持，实际: {result}"
    finally:
        os.unlink(tmp.name)


def test_both_text_and_file():
    """同时提供粘贴文本和文件路径"""
    result = read_problem(problem_text=PROBLEM_TEXT, file_path="test.txt")
    assert "只能提供其中一个" in result or "错误" in result, f"应报错，实际: {result}"


def test_neither_text_nor_file():
    """都不提供"""
    result = read_problem(problem_text="", file_path="")
    assert "请提供" in result or "错误" in result, f"应报错，实际: {result}"


def test_text_normalization():
    """\\r\\n 换行符应被标准化"""
    result = read_problem(problem_text="line1\r\nline2\r\nline3")
    assert "\r" not in result, "\\r 应被移除"
    assert "line1\nline2\nline3" == result


def test_whitespace_only_text():
    """只有空白字符的输入"""
    result = read_problem(problem_text="   \n  \t  \n  ")
    assert "请提供" in result or "错误" in result, f"应报错，实际: {result}"


if __name__ == "__main__":
    test_read_problem_from_text()
    print("  [OK] test_read_problem_from_text")
    test_read_problem_from_txt_file()
    print("  [OK] test_read_problem_from_txt_file")
    test_read_problem_from_md_file()
    print("  [OK] test_read_problem_from_md_file")
    test_read_problem()
    print("  [OK] test_read_problem")
    test_file_not_found()
    print("  [OK] test_file_not_found")
    test_unsupported_extension()
    print("  [OK] test_unsupported_extension")
    test_both_text_and_file()
    print("  [OK] test_both_text_and_file")
    test_neither_text_nor_file()
    print("  [OK] test_neither_text_nor_file")
    test_text_normalization()
    print("  [OK] test_text_normalization")
    test_whitespace_only_text()
    print("  [OK] test_whitespace_only_text")
    print("\n[PASS] 第9章 read_problem_file 全部测试通过")
