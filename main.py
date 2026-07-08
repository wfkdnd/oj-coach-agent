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
from oj_tools import build_oj_tools

SYSTEM_PROMPT = """\
你是一个 Coding Agent，能够读写文件、执行命令来帮用户完成编程任务。
你也具备 OJ 刷题陪练能力，能够读取题目、分析题目、读取完整 OJ 代码。

工作规范：
- 先用 list_dir / read_file 了解现状
- 再用 write_file / edit_file 修改代码
- 最后用 bash 验证结果
- 每一步都要说清楚你在做什么

OJ 工具使用规范：
- 用户粘贴题目文本时，用 read_problem
- 用户提供 .txt / .md / .docx 题目文件路径时，用 read_problem_file
- 需要分析题意、输入输出、约束、样例和算法候选时，用 analyze_problem
- 用户粘贴完整 OJ 代码时，用 read_code
- 用户提供 .py / .cpp / .java 代码文件路径时，用 read_code_file
- 运行 OJ 代码时，用 run_oj_code；如果已有题目文本，优先把 problem_text 传入，让工具从题目样例中提取测试用例
- 用户额外补充测试用例时，把它们放入 run_oj_code 的 test_cases；不要覆盖题目样例
- 不要默认保存用户完整代码或敏感信息
"""


def build_main_tools() -> ToolRegistry:
    """构建主入口使用的工具集，包含通用 Coding 工具和 OJ 陪练工具。"""
    tools = build_coding_tools()
    oj_tools = build_oj_tools()

    # ToolRegistry 当前没有公开的合并接口，这里只在主入口做一次轻量合并。
    for tool_name in oj_tools.tool_names:
        tools.register(oj_tools._tools[tool_name])
    return tools


def main():
    # 初始化各模块
    llm = LLMClient()
    tools = build_main_tools()
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
