"""OJ Coach Agent WebUI 服务器。

提供 FastAPI 后端 API + 静态前端文件服务 + SSE 流式输出。
和 CLI 一样复用 OJCoachCommandRouter + OJCoachSession 内核。
"""

from __future__ import annotations

import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from oj_coach import OJCoachCommandRouter, OJCoachSession, parse_command_line
from oj_coach.api import ApiCommandRequest, LocalSessionStore, serialize_command_response
from oj_coach.commands import CommandParseError, CommandResponse

# ── 应用初始化 ──────────────────────────────────────────────

@asynccontextmanager
async def _lifespan(app: FastAPI):
    """启动时注册会话过期清理，关闭时取消后台任务。"""
    cleanup_task = asyncio.create_task(_cleanup_expired_sessions())
    yield
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

app = FastAPI(title="OJ Coach Agent", version="0.2.0", lifespan=_lifespan)

# 静态文件目录（前端三件套）
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)

# 会话过期时间（秒），30 分钟无活动自动清理
SESSION_TTL_SECONDS = 30 * 60

# 内存会话管理：session_id -> OJCoachCommandRouter
# `sessions` 保留给既有调用与测试；阶段 6/7 状态统一由 session_store 管理。
sessions: dict[str, OJCoachCommandRouter] = {}
session_store = LocalSessionStore()

# 会话最后访问时间：session_id -> float (timestamp)
_session_last_access: dict[str, float] = {}

# SSE 流式结果缓存：session_id -> {"result": ..., "tokens": [...]}
# 用于断线重连时重放已执行的结果，避免二次执行命令
_stream_cache: dict[str, dict[str, Any]] = {}


def _touch_session(session_id: str) -> None:
    """更新会话最后访问时间。"""
    if session_id in sessions:
        _session_last_access[session_id] = time.time()


async def _cleanup_expired_sessions() -> None:
    """后台任务：定期清理过期会话。"""
    while True:
        await asyncio.sleep(60)  # 每分钟检查一次
        now = time.time()
        expired = [
            sid for sid, ts in _session_last_access.items()
            if now - ts > SESSION_TTL_SECONDS
        ]
        for sid in expired:
            sessions.pop(sid, None)
            session_store.delete_session(sid)
            _session_last_access.pop(sid, None)
            _stream_cache.pop(sid, None)


def _get_router(session_id: str) -> OJCoachCommandRouter:
    """获取或抛出 404 的会话路由器。同时更新最后访问时间。"""
    router = sessions.get(session_id)
    if router is None:
        raise HTTPException(status_code=404, detail="会话不存在或已过期")
    _touch_session(session_id)
    return router


# ── 前端页面 ────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    """返回前端单页 HTML。"""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(index_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>OJ Coach Agent</h1><p>前端页面尚未创建。</p>")


# ── LLM 健康检查 API ──────────────────────────────────────

@app.get("/api/status/llm")
async def check_llm_status():
    """返回 LLM 配置状态；API Key 只返回是否配置，绝不返回真实值。"""
    from _env import get_base_url, get_api_key, get_model_id

    values = {"base_url": "", "model": "", "api_key_configured": False}
    errors: list[str] = []
    getters = (
        ("base_url", get_base_url),
        ("api_key", get_api_key),
        ("model", get_model_id),
    )
    for field, getter in getters:
        try:
            value = getter()
            if field == "api_key":
                # 真实密钥不能进入响应、前端 DOM 或浏览器日志。
                values["api_key_configured"] = bool(value)
            else:
                values[field] = value
        except EnvironmentError as exc:
            errors.append(str(exc))

    available = bool(
        values["base_url"] and values["model"] and values["api_key_configured"]
    )
    return {
        "ok": True,
        "llm_available": available,
        "reason": "；".join(errors),
        **values,
    }


# ── 会话管理 API ───────────────────────────────────────────

@app.post("/api/sessions")
async def create_session():
    """创建新的刷题会话，返回 session_id。"""
    session_id = uuid.uuid4().hex[:12]
    session_store.create_session(session_id=session_id)
    router = session_store.get_router(session_id)
    sessions[session_id] = router
    _touch_session(session_id)
    return {"ok": True, "session_id": session_id}


