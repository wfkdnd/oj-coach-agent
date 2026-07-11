"""测试 WebUI 服务器 (server.py) 的 API 端点。

使用 FastAPI TestClient 对 5 个 API 端点 + SSE 流式做集成测试。
"""

import importlib.util
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

# 检查是否有 fastapi
has_fastapi = importlib.util.find_spec("fastapi") is not None

if not has_fastapi:
    pytest.skip("FastAPI 未安装，跳过 server 测试", allow_module_level=True)

from server import (
    app,
    sessions,
    _parse_payload,
    _serialize_response,
)
from oj_coach.commands import CommandResponse
from fastapi.testclient import TestClient

client = TestClient(app)

# 关键：兼容 oj_coach/api.py 顶层 create_app() 可能已注册了 sessions 路由，
# 但 server.py 有自己的 app。两个互不影响。


def _cleanup_session(session_id: str):
    """测试辅助：清理测试期间创建的会话。"""
    sessions.pop(session_id, None)


# ═══════════════════════════════════════════════════════════════
# _parse_payload 单元测试
# ═══════════════════════════════════════════════════════════════

def test_parse_payload_raw_command():
    """raw 格式：/status、/run、/help 等原生命令。"""
    cmd, args, intext = _parse_payload({"raw": "/status"})
    assert cmd == "status"
    assert args == ""
    assert intext is None


def test_parse_payload_raw_with_args():
    """raw 带参数：/set_timeout 5000。"""
    cmd, args, intext = _parse_payload({"raw": "/set_timeout 5000"})
    assert cmd == "set_timeout"
    assert args == "5000"


def test_parse_payload_raw_no_slash_auto_ask():
    """非 / 开头 raw 自动转为 /ask。"""
    cmd, args, intext = _parse_payload({"raw": "这题怎么做"})
    assert cmd == "ask"
    assert args == ""
    assert intext == "这题怎么做"


def test_parse_payload_structured_command():
    """结构化格式：command + args。"""
    cmd, args, intext = _parse_payload({
        "command": "paste_code",
        "args": "python",
        "input_text": "print(1)",
    })
    assert cmd == "paste_code"
    assert args == "python"
    assert intext == "print(1)"


def test_parse_payload_direct_question():
    """question 字段自动转 /ask。"""
    cmd, args, intext = _parse_payload({
        "question": "为什么超时了？",
    })
    assert cmd == "ask"
    assert args == ""
    assert intext == "为什么超时了？"


def test_parse_payload_empty():
    """空 payload。"""
    cmd, args, intext = _parse_payload({})
    assert cmd == ""
    assert args == ""


# ═══════════════════════════════════════════════════════════════
# _serialize_response 单元测试
# ═══════════════════════════════════════════════════════════════

def test_serialize_response_basic():
    resp = CommandResponse(ok=True, messages=["OK"], output="done")
    result = _serialize_response(resp)
    assert result["ok"] is True
    assert result["messages"] == ["OK"]
    assert result["output"] == "done"
    assert result["has_stream"] is False


def test_serialize_response_with_data():
    resp = CommandResponse(ok=True, data={"key": "value"})
    result = _serialize_response(resp)
    assert result["data"] == {"key": "value"}


def test_serialize_response_with_stream():
    resp = CommandResponse(ok=True, stream=iter(["chunk1", "chunk2"]))
    result = _serialize_response(resp)
    assert result["has_stream"] is True
    # stream 本身不应该在 JSON 中
    assert "stream" not in result


# ═══════════════════════════════════════════════════════════════
# 前端页面 API 测试
# ═══════════════════════════════════════════════════════════════

def test_index_returns_html():
    """GET / 返回 HTML 页面。"""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "OJ Coach" in resp.text


# ═══════════════════════════════════════════════════════════════
# 会话管理 API 测试
# ═══════════════════════════════════════════════════════════════

