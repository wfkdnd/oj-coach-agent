"""
ContextManager（底盘 · 通常无需修改）
======================================

上下文管理器：当对话 token 超过阈值时，把中间历史摘要压缩，
保留 system + 最近 keep_last 条，避免上下文膨胀。
"""

from __future__ import annotations

from .llm import LLMClient


class ContextManager:
    def __init__(self, llm: LLMClient, max_tokens: int = 4000, keep_last: int = 4):
        self.llm = llm
        self.max_tokens = max_tokens
        self.keep_last = keep_last

    def should_compress(self, messages: list[dict]) -> bool:
        """判断 messages 总 token 是否超过 max_tokens。"""
        total = sum(self.llm.count_tokens(m.get("content", "") or "") for m in messages)
        return total > self.max_tokens

    def compress(self, messages: list[dict]) -> list[dict]:
        """压缩 messages：保留 system + 最近 keep_last 条，中间部分摘要。"""
        # 消息太少，无需压缩
        if len(messages) <= self.keep_last + 1:
            return messages

        system = messages[0]

        # 切分点：默认保留最近 keep_last 条
        split = len(messages) - self.keep_last
        # 关键：不能让 recent 以 tool 消息开头。tool 消息必须紧跟在带 tool_calls
        # 的 assistant 消息之后，否则接口会报 400。这里把边界回退到对应的 assistant 消息。
        while split > 1 and messages[split].get("role") == "tool":
            split -= 1

        recent = messages[split:]
        middle = messages[1:split]
        if not middle:
            return messages

        conversation = "\n".join(
            f"{m.get('role', '')}: {m.get('content', '') or ''}" for m in middle
        )
        try:
            summary = self.llm.chat(
                [
                    {
                        "role": "system",
                        "content": "你是对话摘要助手，请用简洁中文提炼以下多轮对话中的关键信息、"
                        "结论与用户偏好，供后续对话参考。",
                    },
                    {"role": "user", "content": conversation},
                ]
            )
        except Exception:
            # 摘要失败时降级为原始拼接，保证不丢关键信息
            summary = conversation

        summary_msg = {"role": "system", "content": f"[历史对话摘要]\n{summary}"}
        return [system, summary_msg, *recent]
