"""
第4章产出：ContextManager
==========================

补全这个类，让 tests/test_context.py 全部通过。
"""

from __future__ import annotations

from llm import LLMClient


class ContextManager:
    def __init__(self, llm: LLMClient, max_tokens: int = 4000, keep_last: int = 4):
        self.llm = llm
        self.max_tokens = max_tokens
        self.keep_last = keep_last

    def should_compress(self, messages: list[dict]) -> bool:
        """判断 messages 总 token 是否超过 max_tokens。"""
        total = 0
        for message in messages:
            total += self.llm.count_tokens(message["content"])
        return total > self.max_tokens

    def compress(self, messages: list[dict]) -> list[dict]:
        """压缩 messages：保留 system + 最近 keep_last 条，中间部分摘要。"""
        if not self.should_compress(messages) and len(messages) <= self.keep_last + 2:
            return messages[:]
        
        system = messages[0]
        recent = messages[-self.keep_last:]
        middle = messages[1:-self.keep_last]
        
        middle_text = "\n".join(
            f"{msg['role']}: {msg['content']}" for msg in middle
        )
        summary_prompt = (
            "请把下面这段对话压缩成一段 100 字以内的中文摘要，"
            "**特别保留任何用户偏好、约束、关键事实**：\n\n" + middle_text
        )
        msg = self.llm.chat(
            [{"role": "user", "content": summary_prompt}],
            temperature=0,
        )
        summary = msg or ""
        return [system, {"role": "system", "content": f"[对话摘要] {summary}"}, *recent]