class TestSessionAPI:
    """会话 CRUD 流程测试。"""

    def test_create_session(self):
        resp = client.post("/api/sessions")
        data = resp.json()
        assert data["ok"] is True
        assert "session_id" in data
        assert len(data["session_id"]) == 12
        _cleanup_session(data["session_id"])

    def test_get_session_status(self):
        # 创建
        resp = client.post("/api/sessions")
        sid = resp.json()["session_id"]

        # 查询
        resp = client.get(f"/api/sessions/{sid}/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "status" in data
        status = data["status"]
        assert "problem_text_set" in status
        assert "code_set" in status
        assert "language" in status
        _cleanup_session(sid)

    def test_get_nonexistent_session_404(self):
        resp = client.get("/api/sessions/nonexist123/status")
        assert resp.status_code == 404
        assert "不存在" in resp.json()["detail"]


# ═══════════════════════════════════════════════════════════════
# 命令执行 API 测试
# ═══════════════════════════════════════════════════════════════

class TestCommandAPI:
    """命令执行端点测试。"""

    def test_help_command(self):
        resp = client.post("/api/sessions")
        sid = resp.json()["session_id"]

        resp = client.post(
            f"/api/sessions/{sid}/command",
            json={"raw": "/help"},
        )
        data = resp.json()
        assert data["ok"] is True
        assert "paste_problem" in data["output"]
        _cleanup_session(sid)

    def test_status_command(self):
        resp = client.post("/api/sessions")
        sid = resp.json()["session_id"]

        resp = client.post(
            f"/api/sessions/{sid}/command",
            json={"raw": "/status"},
        )
        data = resp.json()
        assert data["ok"] is True
        assert "timeout_ms" in data["output"] or "timeout_ms" in str(data.get("data", {}).get("status", {}))
        _cleanup_session(sid)

    def test_paste_problem_and_run_workflow(self):
        """完整工作流：贴题目 → 贴代码 → 运行。"""
        resp = client.post("/api/sessions")
        sid = resp.json()["session_id"]

        # 1. 贴题目
        problem = "## A+B\n给定 a, b，求和。\n样例输入：\n1 2\n样例输出：\n3"
        resp = client.post(
            f"/api/sessions/{sid}/command",
            json={
                "command": "paste_problem",
                "input_text": problem,
            },
        )
        assert resp.json()["ok"] is True

        # 2. 贴代码
        code = "a, b = map(int, input().split())\nprint(a + b)"
        resp = client.post(
            f"/api/sessions/{sid}/command",
            json={
                "command": "paste_code",
                "args": "python",
                "input_text": code,
            },
        )
        assert resp.json()["ok"] is True

        # 3. 单独运行
        resp = client.post(
            f"/api/sessions/{sid}/command",
            json={"raw": "/run"},
        )
        data = resp.json()
        assert data["ok"] is True
        _cleanup_session(sid)

    def test_set_timeout(self):
        resp = client.post("/api/sessions")
        sid = resp.json()["session_id"]

        resp = client.post(
            f"/api/sessions/{sid}/command",
            json={"raw": "/set_timeout 5000"},
        )
        data = resp.json()
        assert data["ok"] is True
        assert "5000ms" in str(data["messages"])

        # 验证状态
        resp = client.get(f"/api/sessions/{sid}/status")
        assert resp.json()["status"]["timeout_ms"] == 5000
        _cleanup_session(sid)

    def test_unknown_command(self):
        resp = client.post("/api/sessions")
        sid = resp.json()["session_id"]

        resp = client.post(
            f"/api/sessions/{sid}/command",
            json={"raw": "/nonexist"},
        )
        data = resp.json()
        assert data["ok"] is False
        assert "未知命令" in data["output"]
        _cleanup_session(sid)

    def test_structured_command_format(self):
        """结构化格式（非 raw）也能正确执行。"""
        resp = client.post("/api/sessions")
        sid = resp.json()["session_id"]

        resp = client.post(
            f"/api/sessions/{sid}/command",
            json={"command": "status"},
        )
        assert resp.json()["ok"] is True
        _cleanup_session(sid)

    def test_non_existent_session_command_404(self):
        resp = client.post(
            "/api/sessions/nonexist123/command",
            json={"raw": "/status"},
        )
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════
# SSE 流式命令 API 测试
# ═══════════════════════════════════════════════════════════════

class TestSSEStreamAPI:
    """SSE 流式端点测试。"""

    def test_stream_status_command(self):
        """非 /ask 命令也有 SSE 输出。"""
        resp = client.post("/api/sessions")
        sid = resp.json()["session_id"]

        resp = client.post(
            f"/api/sessions/{sid}/command/stream",
            json={"raw": "/status"},
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

        body = resp.text
        # 应包含 result 事件和 done 事件
        assert "event: result" in body or "event: done" in body
        _cleanup_session(sid)

    def test_stream_ask_command(self):
        """/ask 命令 SSE 流式返回。"""
        resp = client.post("/api/sessions")
        sid = resp.json()["session_id"]

        resp = client.post(
            f"/api/sessions/{sid}/command/stream",
            json={"raw": "/ask 这题怎么想"},
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

        body = resp.text
        # 有 token 事件（LLM 降级消息）或 result 事件
        assert "event:" in body
        _cleanup_session(sid)

    def test_stream_with_direct_question(self):
        """非 / 开头问题流式返回。"""
        resp = client.post("/api/sessions")
        sid = resp.json()["session_id"]

        resp = client.post(
            f"/api/sessions/{sid}/command/stream",
            json={"command": "ask", "args": "", "input_text": "为什么错了？"},
        )
        assert resp.status_code == 200
        _cleanup_session(sid)


# ═══════════════════════════════════════════════════════════════
# _parse_payload 边界测试
# ═══════════════════════════════════════════════════════════════

def test_parse_payload_raw_with_args_and_spaces():
    """带引号参数 /load_code "a b.py"。"""
    cmd, args, intext = _parse_payload({"raw": '/load_code "my file.py"'})
    assert cmd == "load_code"
    assert "my file.py" in args


def test_parse_payload_text_field():
    """text 字段自动转 /ask。"""
    cmd, args, intext = _parse_payload({"text": "这道题考察什么知识点？"})
    assert cmd == "ask"
    assert intext == "这道题考察什么知识点？"


def test_parse_payload_command_without_slash():
    """command 字段不含 /，直接小写。"""
    cmd, args, intext = _parse_payload({
        "command": "status",
        "args": "",
    })
    assert cmd == "status"
