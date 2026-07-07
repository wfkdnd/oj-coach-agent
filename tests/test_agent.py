"""第3章 测试：Agent"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from llm import LLMClient
from tools import ToolRegistry
from agent import Agent


def make_test_agent():
    """构造一个带简单工具的测试 Agent。"""
    llm = LLMClient()
    registry = ToolRegistry()

    @registry.register
    def get_time() -> str:
        """获取当前时间"""
        import datetime
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @registry.register
    def add(a: int, b: int) -> int:
        """计算两个数的和"""
        return a + b

    return Agent(llm=llm, tools=registry, system_prompt="你是一个助手，有工具可用。")


def test_basic_chat():
    agent = make_test_agent()
    reply = agent.run("你好")
    assert isinstance(reply, str), "应该返回字符串"
    assert len(reply) > 0, "回复不应该为空"


def test_tool_usage():
    agent = make_test_agent()
    reply = agent.run("请帮我算 17 + 25 等于多少")
    assert "42" in reply, f"17+25=42，但 Agent 回答: {reply}"


def test_max_iterations():
    agent = make_test_agent()
    # 即使设 max_iterations=1，也应该返回字符串不崩
    reply = agent.run("你好", max_iterations=1)
    assert isinstance(reply, str), "max_iterations=1 也应该返回字符串"


if __name__ == "__main__":
    test_basic_chat()
    print("  ✓ test_basic_chat")
    test_tool_usage()
    print("  ✓ test_tool_usage")
    test_max_iterations()
    print("  ✓ test_max_iterations")
    print("\n✅ 第3章 Agent 全部测试通过")