@app.get("/api/sessions")
async def list_sessions():
    """列出所有活跃会话。"""
    return {
        "ok": True,
        "sessions": [
            {
                "session_id": sid,
                "language": router.session.state.language or "未设置",
                "event_count": session_store.describe_session(sid)["event_count"],
            }
            for sid, router in sessions.items()
        ],
    }


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除指定会话。"""
    sessions.pop(session_id, None)
    session_store.delete_session(session_id)
    _session_last_access.pop(session_id, None)
    _stream_cache.pop(session_id, None)
    return {"ok": True}


@app.get("/api/sessions/{session_id}/status")
async def get_session_status(session_id: str):
    """获取会话的当前状态。"""
    router = _get_router(session_id)
    status = router.session.status()
    return {"ok": True, "status": status}


@app.get("/api/sessions/{session_id}/events")
async def get_session_events(session_id: str, limit: int = 30):
    """阶段 6 阅读日志：返回最近事件，不保存完整题目或代码。"""
    _get_router(session_id)
    return {
        "ok": True,
        "session_id": session_id,
        "events": session_store.recent_events(session_id, limit=limit),
    }


@app.get("/api/sessions/{session_id}/context")
async def get_session_context(session_id: str):
    """返回阶段 6/7 压缩状态和最近快照。"""
    _get_router(session_id)
    return {"ok": True, **session_store.context_state(session_id)}


@app.post("/api/sessions/{session_id}/context/compress")
async def compress_session_context(session_id: str):
    """手动压缩入口，与 /compress 命令使用同一实现。"""
    _get_router(session_id)
    return {"ok": True, **session_store.compress_context(session_id, force=True)}


# ── 命令执行 API ───────────────────────────────────────────

@app.post("/api/sessions/{session_id}/command")
async def execute_command(session_id: str, payload: dict[str, Any]):
    """执行非流式命令。

    请求体支持两种格式：
    1. 结构化：{"command": "paste_code", "args": "python", "input_text": "..."}
    2. 原始命令：{"raw": "/run"}
    """
    _get_router(session_id)
    command, args, input_text = _parse_payload(payload)
    response = session_store.execute_command(
        session_id,
        ApiCommandRequest(command=command, args=args, input_text=input_text),
    )
    return _serialize_response(response)


@app.post("/api/sessions/{session_id}/command/stream")
async def execute_command_stream(session_id: str, payload: dict[str, Any]):
    """执行命令并通过 SSE 流式返回。支持断线重连（resume 模式）。

    普通命令也会通过 SSE 返回，但非流式命令只会发送一个结果事件。
    客户端重连时发送 {"resume": true}，服务端会重放缓存结果而非重新执行。
    """
    # 断线重连：回放缓存
    if payload.get("resume"):
        cached = _stream_cache.get(session_id)
        if cached:
            async def replay_cache():
                yield {"event": "result", "data": _json_dumps(cached["result"])}
                for chunk in cached["tokens"]:
                    yield {"event": "token", "data": chunk}
                yield {"event": "done", "data": ""}
            return EventSourceResponse(replay_cache())

    _get_router(session_id)
    command, args, input_text = _parse_payload(payload)
    response = session_store.execute_command(
        session_id,
        ApiCommandRequest(command=command, args=args, input_text=input_text),
    )

    async def event_generator():
        base = _serialize_response(response)
        yield {"event": "result", "data": _json_dumps(base)}

        if response.stream is not None:
            collected: list[str] = []
            for chunk in response.stream:
                collected.append(chunk)
                yield {"event": "token", "data": chunk}
            yield {"event": "done", "data": ""}
            # 缓存结果用于断线重连
            _stream_cache[session_id] = {"result": base, "tokens": collected}

    return EventSourceResponse(event_generator())


# ── 帮助函数 ───────────────────────────────────────────────

def _parse_payload(payload: dict[str, Any]) -> tuple[str, str, str | None]:
    """从请求体中提取 command, args, input_text。"""
    # 格式 1：原始命令
    raw: str = str(payload.get("raw", "")).strip()
    if raw:
        try:
            parsed = parse_command_line(raw)
            return parsed.command, parsed.args, None
        except CommandParseError:
            # 如果 raw 不以 / 开头，当做 /ask 处理
            return "ask", "", raw

    # 格式 2：结构化
    command = str(payload.get("command", "")).strip().lower()
    args = str(payload.get("args", "")).strip()
    input_text = payload.get("input_text")

    # 前端直接输入的问题（不以 / 开头）自动转成 /ask
    if not command and raw == "":
        question = str(payload.get("question") or payload.get("text") or "").strip()
        if question:
            return "ask", "", question

    return command, args, input_text


def _serialize_response(response: CommandResponse) -> dict[str, Any]:
    """将 CommandResponse 序列化为 JSON 安全的字典。stream 不能直接序列化。"""
    return serialize_command_response(response)


def _json_dumps(obj: Any) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False, default=str)


# ── 静态文件挂载（放在最后，避免拦截 API 路由）──────────────

if STATIC_DIR.exists() and any(STATIC_DIR.iterdir()):
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── 启动入口 ───────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print("OJ Coach Agent WebUI 启动中...")
    print("打开浏览器访问 http://localhost:8866")
    uvicorn.run(app, host="0.0.0.0", port=8866)
