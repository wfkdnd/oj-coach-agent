"""OJ Coach 本地 API 层。

这一层只负责把 HTTP 请求转换成统一命令调用。刷题状态仍然由
`OJCoachSession` 管理，`/` 命令行为仍然由 `OJCoachCommandRouter` 管理。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from typing import Any, Callable, Iterator
from uuid import uuid4

from oj_coach.commands import (
    COMPRESSION_COMMANDS,
    CommandParseError,
    CommandResponse,
    EXIT_COMMANDS,
    OJCoachCommandRouter,
    parse_command_line,
)
from oj_coach.context import ContextCompressor, ContextSnapshot, SessionEvent
from oj_coach.session import OJCoachSession


LOCAL_API_TITLE = "OJ Coach Local API"
AUTO_COMPRESS_MIN_NEW_EVENTS = 10
MAX_CONVERSATION_MESSAGES = 40
MAX_CONVERSATION_MESSAGE_CHARS = 12000


class SessionNotFoundError(KeyError):
    """请求的本地会话不存在。"""


@dataclass(frozen=True)
class ApiCommandRequest:
    """API 层的命令请求，支持原始 `/` 命令或拆分后的 command/args。"""

    raw: str = ""
    command: str = ""
    args: str = ""
    input_text: str | None = None


@dataclass
class ApiSessionRecord:
    session_id: str
    router: OJCoachCommandRouter
    created_at: str = field(default_factory=lambda: _now_iso())
    updated_at: str = field(default_factory=lambda: _now_iso())
    events: list[SessionEvent] = field(default_factory=list)
    conversation_messages: list[dict[str, str]] = field(
        default_factory=lambda: [{"role": "system", "content": "OJ Coach 刷题会话阅读日志"}]
    )
    snapshot: ContextSnapshot = field(default_factory=ContextSnapshot)
    compressor: ContextCompressor = field(default_factory=ContextCompressor)

    @property
    def coach_session(self) -> OJCoachSession:
        return self.router.session

    def add_event(self, event_type: str, payload: dict[str, Any]) -> None:
        self.events.append(SessionEvent(event_type, _jsonable(payload)))
        self.updated_at = _now_iso()

    def bind_context_provider(self) -> None:
        self.coach_session.context_provider = self.build_question_context

    def add_conversation_message(self, role: str, content: str) -> None:
        text = str(content or "").strip()
        if not text:
            return
        if len(text) > MAX_CONVERSATION_MESSAGE_CHARS:
            text = text[:MAX_CONVERSATION_MESSAGE_CHARS] + "\n…（内容已截断）"
        self.conversation_messages.append({"role": role, "content": text})
        # 始终保留 system 提示和最近对话，避免内存日志无限增长。
        if len(self.conversation_messages) > MAX_CONVERSATION_MESSAGES + 1:
            self.conversation_messages = [
                self.conversation_messages[0],
                *self.conversation_messages[-MAX_CONVERSATION_MESSAGES:],
            ]

    def build_question_context(self, question: str) -> str:
        if self.snapshot.is_empty:
            return ""
        return self.compressor.build_llm_context(
            snapshot=self.snapshot,
            session_state=self.coach_session.state,
            question=question,
        )


class LocalSessionStore:
    """本地内存 session 仓库。

    当前阶段不做持久化，服务重启后会话自然消失。这样可以避免默认保存用户代码
    和题目内容，也方便后续替换成更严格的本地存储策略。
    """

    def __init__(
        self,
        session_factory: Callable[[], OJCoachSession] | None = None,
    ):
        self._session_factory = session_factory or OJCoachSession
        self._records: dict[str, ApiSessionRecord] = {}

    def create_session(self, session_id: str | None = None) -> dict[str, Any]:
        session_id = session_id or uuid4().hex
        coach_session = self._session_factory()
        record = ApiSessionRecord(
            session_id=session_id,
            router=OJCoachCommandRouter(coach_session),
            compressor=ContextCompressor(llm_factory=coach_session.llm_factory),
        )
        record.bind_context_provider()
        record.add_event("session_created", {"session_id": session_id})
        self._records[session_id] = record
        return self.describe_session(session_id)

    def delete_session(self, session_id: str) -> bool:
        return self._records.pop(session_id, None) is not None

    def get_router(self, session_id: str) -> OJCoachCommandRouter:
        return self._get_record(session_id).router

    def list_sessions(self) -> list[dict[str, Any]]:
        return [self.describe_session(session_id) for session_id in sorted(self._records)]

    def describe_session(self, session_id: str) -> dict[str, Any]:
        record = self._get_record(session_id)
        return {
            "session_id": record.session_id,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "event_count": len(record.events),
            "conversation_message_count": max(0, len(record.conversation_messages) - 1),
            "context": self.context_state(session_id),
            "status": record.coach_session.status(),
        }

    def recent_events(self, session_id: str, limit: int = 20) -> list[dict[str, Any]]:
        record = self._get_record(session_id)
        safe_limit = max(1, int(limit))
        return [event.to_dict() for event in record.events[-safe_limit:]]

    def context_state(self, session_id: str) -> dict[str, Any]:
        record = self._get_record(session_id)
        return {
            "session_id": session_id,
            "event_count": len(record.events),
            "conversation_message_count": max(0, len(record.conversation_messages) - 1),
            "events_since_last_compress": _events_since_last_compress(record),
            "should_compress": record.compressor.should_compress(
                record.events,
                record.coach_session.state,
            ),
            "snapshot": record.snapshot.to_dict(),
        }

    def compress_context(self, session_id: str, force: bool = True) -> dict[str, Any]:
        record = self._get_record(session_id)
        snapshot = record.compressor.compress(
            session_state=record.coach_session.state,
            events=record.events,
            conversation_messages=record.conversation_messages,
            force=force,
        )
        record.snapshot = snapshot
        record.add_event(
            "context_compressed",
            {
                "source_event_count": snapshot.source_event_count,
                "compression_mode": snapshot.compression_mode,
            },
        )
        return self.context_state(session_id)

    def maybe_auto_compress_context(self, record: ApiSessionRecord) -> bool:
        if not _should_auto_compress(record):
            return False

        try:
            snapshot = record.compressor.compress(
                session_state=record.coach_session.state,
                events=record.events,
                conversation_messages=record.conversation_messages,
                force=False,
            )
        except Exception as exc:
            record.add_event("context_compress_failed", {"error": str(exc)})
            return False

        record.snapshot = snapshot
        record.add_event(
            "context_auto_compressed",
            {
                "source_event_count": snapshot.source_event_count,
                "compression_mode": snapshot.compression_mode,
            },
        )
        return True

    def execute_command(
        self,
        session_id: str,
        request: ApiCommandRequest,
    ) -> CommandResponse:
        record = self._get_record(session_id)

        try:
            command, args = resolve_command_request(request)
        except CommandParseError as exc:
            response = CommandResponse(False, output=str(exc))
            record.add_event("command_rejected", _command_event_payload(request, "", "", response))
            return response

        if command in EXIT_COMMANDS:
            response = CommandResponse(
                False,
                output="本地 API 不支持 /exit；如需结束服务，请停止本地服务进程。",
            )
            record.add_event("command_rejected", _command_event_payload(request, command, args, response))
            return response

        if command in COMPRESSION_COMMANDS:
            context = self.compress_context(session_id, force=True)
            return CommandResponse(
                True,
                messages=["已压缩当前会话上下文。"],
                output=_render_context_snapshot(context),
                data={"context": context},
            )

        if command in {"ask", "summary"}:
            self.maybe_auto_compress_context(record)

        conversation_input = ""
        if command == "ask":
            conversation_input = args.strip() or (request.input_text or "").strip()
        elif command == "summary":
            conversation_input = "/summary" + (f" {args.strip()}" if args.strip() else "")
        if conversation_input:
            record.add_conversation_message("user", conversation_input)

        response = record.router.execute(command, args, input_text=request.input_text)
        if command in {"ask", "summary"} and response.stream is not None:
            response.stream = _capture_stream_for_log(record, response.stream)
        elif command == "summary" and response.output.strip():
            record.add_conversation_message("assistant", response.output)
        record.add_event("command_executed", _command_event_payload(request, command, args, response))
        return response

    def _get_record(self, session_id: str) -> ApiSessionRecord:
        try:
            return self._records[session_id]
        except KeyError as exc:
            raise SessionNotFoundError(f"会话不存在：{session_id}") from exc


def resolve_command_request(request: ApiCommandRequest) -> tuple[str, str]:
    """把 API 请求解析成命令名和参数。"""

    raw = request.raw.strip()
    if raw:
        parsed = parse_command_line(raw)
        return parsed.command, parsed.args

    command = request.command.strip()
    args = request.args.strip()
    if command.startswith("/"):
        parsed = parse_command_line(command + (f" {args}" if args else ""))
        return parsed.command, parsed.args
    if not command:
        raise CommandParseError("请提供 command 或 raw。")
    return command.lower(), args


def serialize_command_response(response: CommandResponse) -> dict[str, Any]:
    """把命令响应转换成 JSON 友好的结构。"""

    return {
        "ok": response.ok,
        "messages": response.messages,
        "output": response.output,
        "data": _jsonable(response.data),
        "has_stream": response.stream is not None,
        "stream_title": response.stream_title,
    }


def create_app(store: LocalSessionStore | None = None):
    """创建 FastAPI app。

    当前运行环境可能尚未安装 FastAPI，所以依赖在这里延迟导入。真正启动 API
    服务前，请先安装 `fastapi` 和 `uvicorn`。
    """

    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.responses import StreamingResponse
        from pydantic import BaseModel
    except ImportError as exc:
        raise RuntimeError(
            "缺少本地 API 依赖。请先安装 fastapi 和 uvicorn，例如："
            "pip install fastapi \"uvicorn[standard]\""
        ) from exc

    session_store = store or LocalSessionStore()
    app = FastAPI(title=LOCAL_API_TITLE, version="0.2.0")
    app.state.session_store = session_store

    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    class CommandBody(BaseModel):
        raw: str | None = None
        command: str | None = None
        args: str | None = None
        input_text: str | None = None

    def get_store() -> LocalSessionStore:
        return app.state.session_store

    def get_or_404(session_id: str) -> dict[str, Any]:
        try:
            return get_store().describe_session(session_id)
        except SessionNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    def to_api_request(body: CommandBody) -> ApiCommandRequest:
        return ApiCommandRequest(
            raw=body.raw or "",
            command=body.command or "",
            args=body.args or "",
            input_text=body.input_text,
        )

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "service": LOCAL_API_TITLE}

    @app.post("/api/sessions")
    def create_session() -> dict[str, Any]:
        return get_store().create_session()

    @app.get("/api/sessions")
    def list_sessions() -> dict[str, Any]:
        return {"sessions": get_store().list_sessions()}

    @app.get("/api/sessions/{session_id}/status")
    def get_status(session_id: str) -> dict[str, Any]:
        return get_or_404(session_id)

    @app.get("/api/sessions/{session_id}/events")
    def get_events(session_id: str, limit: int = 20) -> dict[str, Any]:
        get_or_404(session_id)
        return {
            "session_id": session_id,
            "events": get_store().recent_events(session_id, limit=limit),
        }

    @app.get("/api/sessions/{session_id}/context")
    def get_context(session_id: str) -> dict[str, Any]:
        get_or_404(session_id)
        return get_store().context_state(session_id)

    @app.post("/api/sessions/{session_id}/context/compress")
    def compress_context(session_id: str) -> dict[str, Any]:
        get_or_404(session_id)
        return get_store().compress_context(session_id, force=True)

    @app.post("/api/sessions/{session_id}/command")
    def execute_command(session_id: str, body: CommandBody) -> dict[str, Any]:
        get_or_404(session_id)
        response = get_store().execute_command(session_id, to_api_request(body))
        return serialize_command_response(response)

    @app.post("/api/sessions/{session_id}/command/stream")
    def execute_command_stream(session_id: str, body: CommandBody):
        get_or_404(session_id)
        response = get_store().execute_command(session_id, to_api_request(body))
        return StreamingResponse(
            _sse_response(response),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    return app


def run_dev_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    """启动本地开发 API 服务。"""

    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError(
            "缺少 uvicorn，无法启动本地 API 服务。请先安装：pip install \"uvicorn[standard]\""
        ) from exc

    uvicorn.run(create_app(), host=host, port=port)


def _sse_response(response: CommandResponse) -> Iterator[str]:
    yield _sse_event("start", serialize_command_response(response))
    if response.stream is None:
        yield _sse_event("done", {"ok": response.ok})
        return

    for chunk in response.stream:
        yield _sse_event("chunk", {"text": chunk})
    yield _sse_event("done", {"ok": response.ok})


def _sse_event(event: str, data: dict[str, Any]) -> str:
    json_data = json.dumps(_jsonable(data), ensure_ascii=False)
    return f"event: {event}\ndata: {json_data}\n\n"


def _command_event_payload(
    request: ApiCommandRequest,
    command: str,
    args: str,
    response: CommandResponse,
) -> dict[str, Any]:
    return {
        "command": command,
        "args_chars": len(args),
        "used_raw": bool(request.raw.strip()),
        "input_chars": len(request.input_text or ""),
        "ok": response.ok,
        "message_count": len(response.messages),
        "output_chars": len(response.output),
        "has_stream": response.stream is not None,
    }


def _capture_stream_for_log(
    record: ApiSessionRecord,
    stream: Iterator[str],
) -> Iterator[str]:
    """边流式返回边记录回答，供下一次阶段 7 压缩使用。"""
    chunks: list[str] = []
    try:
        for chunk in stream:
            text = str(chunk)
            chunks.append(text)
            yield text
    finally:
        answer = "".join(chunks).strip()
        if answer:
            record.add_conversation_message("assistant", answer)
            record.add_event("assistant_response", {"output_chars": len(answer)})


def _should_auto_compress(record: ApiSessionRecord) -> bool:
    if record.snapshot.is_empty:
        return record.compressor.should_compress(record.events, record.coach_session.state)

    if _events_since_last_compress(record) < AUTO_COMPRESS_MIN_NEW_EVENTS:
        return False
    return record.compressor.should_compress(record.events, record.coach_session.state)


def _events_since_last_compress(record: ApiSessionRecord) -> int:
    if record.snapshot.is_empty:
        return len(record.events)
    return max(0, len(record.events) - record.snapshot.source_event_count)


def _render_context_snapshot(context: dict[str, Any]) -> str:
    snapshot = context.get("snapshot", {})
    if snapshot.get("is_empty"):
        return "当前没有可压缩的上下文。"

    lines = [
        "上下文压缩完成：",
        f"- 事件数：{context.get('event_count', 0)}",
        f"- 快照来源事件数：{snapshot.get('source_event_count', 0)}",
        f"- 压缩模式：{snapshot.get('compression_mode', '')}",
    ]
    for key, label in (
        ("problem_summary", "题目摘要"),
        ("code_summary", "代码摘要"),
        ("test_case_summary", "测试用例摘要"),
        ("run_summary", "运行摘要"),
        ("conversation_summary", "对话摘要"),
    ):
        value = str(snapshot.get(key) or "").strip()
        if value:
            lines.append(f"- {label}：{value}")
    return "\n".join(lines)


def _jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


try:
    app = create_app()
except RuntimeError:
    app = None


if __name__ == "__main__":
    run_dev_server()
