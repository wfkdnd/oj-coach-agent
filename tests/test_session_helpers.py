"""测试 OJCoachSession 内部辅助函数。

oj_coach/session.py 中有 ~20 个内部函数负责测试用例的解析、规范化、
序列化和计数。这些函数是整个 OJ Coach 工作流的数据基础，

之前的测试只覆盖了约 30% 的 session 方法，这个文件补充对内部辅助函数
的独立单元测试。

注意：所有被测试的函数都是 oj_coach/session.py 中的模块级函数，
不是 OJCoachSession 的方法。
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from oj_coach.session import (
    # 文本提取 & 解析
    _extract_json_text,
    _normalize_llm_test_case_payload,
    _normalize_case_items,
    _parse_user_cases,
    _parse_user_cases_text,
    # 规范化 & 清理
    _normalize_case_text,
    _strip_explanation_tail,
    _replace_source,
    _set_case_source,
    # 序列化 & 计数
    _serialize_cases,
    _extract_cases_from_json_text,
    _count_cases,
    _count_runnable_cases_json,
    _count_cases_by_source,
    _count_runnable_problem_cases,
    # 工具函数
    _first_present,
    _looks_like_error,
    _clip,
    _session_result,
)
from oj_tools._shared import parse_case_heading, append_text

# ═══════════════════════════════════════════════════════════════
# _extract_json_text — 从 LLM 回复中提取 JSON
# ═══════════════════════════════════════════════════════════════

class TestExtractJsonText:
    """测试从各种 LLM 回复格式中提取 JSON 文本。"""

    def test_plain_json_object(self):
        text = '{"key": "value"}'
        result = _extract_json_text(text)
        assert result == '{"key": "value"}'

    def test_markdown_fenced_json(self):
        text = '```json\n{"a": 1}\n```'
        result = _extract_json_text(text)
        assert result == '{"a": 1}'

    def test_markdown_fenced_no_lang(self):
        text = '```\n{"b": 2}\n```'
        result = _extract_json_text(text)
        assert result == '{"b": 2}'

    def test_json_with_explanation_around(self):
        text = '这是分析结果：\n{"test": true}\n以上为 JSON'
        result = _extract_json_text(text)
        assert result == '{"test": true}'

    def test_json_array_of_objects_returns_complete_array(self):
        """对象数组必须保留外层 []，不能截取成其中的对象。"""
        text = '[{"name": "t1"}, {"name": "t2"}]'
        result = _extract_json_text(text)
        assert result == text

    def test_json_array_with_non_objects_works(self):
        """纯数字/字符串数组能正确提取。"""
        text = '结果：[1, 2, 3]'
        result = _extract_json_text(text)
        assert result == '[1, 2, 3]'

    def test_empty_string(self):
        assert _extract_json_text("") == ""

    def test_no_json(self):
        assert _extract_json_text("这是纯文本，没有 JSON") == ""

    def test_nested_json(self):
        text = '{"outer": {"inner": [1, 2, 3]}}'
        result = _extract_json_text(text)
        assert result == '{"outer": {"inner": [1, 2, 3]}}'

    def test_multiple_json_objects_takes_outermost(self):
        """多个 {} 块时取最外层的。"""
        text = '{"a": {"b": 1}}'
        result = _extract_json_text(text)
        assert result == '{"a": {"b": 1}}'


# ═══════════════════════════════════════════════════════════════
# _normalize_llm_test_case_payload — LLM 用例 JSON 规范化
# ═══════════════════════════════════════════════════════════════

class TestNormalizeLLMTestCasePayload:
    """测试 LLM 返回的用例 JSON 标准化。"""

    def test_standard_format(self):
        raw = json.dumps({
            "test_cases": [
                {"name": "示例1", "stdin": "1 2", "expected_output": "3"},
            ],
        })
        result = _normalize_llm_test_case_payload(raw)
        assert result is not None
        assert len(result["test_cases"]) == 1
        assert result["test_cases"][0]["stdin"] == "1 2"

    def test_flat_list_format(self):
        """顶层对象数组会被规范化为 test_cases。"""
        raw = json.dumps([
            {"stdin": "5 7", "expected_output": "12"},
        ])
        result = _normalize_llm_test_case_payload(raw)
        assert result is not None
        assert len(result["test_cases"]) == 1
        assert result["test_cases"][0]["expected_output"] == "12"

    def test_chinese_keys(self):
        """中文 key 的兼容性。"""
        raw = json.dumps({
            "测试用例": [
                {"名称": "样例1", "输入": "1", "输出": "2"},
            ],
        })
        result = _normalize_llm_test_case_payload(raw)
        assert result is not None
        assert len(result["test_cases"]) == 1
        assert result["test_cases"][0]["stdin"] == "1"

    def test_key_variants(self):
        """所有 key 变体都能正确映射。"""
        raw = json.dumps({
            "cases": [{"input": "3", "expected": "6"}],
        })
        result = _normalize_llm_test_case_payload(raw)
        assert result is not None
        assert result["test_cases"][0]["expected_output"] == "6"

    def test_invalid_json_returns_none(self):
        assert _normalize_llm_test_case_payload("这不是 JSON") is None

    def test_empty_payload_returns_none(self):
        assert _normalize_llm_test_case_payload("") is None

    def test_warnings_field(self):
        raw = json.dumps({
            "test_cases": [{"stdin": "1", "expected_output": "2"}],
            "warnings": "第3组样例无法解析",
        })
        result = _normalize_llm_test_case_payload(raw)
        assert result is not None
        assert len(result["warnings"]) == 1

    def test_warnings_as_list(self):
        raw = json.dumps({
            "test_cases": [],
            "warnings": ["警告1", "警告2"],
        })
        result = _normalize_llm_test_case_payload(raw)
        assert result is not None
        assert len(result["warnings"]) == 2

    def test_non_dict_payload_returns_none(self):
        assert _normalize_llm_test_case_payload('"just a string"') is None


# ═══════════════════════════════════════════════════════════════
# _normalize_case_items — 用例列表规范化
# ═══════════════════════════════════════════════════════════════

class TestNormalizeCaseItems:
    """测试原始用例数据标准化。"""

    def test_standard_items(self):
        raw = [
            {"name": "t1", "stdin": "1", "expected_output": "2", "source": "题目"},
        ]
        result = _normalize_case_items(raw, default_source="题目")
        assert len(result) == 1
        assert result[0]["name"] == "t1"
        assert result[0]["source"] == "题目"

    def test_skip_non_dict(self):
        raw = ["not a dict", {"stdin": "1", "expected_output": "2"}]
        result = _normalize_case_items(raw, default_source="题目")
        assert len(result) == 1

    def test_skip_empty_cases(self):
        raw = [{"name": "empty", "stdin": "", "expected_output": ""}]
        result = _normalize_case_items(raw, default_source="题目")
        assert len(result) == 0

    def test_accept_output_only_case(self):
        raw = [{"name": "no-input", "stdin": "", "expected_output": "YES"}]
        result = _normalize_case_items(raw, default_source="题目")
        assert len(result) == 1
        assert result[0]["stdin"] == ""

    def test_default_name_and_source(self):
        """_normalize_case_items 的默认名称格式为 '示例 N'。"""
        raw = [{"stdin": "1", "expected_output": "2"}]
        result = _normalize_case_items(raw, default_source="LLM")
        assert result[0]["name"] == "示例 1"
        assert result[0]["source"] == "LLM"

    def test_auto_numbering_names(self):
        raw = [
            {"stdin": "a", "expected_output": "A"},
            {"stdin": "b", "expected_output": "B"},
        ]
        result = _normalize_case_items(raw, default_source="题目")
        assert result[0]["name"] == "示例 1"
        assert result[1]["name"] == "示例 2"


# ═══════════════════════════════════════════════════════════════
# _parse_user_cases — 用户用例解析
# ═══════════════════════════════════════════════════════════════

class TestParseUserCases:
    """测试用户输入的测试用例解析。"""

    def test_json_array_format(self):
        """前端或 API 直接提交对象数组时也能正常识别。"""
        text = json.dumps([
            {"stdin": "1 2", "expected_output": "3"},
        ])
        result = _parse_user_cases(text)
        assert len(result) == 1
        assert result[0]["expected_output"] == "3"

    def test_json_object_format_works(self):
        """标准 JSON 对象格式（有 test_cases key）。"""
        text = json.dumps({
            "test_cases": [
                {"stdin": "1 2", "expected_output": "3"},
            ],
        })
        result = _parse_user_cases(text)
        assert len(result) == 1
        assert result[0]["source"] == "用户"

    def test_text_format_simple(self):
        text = "输入：\n1 2\n输出：\n3"
        result = _parse_user_cases(text)
        assert len(result) == 1
        assert result[0]["stdin"] == "1 2"
        assert result[0]["expected_output"] == "3"

    def test_text_format_multiple_cases(self):
        text = (
            "输入：\n1 2\n输出：\n3\n"
            "---\n"
            "输入：\n5 7\n输出：\n12\n"
            "---\n"
            "输入：\n0 0\n输出：\n0"
        )
        result = _parse_user_cases(text)
        assert len(result) == 3
        assert result[1]["stdin"] == "5 7"

    def test_text_format_separator_equals(self):
        text = "输入：\nhello\n输出：\nworld\n===\n输入：\nfoo\n输出：\nbar"
        result = _parse_user_cases(text)
        assert len(result) == 2

    def test_text_format_no_separator_single_case(self):
        text = "输入：\ntest\n输出：\nresult"
        result = _parse_user_cases(text)
        assert len(result) == 1

    def test_incomplete_case_rejected(self):
        """只有输入没有输出的用例会被过滤。"""
        text = "输入：\nonly input"
        result = _parse_user_cases(text)
        assert len(result) == 0

    def test_output_only_case_accepted(self):
        result = _parse_user_cases("输出：\nYES")
        assert len(result) == 1
        assert result[0]["stdin"] == ""
        assert result[0]["expected_output"] == "YES"

    def test_colon_format(self):
        """英文冒号格式。"""
        text = "Input:\n1\nOutput:\n2"
        result = _parse_user_cases(text)
        assert len(result) == 1
        assert result[0]["stdin"] == "1"
        assert result[0]["expected_output"] == "2"


# ═══════════════════════════════════════════════════════════════
# _parse_user_cases_text — 纯文本格式解析
# ═══════════════════════════════════════════════════════════════

class TestParseUserCasesText:
    """测试纯文本格式的用户用例解析。"""

    def test_single_case(self):
        text = "输入：\n1 2\n输出：\n3"
        result = _parse_user_cases_text(text)
        assert len(result) == 1
        assert result[0]["stdin"] == "1 2"
        assert result[0]["expected_output"] == "3"

    def test_multiline_stdin(self):
        text = "输入：\n1 2\n3 4\n输出：\n5\n7"
        result = _parse_user_cases_text(text)
        assert len(result) == 1
        assert result[0]["stdin"] == "1 2\n3 4"

    def test_heading_with_inline_value(self):
        """标题同行有值。"""
        text = "输入：1 2\n输出：3"
        result = _parse_user_cases_text(text)
        assert len(result) == 1
        assert result[0]["stdin"] == "1 2"
        assert result[0]["expected_output"] == "3"

    def test_heading_with_hash(self):
        """带 # 的标题。"""
        text = "# 输入：\n1\n# 输出：\n2"
        result = _parse_user_cases_text(text)
        assert len(result) == 1

    def test_empty_input(self):
        assert _parse_user_cases_text("") == []

    def test_input_only_no_output(self):
        text = "输入：\n1"
        result = _parse_user_cases_text(text)
        # 只有输入、没有期望输出的用例无法校验结果。
        assert result == []

    def test_output_only_without_input(self):
        result = _parse_user_cases_text("输出：\nYES")
        assert len(result) == 1
        assert result[0]["stdin"] == ""
        assert result[0]["expected_output"] == "YES"

    def test_case_with_auto_numbering(self):
        text = "输入：\na\n输出：\nb\n---\n输入：\nc\n输出：\nd"
        result = _parse_user_cases_text(text)
        assert result[0]["name"] == "用户用例 1"
        assert result[1]["name"] == "用户用例 2"


