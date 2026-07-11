"""OJ Coach 可复用状态和编排层。

终端界面只负责读取命令和渲染结果。这个模块负责维护会话状态，
并调用确定性的 OJ 工具以及可选的 LLM 辅助能力。
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Callable, Iterator

from oj_tools import build_oj_tools
from oj_coach.prompts import (
    OJ_COACH_SYSTEM_PROMPT,
    TEST_CASE_EXTRACT_SYSTEM_PROMPT,
    TEST_CASE_EXTRACT_USER_PROMPT,
)


DEFAULT_TIMEOUT_MS = 3000
MAX_CONTEXT_CHARS = 6000


@dataclass
class OJCoachState:
    problem_text: str = ""
    language: str = ""
    code: str = ""
    test_cases: str = ""
    last_run_result: str = ""
    analysis_result: str = ""
    timeout_ms: int = DEFAULT_TIMEOUT_MS


class OJCoachSession:
    """终端和后续前端共享的有状态 OJ Coach 工作流接口。"""

    def __init__(
        self,
        tools: Any | None = None,
        llm_factory: Callable[[], Any | None] | None = None,
        context_provider: Callable[[str], str] | None = None,
        auto_extract_with_llm: bool = True,
        auto_run: bool = True,
    ):
        self.state = OJCoachState()
        self.tools = tools or build_oj_tools()
        self.llm_factory = llm_factory or _default_llm_factory
        self.context_provider = context_provider
        self.auto_extract_with_llm = auto_extract_with_llm
        self.auto_run = auto_run

    def set_problem_text(self, problem_text: str) -> dict[str, Any]:
        messages: list[str] = []
        result = self._invoke_oj_tool("read_problem", {"problem_text": problem_text})
        if _looks_like_error(result):
            return _session_result(False, [result])

        self.state.problem_text = result
        self.state.analysis_result = ""
        self._replace_cases_by_source("题目", [])
        messages.append(f"已读取题目文本，共 {len(self.state.problem_text)} 个字符。")
        self._analyze_problem_core(messages)
        self._extract_problem_test_cases(messages)
        run_result = self._maybe_auto_run("题目已更新", messages)
        return _session_result(
            True,
            messages,
            analysis_result=self.state.analysis_result,
            run_result=run_result,
        )

    def load_problem_file(self, file_path: str) -> dict[str, Any]:
        messages: list[str] = []
        result = self._invoke_oj_tool("read_problem_file", {"file_path": file_path})
        if _looks_like_error(result):
            return _session_result(False, [result])

        self.state.problem_text = result
        self.state.analysis_result = ""
        self._replace_cases_by_source("题目", [])
        messages.append(f"已读取题目文件，共 {len(self.state.problem_text)} 个字符。")
        self._analyze_problem_core(messages)
        self._extract_problem_test_cases(messages)
        run_result = self._maybe_auto_run("题目已更新", messages)
        return _session_result(
            True,
            messages,
            analysis_result=self.state.analysis_result,
            run_result=run_result,
        )

    def analyze_problem(self) -> dict[str, Any]:
        messages: list[str] = []
        if not self._analyze_problem_core(messages):
            return _session_result(False, messages)

        self._extract_problem_test_cases(messages)
        run_result = self._maybe_auto_run("题目分析已更新", messages)
        return _session_result(
            True,
            messages,
            analysis_result=self.state.analysis_result,
            run_result=run_result,
        )

    def set_code(self, code_text: str, language: str) -> dict[str, Any]:
        raw_result = self._invoke_oj_tool(
            "read_code",
            {"code_text": code_text, "language": language},
        )
        messages: list[str] = []
        if not self._apply_code_payload(raw_result, messages):
            return _session_result(False, messages)

        run_result = self._maybe_auto_run("代码已更新", messages)
        return _session_result(True, messages, run_result=run_result)

    def load_code_file(self, file_path: str) -> dict[str, Any]:
        raw_result = self._invoke_oj_tool("read_code_file", {"file_path": file_path})
        messages: list[str] = []
        if not self._apply_code_payload(raw_result, messages):
            return _session_result(False, messages)

        run_result = self._maybe_auto_run("代码已更新", messages)
        return _session_result(True, messages, run_result=run_result)

    def add_cases(self, raw_cases: str) -> dict[str, Any]:
        user_cases = _parse_user_cases(raw_cases)
        if not user_cases:
            return _session_result(
                False,
                ["没有识别到可运行测试用例，请确认每组用例同时包含输入和期望输出。"],
            )

        existing_cases = _extract_cases_from_json_text(self.state.test_cases)
        self.state.test_cases = _serialize_cases(existing_cases + user_cases)
        message = (
            f"已添加 {len(user_cases)} 组用户测试用例；当前共有 "
            f"{_count_runnable_cases_json(self.state.test_cases)} 组可运行用例。"
        )
        return _session_result(True, [message])

    def set_timeout(self, timeout_ms: int | str) -> dict[str, Any]:
        try:
            value = int(timeout_ms)
        except (TypeError, ValueError):
            return _session_result(False, ["错误：timeout_ms 必须是整数。"])

        if value <= 0:
            return _session_result(False, ["错误：timeout_ms 必须大于 0。"])

        self.state.timeout_ms = value
        return _session_result(True, [f"已设置超时时间：{self.state.timeout_ms}ms。"])

    def run_code(self) -> dict[str, Any]:
        if not self.state.code.strip():
            return _session_result(False, ["请先使用 /paste_code 或 /load_code 读取完整 OJ 代码。"])
        if not self.state.language.strip() or self.state.language == "未知":
            return _session_result(False, ["请先提供代码语言，例如 /paste_code python 或 /load_code main.cpp。"])

        messages = ["正在运行当前代码..."]
        result = self._run_current_code()
        self.state.last_run_result = result
        explanation = self.explain_last_run()
        return _session_result(True, messages, run_result=result, llm_explanation=explanation)

    def ask(self, question: str) -> dict[str, Any]:
        question = question.strip()
        if not question:
            return _session_result(False, ["问题为空，已取消。"])

        llm = self._try_create_llm()
        if llm is None:
            return _session_result(
                False,
                [
                    "当前未能初始化 LLM。请确认 BASE_URL / API_KEY / MODEL_ID 已配置。",
                    "你仍然可以使用 /run 查看真实运行结果，或使用 /summary 生成规则版复盘。",
                ],
            )

        messages = [
            {"role": "system", "content": OJ_COACH_SYSTEM_PROMPT},
            {"role": "user", "content": self.build_question_context(question)},
        ]
        try:
            answer = llm.chat(messages)
        except Exception as exc:
            return _session_result(False, [f"LLM 回答生成失败：{exc}"])
        return _session_result(True, [], answer=answer)

    def ask_stream(self, question: str) -> Iterator[str]:
        """为支持增量输出的界面流式返回回答。"""
        question = question.strip()
        if not question:
            yield "问题为空，已取消。"
            return

        llm = self._try_create_llm()
        if llm is None:
            yield "当前未能初始化 LLM。请确认 BASE_URL / API_KEY / MODEL_ID 已配置。"
            return

        messages = [
            {"role": "system", "content": OJ_COACH_SYSTEM_PROMPT},
            {"role": "user", "content": self.build_question_context(question)},
        ]
        try:
            for chunk in llm.chat_stream(messages):
                yield chunk
        except Exception as exc:
            yield f"\n（LLM 回答生成失败：{exc}）"

    def summarize(self, notes: str = "") -> dict[str, Any]:
        if not self.state.problem_text.strip():
            return _session_result(False, ["请先使用 /paste_problem 或 /load_problem 读取题目。"])
        if not self.state.code.strip():
            return _session_result(False, ["请先使用 /paste_code 或 /load_code 读取代码。"])
        if not self.state.last_run_result.strip():
            return _session_result(False, ["请先使用 /run 运行一次代码，再做复盘。"])

        summary_result = self._invoke_oj_tool(
            "summarize_practice",
            {
                "problem_text": self.state.problem_text,
                "code": self.state.code,
                "run_result": self.state.last_run_result,
                "notes": notes,
            },
        )
        llm_summary = self.explain_summary(summary_result, notes)
        return _session_result(True, [], rule_summary=summary_result, llm_summary=llm_summary)

    def status(self) -> dict[str, Any]:
        source_counts = _count_cases_by_source(self.state.test_cases)
        return {
            "problem_text_set": bool(self.state.problem_text.strip()),
            "problem_text_chars": len(self.state.problem_text),
            "analysis_result_set": bool(self.state.analysis_result.strip()),
            "language": self.state.language or "未设置",
            "code_set": bool(self.state.code.strip()),
            "code_chars": len(self.state.code),
            "test_cases_set": bool(self.state.test_cases.strip()),
            "runnable_case_count": _count_runnable_cases_json(self.state.test_cases),
            "test_case_sources": source_counts,
            "last_run_result_set": bool(self.state.last_run_result.strip()),
            "timeout_ms": self.state.timeout_ms,
        }

    def explain_last_run(self) -> str:
        if not self.state.last_run_result.strip():
            return ""

        llm = self._try_create_llm()
        if llm is None:
            return ""

        messages = [
            {"role": "system", "content": OJ_COACH_SYSTEM_PROMPT},
            {"role": "user", "content": self.build_run_analysis_prompt()},
        ]
        try:
            return llm.chat(messages)
        except Exception as exc:
            return f"（LLM 解释生成失败：{exc}）"

    def explain_summary(self, summary_result: str, notes: str = "") -> str:
        llm = self._try_create_llm()
        if llm is None:
            return ""

        messages = [
            {"role": "system", "content": OJ_COACH_SYSTEM_PROMPT},
            {"role": "user", "content": self.build_summary_explanation_prompt(summary_result, notes)},
        ]
        try:
            return llm.chat(messages)
        except Exception as exc:
            return f"（LLM 复盘讲解生成失败：{exc}）"

    def build_question_context(self, question: str) -> str:
        if self.context_provider is not None:
            try:
                provided_context = self.context_provider(question)
            except Exception:
                provided_context = ""
            if provided_context.strip():
                return provided_context

        return f"""\
