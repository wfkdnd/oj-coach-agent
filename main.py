"""
第6章：组装完整 Agent
=====================

把 第1章-第5章 的零件拼起来，跑通一个真任务。
"""

from llm import LLMClient
from tools import ToolRegistry
from agent import Agent
from context import ContextManager
from memory import Memory
from coding_tools import build_coding_tools

SYSTEM_PROMPT = """\
你是一个 Coding Agent，能够读写文件、执行命令来帮用户完成编程任务。

工作规范：
- 先用 list_dir / read_file 了解现状
- 再用 write_file / edit_file 修改代码
- 最后用 bash 验证结果
- 每一步都要说清楚你在做什么
"""


def main():
    # 初始化各模块
    llm = LLMClient()
    tools = build_coding_tools()
    context = ContextManager(llm=llm, max_tokens=8000)
    mem = Memory(llm=llm)

    # 组装 Agent
    agent = Agent(
        llm=llm,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        # context_manager=context,  # 第6章 接入
        # memory=mem,               # 第6章 接入
    )

    # 交互式 REPL
    print("🤖 My Coding Agent (输入 exit 退出)")
    print("=" * 50)

    while True:
        try:
            user_input = input("\n你: ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if not user_input or user_input.lower() in ("exit", "quit"):
            break

        print("\nAgent: ", end="")
        result = agent.run(user_input)
        print(result)


if __name__ == "__main__":
    main()