# ═══════════════════════════════════════════════════════════════
# _parse_case_heading — 标题解析
# ═══════════════════════════════════════════════════════════════

class TestParseCaseHeading:
    def test_chinese_stdin(self):
        key, val = parse_case_heading("输入：1 2")
        assert key == "stdin"
        assert val == "1 2"

    def test_chinese_output(self):
        key, val = parse_case_heading("输出：3")
        assert key == "expected_output"
        assert val == "3"

    def test_english_stdin(self):
        key, val = parse_case_heading("stdin: 1")
        assert key == "stdin"

    def test_english_expected(self):
        key, val = parse_case_heading("expected_output: 2")
        assert key == "expected_output"

    def test_non_heading(self):
        key, val = parse_case_heading("just text")
        assert key == ""
        assert val == ""

    def test_heading_without_colon(self):
        key, val = parse_case_heading("input")
        # "input" 本身可能匹配 stdin → 取决于 parse_case_heading 逻辑
        # 但 heading 是整行，没有冒号时 raw_heading="input", inline_value=""
        # heading = "input".strip().lower() = "input" → 匹配 stdin
        assert key == "stdin"
        assert val == ""

    def test_heading_with_hash_prefix(self):
        key, val = parse_case_heading("### 输入：1 2")
        assert key == "stdin"
        assert val == "1 2"


