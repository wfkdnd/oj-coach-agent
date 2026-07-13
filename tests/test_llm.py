"""第1章 测试：LLMClient"""

import sys
import os
from types import SimpleNamespace
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from llm import LLMClient


def _stream_chunk(*, content=None, reasoning_content=None):
    delta = SimpleNamespace(content=content, reasoning_content=reasoning_content)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)])


def test_chat_uses_stream_request_and_collects_final_content():
    """同步语义的 chat 也必须兼容只接受 stream=True 的云端接口。"""
    calls = []

    class FakeCompletions:
        def create(self, **kwargs):
            calls.append(kwargs)
            assert kwargs["stream"] is True
            return iter(
                [
                    _stream_chunk(reasoning_content="内部思考"),
                    _stream_chunk(content="最终"),
                    _stream_chunk(content="答案"),
                ]
            )

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=FakeCompletions()),
    )
    llm = LLMClient.__new__(LLMClient)
    llm.client = client
    llm.model = "test-model"

    assert llm.chat([{"role": "user", "content": "测试"}], stream=False) == "最终答案"
    assert calls[0]["model"] == "test-model"


def test_init():
    llm = LLMClient()
    assert llm.client is not None, "client 应该初始化"
    assert llm.model is not None, "model 不应该为空"


def test_chat():
    llm = LLMClient()
    reply = llm.chat([{"role": "user", "content": "回复一个字：好"}])
    assert isinstance(reply, str), "chat 应该返回字符串"
    assert len(reply) > 0, "回复不应该为空"


def test_chat_stream():
    llm = LLMClient()
    chunks = list(llm.chat_stream([{"role": "user", "content": "回复一个字：好"}]))
    assert len(chunks) > 0, "流式应该至少有一个 chunk"
    full = "".join(chunks)
    assert len(full) > 0, "拼接后不应该为空"


def test_count_tokens():
    llm = LLMClient()
    n = llm.count_tokens("Hello, world!")
    assert isinstance(n, int), "应该返回整数"
    assert 1 <= n <= 10, f"'Hello, world!' 应该是 4 token 左右，实际: {n}"

    assert llm.count_tokens("") == 0, "空字符串应该是 0"


if __name__ == "__main__":
    test_init()
    print("  ✓ test_init")
    test_chat()
    print("  ✓ test_chat")
    test_chat_stream()
    print("  ✓ test_chat_stream")
    test_count_tokens()
    print("  ✓ test_count_tokens")
    print("\n✅ 第1章 LLMClient 全部测试通过")
