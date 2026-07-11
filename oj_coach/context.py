"""OJ Coach 专用上下文事件和压缩预留。

根目录的 `context.py` 是课程通用对话压缩器；这里保留 OJ 业务专用的
事件日志、上下文快照和压缩入口，并在压缩对话消息时复用通用 ContextManager。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from typing import Any, Callable


DEFAULT_EVENT_LIMIT = 30
DEFAULT_CHAR_LIMIT = 12000
SUMMARY_LIMIT = 800


@dataclass
class SessionEvent:
    """本地内存事件日志项。

    事件默认只保存命令元信息，不保存完整题目、完整代码或完整测试用例文本。
    """

    type: str
    payload: dict[str, Any]
    created_at: str = field(default_factory=lambda: _now_iso())

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "payload": _jsonable(self.payload),
            "created_at": self.created_at,
        }


@dataclass
class ContextSnapshot:
    """一次上下文压缩后的结构化快照。"""

    problem_summary: str = ""
    code_summary: str = ""
    test_case_summary: str = ""
    run_summary: str = ""
    conversation_summary: str = ""
    important_facts: list[str] = field(default_factory=list)
    source_event_count: int = 0
    compressed_at: str = ""
    compression_mode: str = "未压缩"

    @property
    def is_empty(self) -> bool:
        return not any(
            (
                self.problem_summary,
                self.code_summary,
                self.test_case_summary,
                self.run_summary,
                self.conversation_summary,
                self.important_facts,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "problem_summary": self.problem_summary,
            "code_summary": self.code_summary,
            "test_case_summary": self.test_case_summary,
            "run_summary": self.run_summary,
            "conversation_summary": self.conversation_summary,
            "important_facts": list(self.important_facts),
            "source_event_count": self.source_event_count,
            "compressed_at": self.compressed_at,
            "compression_mode": self.compression_mode,
            "is_empty": self.is_empty,
        }


class ContextCompressor:
    """OJ Coach 上下文压缩预留器。

    当前阶段先生成规则版快照，并保留复用通用 `ContextManager` 压缩对话消息的
    入口。后续阶段可以把这个快照接入 `OJCoachSession.build_question_context()`。
    """

    def __init__(
        self,
        generic_context_manager: Any | None = None,
        llm_factory: Callable[[], Any | None] | None = None,
        max_events_before_compress: int = DEFAULT_EVENT_LIMIT,
        max_chars_before_compress: int = DEFAULT_CHAR_LIMIT,
    ):
        self.generic_context_manager = generic_context_manager
        if self.generic_context_manager is None and llm_factory is not None:
            self.generic_context_manager = self._try_create_generic_manager(llm_factory)
        self.max_events_before_compress = max_events_before_compress
        self.max_chars_before_compress = max_chars_before_compress

    def should_compress(self, events: list[SessionEvent], session_state: Any | None = None) -> bool:
        if len(events) >= self.max_events_before_compress:
            return True

        event_chars = len(json.dumps([event.to_dict() for event in events], ensure_ascii=False, default=str))
        state_chars = _state_text_chars(session_state)
        return event_chars + state_chars >= self.max_chars_before_compress

    def compress(
        self,
        session_state: Any,
        events: list[SessionEvent],
        conversation_messages: list[dict[str, Any]] | None = None,
        force: bool = True,
    ) -> ContextSnapshot:
        should_compress = self.should_compress(events, session_state)
        mode = "规则摘要" if force or should_compress else "未达到阈值"

        return ContextSnapshot(
            problem_summary=_summarize_problem(session_state),
            code_summary=_summarize_code(session_state),
            test_case_summary=_summarize_test_cases(session_state),
            run_summary=_summarize_run_result(session_state),
            conversation_summary=self.compress_conversation_messages(conversation_messages)
            or _summarize_events(events),
            important_facts=_build_important_facts(session_state, events),
            source_event_count=len(events),
            compressed_at=_now_iso(),
            compression_mode=mode,
        )

    def compress_conversation_messages(self, messages: list[dict[str, Any]] | None) -> str:
        """复用根目录通用 ContextManager 压缩对话消息。"""

        if not messages:
            return ""
        if self.generic_context_manager is None:
            return _messages_to_text(messages)

        try:
            compressed_messages = self.generic_context_manager.compress(messages)
        except Exception as exc:
            return f"通用对话压缩失败，已保留最近消息摘要：{exc}\n{_messages_to_text(messages[-4:])}"
        return _messages_to_text(compressed_messages)

    def build_llm_context(
        self,
        snapshot: ContextSnapshot,
        session_state: Any,
        question: str = "",
    ) -> str:
        """生成后续接入 LLM prompt 时可用的上下文文本。"""

        return f"""\
用户问题：
{question or "（无）"}

上下文快照：
问题摘要：{snapshot.problem_summary or "（无）"}
代码摘要：{snapshot.code_summary or "（无）"}
测试用例摘要：{snapshot.test_case_summary or "（无）"}
最近运行摘要：{snapshot.run_summary or "（无）"}
对话摘要：{snapshot.conversation_summary or "（无）"}
关键事实：{_format_facts(snapshot.important_facts)}