用户问题：
{question}

当前代码：
{_clip(self.state.code)}

最近一次 run_oj_code 结果：
{_clip(self.state.last_run_result)}

题目分析：
{_clip(self.state.analysis_result)}
"""

    def build_run_analysis_prompt(self) -> str:
        return f"""\
请基于下面三部分上下文分析运行结果并给出调试建议：

题目分析：
{_clip(self.state.analysis_result)}

当前代码：
{_clip(self.state.code, limit=MAX_CONTEXT_CHARS * 2)}

最近一次 run_oj_code 结果：
{_clip(self.state.last_run_result)}

请根据以上信息：
1. 如果运行出错（compile_error / runtime_error / time_limit_exceeded / wrong_answer），请具体指出错误原因和修复方向
2. 如果运行通过（accepted），可以给出代码优化建议或考察的知识点总结
3. 不要直接给出完整代码，而是引导用户自己思考和修改
"""

    def build_summary_explanation_prompt(self, summary_result: str, notes: str = "") -> str:
        return f"""\
请把下面的规则版复盘总结翻译成适合刷题者理解的自然语言讲解。

要求：
1. 先说明这题主要考察什么，以及应该抓住的关键观察。
2. 再说明当前代码和运行状态，重点解释错误原因或通过原因。
3. 如果有错误，只给定位思路和修改方向，不要直接给完整代码。
4. 最后总结下次遇到类似题时的识别信号。
5. 不要捏造运行结果；所有结论都必须来自下面的上下文。

