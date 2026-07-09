"""第8章 测试：compare_output — 输出对比"""

import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from oj_tools.compare_output import compare_output


def test_strict_match():
    """strict 模式：完全匹配"""
    result = json.loads(compare_output("1 2 3", "1 2 3", mode="strict"))
    assert result["status"] == "accepted", f"完全匹配应是 accepted，实际: {result['status']}"
    assert result["matched"] is True


def test_strict_mismatch():
    """strict 模式：不匹配"""
    result = json.loads(compare_output("1 2 3", "1 2 4", mode="strict"))
    assert result["status"] == "wrong_answer", f"不匹配应是 wrong_answer，实际: {result['status']}"
    assert result["matched"] is False
    assert result["diff_info"], "不匹配时应有 diff_info"


def test_trailing_whitespace():
    """trailing 模式：忽略行尾空格"""
    result = json.loads(compare_output("1 2 3  ", "1 2 3", mode="trailing"))
    assert result["status"] == "accepted", f"行尾空格应被忽略，实际: {result['status']}"


def test_trailing_newlines():
    """trailing 模式：忽略末尾空行"""
    result = json.loads(compare_output("1 2 3\n\n", "1 2 3", mode="trailing"))
    assert result["status"] == "accepted", f"末尾空行应被忽略，实际: {result['status']}"


def test_trailing_mixed():
    """trailing 模式：行尾空格 + 末尾空行混合（行首空格不在 trailing 模式处理）"""
    # trailing 模式去掉每行行尾空格和首尾空行，但保留行首空格
    # 输入带行尾空格，期望不带 → 应匹配
    result = json.loads(compare_output("hello  \nworld  \n", "hello\nworld", mode="trailing"))
    assert result["status"] == "accepted", f"行尾空白混合应被忽略，实际: {result['status']}"


def test_trailing_mismatch():
    """trailing 模式：内容不匹配不会被误判"""
    result = json.loads(compare_output("hello\nworld", "hello\npython", mode="trailing"))
    assert result["status"] == "wrong_answer", "内容不同应该是 wrong_answer"


def test_relaxed_match():
    """relaxed 模式：合并连续空白"""
    result = json.loads(compare_output("a   b\t\tc", "a b c", mode="relaxed"))
    assert result["status"] == "accepted", f"合并空白后应匹配，实际: {result['status']}"


def test_relaxed_mismatch():
    """relaxed 模式：内容不匹配"""
    result = json.loads(compare_output("a   b   c", "a b d", mode="relaxed"))
    assert result["status"] == "wrong_answer", "不同内容应是 wrong_answer"


def test_no_expected_output():
    """无期望输出"""
    result = json.loads(compare_output("1 2 3", "", mode="trailing"))
    assert result["status"] == "no_expected_output"
    assert result["diff_info"], "应有提示信息"


def test_whitespace_only_expected():
    """期望输出只有空白"""
    result = json.loads(compare_output("1 2 3", "   \n  ", mode="trailing"))
    assert result["status"] == "no_expected_output", "纯空白的期望输出应视为未提供"


def test_invalid_mode():
    """不支持的对比模式"""
    result = json.loads(compare_output("a", "a", mode="fuzzy"))
    assert result["status"] == "error", f"无效模式应返回 error，实际: {result['status']}"
    assert "fuzzy" in result.get("message", "")


def test_diff_info_single_line():
    """diff_info：单行差异定位"""
    result = json.loads(compare_output("apple\nbanana", "apple\ncherry", mode="trailing"))
    assert result["status"] == "wrong_answer"
    assert "第 2 行" in result["diff_info"], f"应定位第2行差异，实际: {result['diff_info']}"
    assert "banana" in result["diff_info"]
    assert "cherry" in result["diff_info"]