当前状态摘要：
{_summarize_current_state(session_state)}
"""

    def _try_create_generic_manager(
        self,
        llm_factory: Callable[[], Any | None],
    ) -> Any | None:
        try:
            llm = llm_factory()
        except Exception:
            return None
        if llm is None:
            return None
        try:
            from context import ContextManager as GenericContextManager
        except Exception:
            return None
        return GenericContextManager(llm=llm)


def _summarize_problem(state: Any) -> str:
    problem_text = str(getattr(state, "problem_text", "") or "")
    analysis_result = str(getattr(state, "analysis_result", "") or "")
    if not problem_text.strip() and not analysis_result.strip():
        return ""

    title = _extract_title(problem_text)
    parts = []
    if title:
        parts.append(f"题目：{title}")
    if problem_text:
        parts.append(f"题目文本长度：{len(problem_text)} 字符")
    if analysis_result:
        parts.append("题目分析摘要：" + _clip(_compact_json_text(analysis_result), SUMMARY_LIMIT))
    return "；".join(parts)


def _summarize_code(state: Any) -> str:
    code = str(getattr(state, "code", "") or "")
    language = str(getattr(state, "language", "") or "未设置")
    if not code.strip():
        return ""
    return f"当前语言：{language}；代码长度：{len(code)} 字符；规则快照不保存完整代码。"


def _summarize_test_cases(state: Any) -> str:
    raw_cases = str(getattr(state, "test_cases", "") or "")
    if not raw_cases.strip():
        return ""

    try:
        payload = json.loads(raw_cases)
    except json.JSONDecodeError:
        return f"测试用例 JSON 当前不可解析，长度：{len(raw_cases)} 字符。"

    cases = payload.get("test_cases", [])
    if not isinstance(cases, list):
        return "测试用例结构中没有 test_cases 列表。"

    source_counts: dict[str, int] = {}
    runnable_count = 0
    for case in cases:
        if not isinstance(case, dict):
            continue
        if str(case.get("stdin", "")).strip() and str(case.get("expected_output", "")).strip():
            runnable_count += 1
            source = str(case.get("source") or "未知")
            source_counts[source] = source_counts.get(source, 0) + 1

    source_text = ", ".join(f"{source}={count}" for source, count in source_counts.items()) or "无"
    return f"可运行测试用例：{runnable_count} 组；来源：{source_text}。"


def _summarize_run_result(state: Any) -> str:
    raw_result = str(getattr(state, "last_run_result", "") or "")
    if not raw_result.strip():
        return ""

    try:
        result = json.loads(raw_result)
    except json.JSONDecodeError:
        return _clip(raw_result, SUMMARY_LIMIT)

    parts = [
        f"状态：{result.get('status', 'unknown')}",
        f"耗时：{result.get('time_ms', 0)}ms",
    ]
    if "case_count" in result:
        parts.append(f"用例：{result.get('passed_count', 0)}/{result.get('case_count', 0)} 通过")
    for key, label in (
        ("compile_output", "编译输出"),
        ("stderr", "标准错误"),
        ("diff_info", "差异信息"),
    ):
        value = str(result.get(key) or "").strip()
        if value:
            parts.append(f"{label}：{_clip(value, 240)}")
    return "；".join(parts)


def _summarize_events(events: list[SessionEvent]) -> str:
    if not events:
        return ""

    command_counts: dict[str, int] = {}
    for event in events:
        command = str(event.payload.get("command") or event.type)
        command_counts[command] = command_counts.get(command, 0) + 1

    counts_text = ", ".join(f"{command}={count}" for command, count in sorted(command_counts.items()))
    recent = " -> ".join(
        str(event.payload.get("command") or event.type) for event in events[-6:]
    )
    return f"事件数：{len(events)}；命令统计：{counts_text}；最近事件：{recent}"


def _build_important_facts(state: Any, events: list[SessionEvent]) -> list[str]:
    facts: list[str] = []
    problem_text = str(getattr(state, "problem_text", "") or "")
    code = str(getattr(state, "code", "") or "")
    test_cases = str(getattr(state, "test_cases", "") or "")
    last_run_result = str(getattr(state, "last_run_result", "") or "")
    language = str(getattr(state, "language", "") or "")

    if problem_text.strip():
        facts.append(f"已读取题目，题目文本长度 {len(problem_text)} 字符。")
    if code.strip():
        facts.append(f"已读取 {language or '未知语言'} 代码，代码长度 {len(code)} 字符。")
    if test_cases.strip():
        facts.append("已有统一测试用例 JSON。")
    if last_run_result.strip():
        facts.append("已有最近一次真实运行结果。")
    if events:
        facts.append(f"当前会话累计记录 {len(events)} 条事件。")
    return facts


def _summarize_current_state(state: Any) -> str:
    parts = [
        _summarize_problem(state),
        _summarize_code(state),
        _summarize_test_cases(state),
        _summarize_run_result(state),
    ]
    return "\n".join(part for part in parts if part) or "（空）"


def _messages_to_text(messages: list[dict[str, Any]]) -> str:
    lines = []
    for message in messages:
        role = str(message.get("role", "unknown"))
        content = str(message.get("content", ""))
        lines.append(f"{role}: {_clip(content, 500)}")
    return _clip("\n".join(lines), SUMMARY_LIMIT)


def _format_facts(facts: list[str]) -> str:
    if not facts:
        return "（无）"
    return "；".join(facts)


def _extract_title(problem_text: str) -> str:
    for line in problem_text.splitlines():
        stripped = line.strip().strip("#").strip()
        if stripped:
            return _clip(stripped, 80)
    return ""


def _compact_json_text(text: str) -> str:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _state_text_chars(state: Any | None) -> int:
    if state is None:
        return 0
    return sum(
        len(str(getattr(state, field_name, "") or ""))
        for field_name in ("problem_text", "analysis_result", "code", "test_cases", "last_run_result")
    )


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"...（已截断到 {limit} 字符）"


def _jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