用户备注：
{notes or "（无）"}

规则版复盘总结：
{_clip(summary_result)}

最近一次真实运行结果：
{_clip(self.state.last_run_result)}

题目分析：
{_clip(self.state.analysis_result)}

当前题目：
{_clip(self.state.problem_text)}

当前语言：{self.state.language or "未设置"}

当前代码：
{_clip(self.state.code, limit=MAX_CONTEXT_CHARS * 2)}
"""

    def _analyze_problem_core(self, messages: list[str]) -> bool:
        if not self.state.problem_text.strip():
            messages.append("请先使用 /paste_problem 或 /load_problem 读取题目。")
            return False

        messages.append("正在自动分析题目...")
        result = self._invoke_oj_tool("analyze_problem", {"problem_text": self.state.problem_text})
        if _looks_like_error(result):
            messages.append(result)
            return False

        self.state.analysis_result = result
        sample_count = _count_runnable_problem_cases(result)
        if sample_count:
            messages.append(f"自动分析完成，提取到 {sample_count} 组可运行题目样例。")
        else:
            messages.append("自动分析完成，但没有提取到可直接运行的题目样例。")
        return True

    def _extract_problem_test_cases(self, messages: list[str]) -> bool:
        if not self.state.problem_text.strip():
            return False
        if not self.auto_extract_with_llm:
            return self._extract_problem_test_cases_from_analysis(messages)

        llm = self._try_create_llm()
        if llm is None:
            messages.append("LLM 样例提取不可用，将保留现有规则提取/手动用例流程。")
            return self._extract_problem_test_cases_from_analysis(messages)

        messages.append("正在用 LLM 提取题目样例 JSON...")
        llm_messages = [
            {"role": "system", "content": TEST_CASE_EXTRACT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": TEST_CASE_EXTRACT_USER_PROMPT.format(problem_text=self.state.problem_text),
            },
        ]
        try:
            raw_result = llm.chat(llm_messages, temperature=0)
        except Exception as exc:
            messages.append(f"LLM 样例提取失败，将回退到规则提取：{exc}")
            return self._extract_problem_test_cases_from_analysis(messages)

        payload = _normalize_llm_test_case_payload(raw_result)
        if payload is None:
            messages.append("LLM 返回的样例不是合法 JSON，将回退到规则提取。")
            return self._extract_problem_test_cases_from_analysis(messages)

        problem_cases = _set_case_source(payload.get("test_cases", []), "题目")
        self._replace_cases_by_source("题目", problem_cases)
        sample_count = _count_cases(problem_cases)
        warnings = payload.get("warnings") or []
        if sample_count:
            messages.append(f"LLM 样例提取完成，得到 {sample_count} 组可运行样例。")
        else:
            messages.append("LLM 样例提取完成，但没有得到可运行样例。")
        if warnings:
            messages.append("LLM 样例提取提示：" + "；".join(str(item) for item in warnings))
        return sample_count > 0

    def _extract_problem_test_cases_from_analysis(self, messages: list[str]) -> bool:
        try:
            payload = json.loads(self.state.analysis_result)
        except json.JSONDecodeError:
            return False

        raw_cases = payload.get("测试用例", [])
        if not isinstance(raw_cases, list):
            return False

        problem_cases = _set_case_source(_normalize_case_items(raw_cases, default_source="题目"), "题目")
        self._replace_cases_by_source("题目", problem_cases)
        sample_count = _count_cases(problem_cases)
        if sample_count:
            messages.append(f"已从规则分析结果补充 {sample_count} 组题目样例。")
        return sample_count > 0

    def _maybe_auto_run(self, reason: str, messages: list[str]) -> str:
        if not self.auto_run:
            return ""
        if not self.state.code.strip():
            return ""
        if not self.state.language.strip() or self.state.language == "未知":
            return ""
        if not self.state.problem_text.strip() or not self.state.analysis_result.strip():
            return ""

        sample_count = _count_runnable_cases_json(self.state.test_cases)
        if sample_count <= 0:
            return ""

        messages.append(f"检测到{reason}，将自动运行 {sample_count} 组测试用例...")
        result = self._run_current_code()
        self.state.last_run_result = result
        return result

    def _run_current_code(self) -> str:
        return self._invoke_oj_tool(
            "run_oj_code",
            {
                "language": self.state.language,
                "code": self.state.code,
                "stdin": "",
                "expected_output": "",
                "timeout_ms": self.state.timeout_ms,
                "problem_text": "",
                "test_cases": self.state.test_cases,
            },
        )

    def _apply_code_payload(self, raw_result: str, messages: list[str]) -> bool:
        if _looks_like_error(raw_result):
            messages.append(raw_result)
            return False

        try:
            payload = json.loads(raw_result)
        except json.JSONDecodeError:
            messages.append(f"错误：读取代码结果不是 JSON：{raw_result}")
            return False

        code = str(payload.get("code", ""))
        language = str(payload.get("language", ""))
        if not code.strip():
            messages.append("错误：读取到的代码为空。")
            return False

        self.state.code = code
        self.state.language = language
        self.state.last_run_result = ""
        messages.append(f"已读取 {language} 代码，共 {len(self.state.code)} 个字符。")
        return True

    def _replace_cases_by_source(self, source: str, replacement_cases: list[dict[str, str]]) -> None:
        existing_cases = _extract_cases_from_json_text(self.state.test_cases)
        kept_cases = [case for case in existing_cases if case.get("source") != source]
        self.state.test_cases = _serialize_cases(kept_cases + _set_case_source(replacement_cases, source))

    def _invoke_oj_tool(self, name: str, args: dict[str, Any]) -> str:
        return self.tools.invoke(name, args)

    def _try_create_llm(self):
        try:
            return self.llm_factory()
        except Exception:
            return None


def _session_result(ok: bool, messages: list[str], **extra: Any) -> dict[str, Any]:
    return {"ok": ok, "messages": messages, **extra}


def _default_llm_factory():
    try:
        from llm import LLMClient

        return LLMClient()
    except Exception:
        return None


def _normalize_llm_test_case_payload(raw_result: str, default_source: str = "题目") -> dict[str, Any] | None:
    json_text = _extract_json_text(raw_result)
    if not json_text:
        return None

    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError:
        return None

    if isinstance(payload, list):
        payload = {"test_cases": payload}
    if not isinstance(payload, dict):
        return None

    raw_cases = _first_present(payload, ("test_cases", "cases", "测试用例", "样例"))
    if not isinstance(raw_cases, list):
        raw_cases = []

    warnings = payload.get("warnings", [])
    if isinstance(warnings, str):
        warnings = [warnings]
    elif not isinstance(warnings, list):
        warnings = []

    return {
        "test_cases": _normalize_case_items(raw_cases, default_source=default_source),
        "warnings": [str(item) for item in warnings],
    }


def _normalize_case_items(raw_cases: list[Any], default_source: str) -> list[dict[str, str]]:
    cases: list[dict[str, str]] = []
    for index, item in enumerate(raw_cases, start=1):
        if not isinstance(item, dict):
            continue

        stdin = str(_first_present(item, ("stdin", "input", "输入")) or "")
        expected_output = str(_first_present(item, ("expected_output", "expected", "output", "输出")) or "")
        stdin = _normalize_case_text(stdin)
        expected_output = _strip_explanation_tail(_normalize_case_text(expected_output))

        if not stdin and not expected_output:
            continue

        name = str(_first_present(item, ("name", "名称")) or f"示例 {index}")
        source = str(_first_present(item, ("source", "来源")) or default_source)
        cases.append(
            {
                "name": name,
                "source": source,
                "stdin": stdin,
                "expected_output": expected_output,
            }
        )
    return cases


def _extract_cases_from_json_text(text: str) -> list[dict[str, str]]:
    payload = _normalize_llm_test_case_payload(text)
    if not payload:
        return []
    cases = payload.get("test_cases", [])
    return cases if isinstance(cases, list) else []


def _parse_user_cases(text: str) -> list[dict[str, str]]:
    payload = _normalize_llm_test_case_payload(text, default_source="用户")
    if payload is not None:
        return _set_case_source(payload.get("test_cases", []), "用户")
    return _set_case_source(_parse_user_cases_text(text), "用户")


def _parse_user_cases_text(text: str) -> list[dict[str, str]]:
    cases: list[dict[str, str]] = []
    current = {"name": "", "source": "用户", "stdin": "", "expected_output": ""}
    current_key = ""

    for line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines():
        heading_key, inline_value = _parse_case_heading(line)
        if heading_key == "stdin":
            if current["stdin"] or current["expected_output"]:
                cases.append(current)
                current = {"name": "", "source": "用户", "stdin": "", "expected_output": ""}
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
            current = {"name": "", "source": "用户", "stdin": "", "expected_output": ""}
            current_key = ""
            continue
        if current_key:
            current[current_key] = _append_text(current[current_key], line)

    if current["stdin"] or current["expected_output"]:
        cases.append(current)

    normalized_cases = []
    for index, item in enumerate(cases, start=1):
        stdin = _normalize_case_text(item.get("stdin", ""))
        expected_output = _strip_explanation_tail(_normalize_case_text(item.get("expected_output", "")))
        if stdin and expected_output:
            normalized_cases.append(
                {
                    "name": item.get("name") or f"用户用例 {index}",
                    "source": "用户",
                    "stdin": stdin,
                    "expected_output": expected_output,
                }
            )
    return normalized_cases


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


def _append_text(existing: str, line: str) -> str:
    if not existing:
        return line
    return f"{existing}\n{line}"


def _replace_source(cases: list[dict[str, str]], source: str) -> list[dict[str, str]]:
    return [{**case, "source": source} for case in cases]


def _set_case_source(cases: list[dict[str, str]], source: str) -> list[dict[str, str]]:
    normalized_cases = []
    for index, case in enumerate(cases, start=1):
        stdin = _normalize_case_text(str(case.get("stdin", "")))
        expected_output = _strip_explanation_tail(_normalize_case_text(str(case.get("expected_output", ""))))
        if not stdin or not expected_output:
            continue
        normalized_cases.append(
            {
                "name": str(case.get("name") or f"{source}用例 {index}"),
                "source": source,
                "stdin": stdin,
                "expected_output": expected_output,
            }
        )
    return normalized_cases


def _serialize_cases(cases: list[dict[str, str]]) -> str:
    normalized_cases = [case for case in cases if case.get("stdin", "").strip() and case.get("expected_output", "").strip()]
    if not normalized_cases:
        return ""
    return json.dumps({"test_cases": normalized_cases}, ensure_ascii=False, indent=2)


def _count_cases(cases: list[dict[str, str]]) -> int:
    return sum(1 for case in cases if case.get("stdin", "").strip() and case.get("expected_output", "").strip())


def _extract_json_text(raw_result: str) -> str:
    text = raw_result.strip()
    if not text:
        return ""

    fenced_start = text.find("```")
    if fenced_start != -1:
        fenced_end = text.rfind("```")
        if fenced_end > fenced_start:
            inner = text[fenced_start + 3 : fenced_end].strip()
            if inner.lower().startswith("json"):
                inner = inner[4:].strip()
            text = inner

    object_start = text.find("{")
    object_end = text.rfind("}")
    if object_start != -1 and object_end != -1 and object_start < object_end:
        return text[object_start : object_end + 1]

    array_start = text.find("[")
    array_end = text.rfind("]")
    if array_start != -1 and array_end != -1 and array_start < array_end:
        return text[array_start : array_end + 1]
    return ""


def _first_present(payload: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _normalize_case_text(text: str) -> str:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(line.rstrip() for line in lines)


def _strip_explanation_tail(text: str) -> str:
    explanation_headings = (
        "解释",
        "说明",
        "提示",
        "备注",
        "约束",
        "constraints",
        "explanation",
        "note",
    )
    kept_lines: list[str] = []
    for line in text.splitlines():
        heading = line.strip().strip("#* -").strip().rstrip("：:").lower()
        if heading in explanation_headings:
            break
        kept_lines.append(line)
    return _normalize_case_text("\n".join(kept_lines))


def _count_runnable_cases_json(raw_json: str) -> int:
    runnable_count = 0
    for case in _extract_cases_from_json_text(raw_json):
        stdin = str(case.get("stdin", "")).strip()
        expected_output = str(case.get("expected_output", "")).strip()
        if stdin and expected_output:
            runnable_count += 1
    return runnable_count


def _count_cases_by_source(raw_json: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in _extract_cases_from_json_text(raw_json):
        if not case.get("stdin", "").strip() or not case.get("expected_output", "").strip():
            continue
        source = str(case.get("source") or "未知")
        counts[source] = counts.get(source, 0) + 1
    return counts


def _count_runnable_problem_cases(analysis_result: str) -> int:
    try:
        payload = json.loads(analysis_result)
    except json.JSONDecodeError:
        return 0

    cases = payload.get("测试用例", [])
    if not isinstance(cases, list):
        return 0

    runnable_count = 0
    for case in cases:
        if not isinstance(case, dict):
            continue
        stdin = str(case.get("stdin", "")).strip()
        expected_output = str(case.get("expected_output", "")).strip()
        if stdin and expected_output:
            runnable_count += 1
    return runnable_count


def _looks_like_error(result: str) -> bool:
    stripped = result.lstrip()
    return stripped.startswith(("错误", "执行错误", "未知工具", "error", "Error", "ERROR"))


def _clip(text: str, limit: int = MAX_CONTEXT_CHARS) -> str:
    if len(text) <= limit:
        return text or "（空）"
    return text[:limit] + f"\n...（内容过长，已截断到 {limit} 字符）"
