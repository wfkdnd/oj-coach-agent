"""第4章 测试：ContextManager"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from llm import LLMClient
from context import ContextManager


def test_should_compress_short():
    llm = LLMClient()
    cm = ContextManager(llm=llm, max_tokens=4000)

    short_msgs = [
        {"role": "system", "content": "你是助手"},
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好！"},
    ]
    assert cm.should_compress(short_msgs) is False, "短对话不需要压缩"


def test_should_compress_long():
    llm = LLMClient()
    cm = ContextManager(llm=llm, max_tokens=500)

    long_msgs = [{"role": "system", "content": "你是助手"}]
    for i in range(30):
        long_msgs.append({"role": "user", "content": f"这是第{i}轮很长的对话内容，关于人工智能的讨论。"})
        long_msgs.append({"role": "assistant", "content": f"好的，关于第{i}个话题，我来详细解释一下。"})

    assert cm.should_compress(long_msgs) is True, "30轮对话应该需要压缩"


def test_compress():
    llm = LLMClient()
    cm = ContextManager(llm=llm, max_tokens=500, keep_last=4)

    msgs = [
        {"role": "system", "content": "你是旅行助手"},
        {"role": "user", "content": "我想去杭州"},
        {"role": "assistant", "content": "杭州很好！"},
        {"role": "user", "content": "我不吃鱼"},
        {"role": "assistant", "content": "记下了"},
        {"role": "user", "content": "推荐景点"},
        {"role": "assistant", "content": "西湖、灵隐寺"},
        {"role": "user", "content": "明天天气如何"},
        {"role": "assistant", "content": "明天晴天"},
    ]

    compressed = cm.compress(msgs)
    assert len(compressed) < len(msgs), "压缩后应该更短"
    assert compressed[0]["role"] == "system", "system 消息保留"
    assert compressed[-1]["content"] == msgs[-1]["content"], "最近消息保留"


if __name__ == "__main__":
    test_should_compress_short()
    print("  ✓ test_should_compress_short")
    test_should_compress_long()
    print("  ✓ test_should_compress_long")
    test_compress()
    print("  ✓ test_compress")
    print("\n✅ 第4章 ContextManager 全部测试通过")