# ═══════════════════════════════════════════════════════════════
# _normalize_case_text — 文本规范化
# ═══════════════════════════════════════════════════════════════

class TestNormalizeCaseText:
    def test_trims_blank_lines(self):
        assert _normalize_case_text("\n\n  hello  \n\n") == "  hello"

    def test_strips_trailing_spaces(self):
        assert _normalize_case_text("hello   \nworld   ") == "hello\nworld"

    def test_handles_crlf(self):
        assert _normalize_case_text("a\r\nb\r\nc") == "a\nb\nc"

    def test_handles_cr(self):
        assert _normalize_case_text("a\rb\rc") == "a\nb\nc"

    def test_preserves_inner_blank_lines(self):
        assert _normalize_case_text("a\n\nb") == "a\n\nb"

    def test_empty_string(self):
        assert _normalize_case_text("") == ""

    def test_single_line(self):
        assert _normalize_case_text("hello") == "hello"


# ═══════════════════════════════════════════════════════════════
# _strip_explanation_tail — 去除解释尾部
# ═══════════════════════════════════════════════════════════════

class TestStripExplanationTail:
    def test_cuts_at_explanation_heading_separate_line(self):
        """解释标题需独占一行才会被识别。"""
        text = "1 2 3\n解释：\n这是解释内容"
        result = _strip_explanation_tail(text)
        assert result == "1 2 3"

    def test_does_not_cut_with_inline_explanation(self):
        """标题后跟 inline 内容时不被识别（如 '解释：这是解释' 同一行）。"""
        text = "1 2 3\n解释：这是解释"
        result = _strip_explanation_tail(text)
        # "解释：这是解释" 不被当成 heading → 全文保留
        assert "解释：这是解释" in result

    def test_cuts_at_note_separate_line(self):
        text = "output\n备注：\n额外信息"
        result = _strip_explanation_tail(text)
        assert result == "output"

    def test_no_explanation_preserves_all(self):
        text = "1 2 3\n4 5 6"
        result = _strip_explanation_tail(text)
        assert result == "1 2 3\n4 5 6"

    def test_english_explanation_separate_line(self):
        text = "result\nexplanation:\ndetails"
        result = _strip_explanation_tail(text)
        assert result == "result"

    def test_constraints_separate_line(self):
        text = "output\n约束：\nn <= 1000"
        result = _strip_explanation_tail(text)
        assert result == "output"

    def test_multiple_headings_stops_at_first(self):
        """多个解释标题：第一条匹配即停止。"""
        text = "out\n说明：\nxxx\n提示：\nyyy"
        result = _strip_explanation_tail(text)
        assert "yyy" not in result
        assert result == "out"

    def test_empty_string(self):
        assert _strip_explanation_tail("") == ""


