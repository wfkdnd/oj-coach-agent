"""OJ Coach Agent WebUI 服务器。

提供 FastAPI 后端 API + 静态前端文件服务 + SSE 流式输出。
和 CLI 一样复用 OJCoachCommandRouter + OJCoachSession 内核。
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from oj_coach import OJCoachCommandRouter, OJCoachSession, parse_command_line
from oj_coach.commands import CommandParseError, CommandResponse

# ── 应用初始化 ──────────────────────────────────────────────

app = FastAPI(title="OJ Coach Agent", version="0.2.0")

# 静态文件目录（前端三件套）
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)

# 内存会话管理：session_id -> OJCoachCommandRouter
sessions: dict[str, OJCoachCommandRouter] = {}


def _get_router(session_id: str) -> OJCoachCommandRouter:
    """获取或抛出 404 的会话路由器。"""
    router = sessions.get(session_id)
    if router is None:
        raise HTTPException(status_code=404, detail="会话不存在或已过期")
    return router


# ── 前端页面 ────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    """返回前端单页 HTML。"""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(index_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>OJ Coach Agent</h1><p>前端页面尚未创建。</p>")


# ── 会话管理 API ───────────────────────────────────────────

@app.post("/api/sessions")
async def create_session():
    """创建新的刷题会话，返回 session_id。"""
    session_id = uuid.uuid4().hex[:12]
    session = OJCoachSession()
    router = OJCoachCommandRouter(session)
    sessions[session_id] = router
    return {"ok": True, "session_id": session_id}


@app.get("/api/sessions/{session_id}/status")
async def get_session_status(session_id: str):
    """获取会话的当前状态。"""
    router = _get_router(session_id)
    status = router.session.status()
    return {"ok": True, "status": status}


# ── 命令执行 API ───────────────────────────────────────────

@app.post("/api/sessions/{session_id}/command")
async def execute_command(session_id: str, payload: dict[str, Any]):
    """执行非流式命令。

    请求体支持两种格式：
    1. 结构化：{"command": "paste_code", "args": "python", "input_text": "..."}
    2. 原始命令：{"raw": "/run"}
    """
    router = _get_router(session_id)
    command, args, input_text = _parse_payload(payload)
    response = router.execute(command, args, input_text=input_text)
    return _serialize_response(response)


@app.post("/api/sessions/{session_id}/command/stream")
async def execute_command_stream(session_id: str, payload: dict[str, Any]):
    """执行命令并通过 SSE 流式返回。适用于 /ask 等需要流式输出的命令。

    普通命令也会通过 SSE 返回，但非流式命令只会发送一个结果事件。
    """
    router = _get_router(session_id)
    command, args, input_text = _parse_payload(payload)
    response = router.execute(command, args, input_text=input_text)

    async def event_generator():
        # 先发送消息和输出
        base = _serialize_response(response)
        yield {"event": "result", "data": _json_dumps(base)}

        # 如果有流式内容，逐 token 发送
        if response.stream is not None:
            for chunk in response.stream:
                yield {"event": "token", "data": chunk}
            yield {"event": "done", "data": ""}

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
    return {
        "ok": response.ok,
        "messages": response.messages,
        "output": response.output,
        "data": response.data,
        "has_stream": response.stream is not None,
    }


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