def test_diff_info_different_line_count():
    """diff_info：行数不一致"""
    result = json.loads(compare_output("a\nb\nc", "a\nb", mode="trailing"))
    assert result["status"] == "wrong_answer"
    assert "行数不一致" in result["diff_info"], f"应提示行数不一致，实际: {result['diff_info']}"


def test_normalized_fields():
    """normalized_stdout / normalized_expected 字段存在"""
    result = json.loads(compare_output(" test ", "test", mode="trailing"))
    assert "normalized_stdout" in result
    assert "normalized_expected" in result


def test_crlf_normalization():
    """\\r\\n 换行符应被标准化"""
    result = json.loads(compare_output("1\r\n2\r\n3", "1\n2\n3", mode="strict"))
    assert result["status"] == "accepted", "\\r\\n 应被标准化为 \\n"


def test_full_trim_leading_spaces():
    """full_trim 模式：忽略行首空格"""
    result = json.loads(compare_output("   1 2 3", "1 2 3", mode="full_trim"))
    assert result["status"] == "accepted", f"行首空格应被忽略，实际: {result['status']}"


def test_full_trim_trailing_spaces():
    """full_trim 模式：忽略行尾空格"""
    result = json.loads(compare_output("1 2 3   ", "1 2 3", mode="full_trim"))
    assert result["status"] == "accepted", f"行尾空格应被忽略，实际: {result['status']}"


def test_full_trim_both_sides():
    """full_trim 模式：行首+行尾空白均忽略，但行内空格保留"""
    result = json.loads(compare_output("  hello  world  ", "hello  world", mode="full_trim"))
    assert result["status"] == "accepted", f"首尾空白应被忽略，但行内空格保留，实际: {result['status']}"


def test_full_trim_empty_lines():
    """full_trim 模式：首尾空行被去掉"""
    result = json.loads(compare_output("\n\n1 2 3\n\n", "1 2 3", mode="full_trim"))
    assert result["status"] == "accepted", f"首尾空行应被忽略，实际: {result['status']}"


def test_full_trim_mismatch():
    """full_trim 模式：去空白后内容仍不同"""
    result = json.loads(compare_output("  hello  ", "  world  ", mode="full_trim"))
    assert result["status"] == "wrong_answer", "去首尾空白后内容不同应是 wrong_answer"


if __name__ == "__main__":
    test_strict_match()
    print("  [OK] test_strict_match")
    test_strict_mismatch()
    print("  [OK] test_strict_mismatch")
    test_trailing_whitespace()
    print("  [OK] test_trailing_whitespace")
    test_trailing_newlines()
    print("  [OK] test_trailing_newlines")
    test_trailing_mixed()
    print("  [OK] test_trailing_mixed")
    test_trailing_mismatch()
    print("  [OK] test_trailing_mismatch")
    test_relaxed_match()
    print("  [OK] test_relaxed_match")
    test_relaxed_mismatch()
    print("  [OK] test_relaxed_mismatch")
    test_no_expected_output()
    print("  [OK] test_no_expected_output")
    test_whitespace_only_expected()
    print("  [OK] test_whitespace_only_expected")
    test_invalid_mode()
    print("  [OK] test_invalid_mode")
    test_diff_info_single_line()
    print("  [OK] test_diff_info_single_line")
    test_diff_info_different_line_count()
    print("  [OK] test_diff_info_different_line_count")
    test_normalized_fields()
    print("  [OK] test_normalized_fields")
    test_crlf_normalization()
    print("  [OK] test_crlf_normalization")
    test_full_trim_leading_spaces()
    print("  [OK] test_full_trim_leading_spaces")
    test_full_trim_trailing_spaces()
    print("  [OK] test_full_trim_trailing_spaces")
    test_full_trim_both_sides()
    print("  [OK] test_full_trim_both_sides")
    test_full_trim_empty_lines()
    print("  [OK] test_full_trim_empty_lines")
    test_full_trim_mismatch()
    print("  [OK] test_full_trim_mismatch")
    print("\n[PASS] 第8章 compare_output 全部测试通过")