# ═══════════════════════════════════════════════════════════════
# _replace_source & _set_case_source — 来源标记
# ═══════════════════════════════════════════════════════════════

class TestReplaceSource:
    def test_replaces_all_sources(self):
        cases = [
            {"stdin": "1", "expected_output": "2", "source": "题目"},
            {"stdin": "3", "expected_output": "4", "source": "题目"},
        ]
        result = _replace_source(cases, "用户")
        assert all(c["source"] == "用户" for c in result)


class TestSetCaseSource:
    def test_sets_source_and_normalizes(self):
        cases = [
            {"stdin": " 1 ", "expected_output": " 2 "},
        ]
        result = _set_case_source(cases, "用户")
        assert result[0]["source"] == "用户"
        # _normalize_case_text 去除首尾空行和行尾空格，但保留行首空格
        assert result[0]["stdin"] == " 1"
        assert result[0]["expected_output"] == " 2"

    def test_accepts_output_only_cases(self):
        cases = [
            {"stdin": "", "expected_output": "2"},
            {"stdin": "1", "expected_output": "2"},
        ]
        result = _set_case_source(cases, "题目")
        assert len(result) == 2
        assert result[0]["stdin"] == ""


# ═══════════════════════════════════════════════════════════════
# _serialize_cases & _extract_cases_from_json_text
# ═══════════════════════════════════════════════════════════════

