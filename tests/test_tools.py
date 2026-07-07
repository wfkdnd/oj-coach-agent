"""第2章 测试：ToolRegistry"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools import ToolRegistry


def test_register_and_invoke():
    registry = ToolRegistry()

    @registry.register
    def add(a: int, b: int) -> int:
        """两数相加"""
        return a + b

    assert "add" in registry.tool_names, "add 应该被注册"
    result = registry.invoke("add", {"a": 3, "b": 5})
    assert "8" in str(result), f"add(3,5) 应该是 8，实际: {result}"


def test_to_schemas():
    registry = ToolRegistry()

    @registry.register
    def get_weather(city: str, unit: str = "celsius") -> str:
        """查询城市天气"""
        return f"{city}: 晴"

    schemas = registry.to_schemas()
    assert len(schemas) == 1, f"应该有 1 个 schema，实际: {len(schemas)}"

    s = schemas[0]
    assert s["type"] == "function"
    assert s["function"]["name"] == "get_weather"
    assert "查询城市天气" in s["function"]["description"]

    params = s["function"]["parameters"]
    assert "city" in params["properties"]
    assert params["properties"]["city"]["type"] == "string"
    assert "city" in params["required"]
    assert "unit" not in params["required"], "有默认值的参数不应该在 required"


def test_invoke_error_handling():
    registry = ToolRegistry()

    @registry.register
    def fail_tool() -> str:
        """总是失败"""
        raise RuntimeError("故意的错误")

    result = registry.invoke("fail_tool", {})
    # 应该返回错误信息字符串，而不是抛异常
    assert "错误" in result or "error" in result.lower() or "Error" in result, (
        f"工具出错应该返回错误信息，实际: {result!r}"
    )


def test_multiple_tools():
    registry = ToolRegistry()

    @registry.register
    def tool_a() -> str:
        """工具A"""
        return "a"

    @registry.register
    def tool_b(x: int) -> str:
        """工具B"""
        return f"b:{x}"

    assert len(registry.tool_names) == 2
    schemas = registry.to_schemas()
    assert len(schemas) == 2


if __name__ == "__main__":
    test_register_and_invoke()
    print("  ✓ test_register_and_invoke")
    test_to_schemas()
    print("  ✓ test_to_schemas")
    test_invoke_error_handling()
    print("  ✓ test_invoke_error_handling")
    test_multiple_tools()
    print("  ✓ test_multiple_tools")
    print("\n✅ 第2章 ToolRegistry 全部测试通过")
