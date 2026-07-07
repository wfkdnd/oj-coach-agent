"""第1章 测试：LLMClient"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from llm import LLMClient


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