class TestSerializeCases:
    def test_roundtrip(self):
        cases = [
            {"name": "t1", "source": "题目", "stdin": "1", "expected_output": "2"},
            {"name": "u1", "source": "用户", "stdin": "3", "expected_output": "4"},
        ]
        json_str = _serialize_cases(cases)
        parsed = json.loads(json_str)
        assert parsed["test_cases"][0]["stdin"] == "1"
        assert parsed["test_cases"][1]["source"] == "用户"

    def test_empty_list(self):
        assert _serialize_cases([]) == ""

    def test_filters_incomplete(self):
        cases = [
            {"name": "empty", "source": "x", "stdin": "", "expected_output": ""},
            {"name": "no-input", "source": "x", "stdin": "", "expected_output": "YES"},
            {"name": "good", "source": "x", "stdin": "1", "expected_output": "2"},
        ]
        json_str = _serialize_cases(cases)
        parsed = json.loads(json_str)
        assert len(parsed["test_cases"]) == 2


class TestExtractCasesFromJsonText:
    def test_valid_json_returns_cases(self):
        text = json.dumps({"test_cases": [{"stdin": "1", "expected_output": "2"}]})
        result = _extract_cases_from_json_text(text)
        assert len(result) == 1

    def test_invalid_json_returns_empty(self):
        assert _extract_cases_from_json_text("not json") == []

    def test_json_without_test_cases(self):
        assert _extract_cases_from_json_text('{"other": "data"}') == []


# ═══════════════════════════════════════════════════════════════
# 各种计数函数
# ═══════════════════════════════════════════════════════════════

class TestCountFunctions:
    def test_count_cases(self):
        cases = [
            {"stdin": "1", "expected_output": "2"},
            {"stdin": "", "expected_output": "2"},
            {"stdin": "3", "expected_output": ""},
            {"stdin": "5", "expected_output": "6"},
        ]
        assert _count_cases(cases) == 3  # 第2组无需输入，也可按期望输出校验

    def test_count_cases_empty(self):
        assert _count_cases([]) == 0

    def test_count_runnable_cases_json(self):
        json_str = json.dumps({
            "test_cases": [
                {"stdin": "1", "expected_output": "2"},
                {"stdin": "", "expected_output": "3"},
                {"stdin": "4", "expected_output": "5"},
            ],
        })
        assert _count_runnable_cases_json(json_str) == 3

    def test_count_runnable_cases_empty_json(self):
        assert _count_runnable_cases_json("") == 0

    def test_count_cases_by_source(self):
        json_str = json.dumps({
            "test_cases": [
                {"stdin": "1", "expected_output": "2", "source": "题目"},
                {"stdin": "3", "expected_output": "4", "source": "题目"},
                {"stdin": "5", "expected_output": "6", "source": "用户"},
            ],
        })
        counts = _count_cases_by_source(json_str)
        assert counts == {"题目": 2, "用户": 1}

    def test_count_cases_by_source_empty(self):
        assert _count_cases_by_source("") == {}

    def test_count_runnable_problem_cases(self):
        analysis = json.dumps({
            "测试用例": [
                {"stdin": "1", "expected_output": "2"},
                {"stdin": "3", "expected_output": "4"},
                {"stdin": "", "expected_output": "5"},
            ],
        })
        assert _count_runnable_problem_cases(analysis) == 3

    def test_count_runnable_problem_cases_invalid_json(self):
        assert _count_runnable_problem_cases("not json") == 0

    def test_count_runnable_problem_cases_no_cases_key(self):
        analysis = json.dumps({"other": "data"})
        assert _count_runnable_problem_cases(analysis) == 0


