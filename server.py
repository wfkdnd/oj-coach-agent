"""OJ Coach Agent WebUI 服务器。

提供 FastAPI 后端 API + 静态前端文件服务 + SSE 流式输出。
和 CLI 一样复用 OJCoachCommandRouter + OJCoachSession 内核。
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import MutableMapping
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from oj_coach import OJCoachCommandRouter
from oj_coach.api import (
    LocalSessionStore,
    SessionNotFoundError,
    StreamReplayCache,
    create_app,
    parse_api_payload,
    serialize_command_response,
)
from oj_coach.commands import CommandResponse

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

app: FastAPI

# 静态文件目录（前端三件套）
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)

# 会话过期时间（秒），30 分钟无活动自动清理
SESSION_TTL_SECONDS = 30 * 60

session_store = LocalSessionStore()
stream_cache = StreamReplayCache()

# 会话最后访问时间：session_id -> float (timestamp)
_session_last_access: dict[str, float] = {}


class _SessionRouterView(MutableMapping[str, OJCoachCommandRouter]):
    """兼容旧测试和调试代码的 session_id -> router 视图。"""

    def __getitem__(self, session_id: str) -> OJCoachCommandRouter:
        return session_store.get_router(session_id)

    def __setitem__(self, session_id: str, router: OJCoachCommandRouter) -> None:
        raise TypeError("sessions 是只读视图，请通过 /api/sessions 创建会话。")

    def __delitem__(self, session_id: str) -> None:
        if not session_store.delete_session(session_id):
            raise KeyError(session_id)
        _drop_session_metadata(session_id)

    def __iter__(self):
        return iter(session_store._records)

    def __len__(self) -> int:
        return len(session_store._records)

    def pop(self, session_id: str, default: Any = None) -> OJCoachCommandRouter | Any:
        try:
            router = session_store.get_router(session_id)
        except SessionNotFoundError:
            return default
        session_store.delete_session(session_id)
        _drop_session_metadata(session_id)
        return router


sessions: MutableMapping[str, OJCoachCommandRouter] = _SessionRouterView()


def _touch_session(session_id: str) -> None:
    """更新会话最后访问时间。"""
    _session_last_access[session_id] = time.time()


def _drop_session_metadata(session_id: str) -> None:
    """清理会话附属状态；真实 session 删除由 LocalSessionStore 负责。"""
    _session_last_access.pop(session_id, None)
    stream_cache.drop_session(session_id)


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
            session_store.delete_session(sid)
            _drop_session_metadata(sid)


def _parse_payload(payload: dict[str, Any]) -> tuple[str, str, str | None]:
    """兼容旧测试导入，实际解析逻辑在 oj_coach.api 中维护。"""
    return parse_api_payload(payload)


app = create_app(
    store=session_store,
    title="OJ Coach Agent",
    version="0.2.0",
    lifespan=_lifespan,
    stream_cache=stream_cache,
    on_session_access=lambda session_id: _touch_session(session_id),
    on_session_delete=lambda session_id: _drop_session_metadata(session_id),
)


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


# ── 帮助函数 ───────────────────────────────────────────────

def _serialize_response(response: CommandResponse) -> dict[str, Any]:
    """将 CommandResponse 序列化为 JSON 安全的字典。stream 不能直接序列化。"""
    return serialize_command_response(response)


# ── 静态文件挂载（放在最后，避免拦截 API 路由）──────────────

if STATIC_DIR.exists() and any(STATIC_DIR.iterdir()):
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── 启动入口 ───────────────────────────────────────────────

def main(host: str = "127.0.0.1", port: int = 8866) -> None:
    """启动 WebUI，本地默认只监听 loopback 地址。"""
    import uvicorn

    print("OJ Coach Agent WebUI 启动中...")
    print(f"打开浏览器访问 http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