# ═══════════════════════════════════════════════════════════════
# _first_present — 多 key 查找
# ═══════════════════════════════════════════════════════════════

class TestFirstPresent:
    def test_first_key_matches(self):
        d = {"a": 1, "b": 2, "c": 3}
        assert _first_present(d, ("a", "b", "c")) == 1

    def test_second_key_matches(self):
        d = {"b": 2, "c": 3}
        assert _first_present(d, ("a", "b", "c")) == 2

    def test_no_key_matches(self):
        d = {"x": 1}
        assert _first_present(d, ("a", "b")) is None

    def test_empty_dict(self):
        assert _first_present({}, ("a",)) is None

    def test_none_value_is_returned(self):
        """值为 None 也正常返回（不会跳过）。"""
        d = {"a": None, "b": 2}
        assert _first_present(d, ("a", "b")) is None


# ═══════════════════════════════════════════════════════════════
# _append_text — 文本拼接
# ═══════════════════════════════════════════════════════════════

class TestAppendText:
    def test_append_to_empty(self):
        assert append_text("", "hello") == "hello"

    def test_append_to_existing(self):
        assert append_text("line1", "line2") == "line1\nline2"


# ═══════════════════════════════════════════════════════════════
# _looks_like_error — 错误检测
# ═══════════════════════════════════════════════════════════════

class TestLooksLikeError:
    def test_chinese_error(self):
        assert _looks_like_error("错误：文件不存在") is True

    def test_chinese_exec_error(self):
        assert _looks_like_error("执行错误：超时") is True

    def test_english_error(self):
        assert _looks_like_error("error: file not found") is True

    def test_english_capitalized(self):
        assert _looks_like_error("ERROR: something") is True

    def test_normal_result_is_not_error(self):
        assert _looks_like_error("运行成功") is False

    def test_json_is_not_error(self):
        assert _looks_like_error('{"status": "ok"}') is False

    def test_unknown_tool_prefix(self):
        assert _looks_like_error("未知工具：invalid_tool") is True


# ═══════════════════════════════════════════════════════════════
# _clip — 文本截断
# ═══════════════════════════════════════════════════════════════

class TestClip:
    def test_short_text_unchanged(self):
        text = "hello"
        assert _clip(text, limit=100) == "hello"

    def test_long_text_clipped(self):
        text = "a" * 200
        result = _clip(text, limit=100)
        assert len(result) < len(text)
        assert "截断" in result

    def test_empty_text(self):
        assert _clip("") == "（空）"

    def test_exact_limit(self):
        text = "a" * 50
        result = _clip(text, limit=50)
        assert result == text


# ═══════════════════════════════════════════════════════════════
# _session_result — 结果字典构建
# ═══════════════════════════════════════════════════════════════

class TestSessionResult:
    def test_basic_structure(self):
        result = _session_result(True, ["msg1", "msg2"])
        assert result["ok"] is True
        assert result["messages"] == ["msg1", "msg2"]

    def test_with_extra_fields(self):
        result = _session_result(False, ["error"], run_result="{}")
        assert result["ok"] is False
        assert result["run_result"] == "{}"

    def test_empty_messages(self):
        result = _session_result(True, [])
        assert result["ok"] is True
        assert result["messages"] == []

    def test_multiple_extra_kwargs(self):
        result = _session_result(
            True, [],
            analysis_result="{}",
            run_result="{}",
            extra_field="extra",
        )
        assert result["analysis_result"] == "{}"
        assert result["run_result"] == "{}"
        assert result["extra_field"] == "extra"
