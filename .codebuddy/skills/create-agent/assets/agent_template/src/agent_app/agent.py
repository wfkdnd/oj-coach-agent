"""
Agent 主循环（底盘 · 通常无需修改）
====================================

核心逻辑：Agent = LLM + Tools + Loop。

不断调用 LLM：若返回 tool_calls 就执行工具并把结果回灌，
否则视为最终回答返回。支持可选的上下文压缩、长期记忆与事件回调。
"""

from __future__ import annotations

import json

from .llm import LLMClient
from .tools import ToolRegistry


class Agent:
    def __init__(
        self,
        llm: LLMClient,
        tools: ToolRegistry,
        system_prompt: str = "你是一个有用的助手。",
        context_manager=None,
        memory=None,
    ):
        self.llm = llm
        self.tools = tools
        self.system_prompt = system_prompt
        self.context_manager = context_manager
        self.memory = memory

    def run(self, user_message: str, max_iterations: int = 10, on_event=None,
            history: list[dict] | None = None) -> str:
        """执行任务：循环调用 LLM，有 tool_calls 就执行，没有就返回最终回答。

        on_event: 可选的事件回调 on_event(event: str, data: dict)，供 UI 层
                  渲染运行过程（思考 / 工具调用 / 结果 / 压缩）。默认 None 时无副作用。
        history:  可选的多轮对话历史（不含 system，仅 user/assistant 文本消息）。
                  传入时会作为上下文注入本轮，并在结束后就地追加本轮的
                  user 提问与最终 assistant 回答，供下一轮继续使用。
                  默认 None 时为单轮无状态执行。
        """
        def emit(event: str, **data):
            if on_event is not None:
                try:
                    on_event(event, data)
                except Exception:
                    pass

        def finish(text: str) -> str:
            # 把本轮对话就地写回 history，供下一轮延续（仅保留纯文本对话，
            # 不含工具调用中间消息，避免历史膨胀）。
            if history is not None:
                history.append({"role": "user", "content": user_message})
                history.append({"role": "assistant", "content": text})
            return text

        system_content = self.system_prompt

        # 若接入了长期记忆，检索相关记忆注入 system prompt
        if self.memory is not None:
            try:
                hits = self.memory.search(user_message, k=3)
                if hits:
                    recalled = "\n".join(f"- {text}" for _, text in hits)
                    system_content = f"{system_content}\n\n[相关记忆]\n{recalled}"
            except Exception:
                pass

        messages: list[dict] = [
            {"role": "system", "content": system_content},
            *(history or []),
            {"role": "user", "content": user_message},
        ]
        tool_schemas = self.tools.to_schemas()

        for _ in range(max_iterations):
            # 若接入了上下文管理器且超限，先压缩
            if self.context_manager is not None and self.context_manager.should_compress(messages):
                emit("compress")
                messages = self.context_manager.compress(messages)

            # 接口仅支持流式，complete() 内部强制 stream=True 并拼接为完整 Message；
            # 通过 on_delta 边收边把文本增量抛给 UI 层，形成打字机效果。
            emit("thinking_start")
            _delta_seen = False

            def _on_delta(piece: str) -> None:
                nonlocal _delta_seen
                if not piece:
                    return
                if not _delta_seen:
                    _delta_seen = True
                    emit("stream_start")
                emit("stream_delta", text=piece)

            msg = self.llm.complete(
                messages,
                tools=tool_schemas or None,
                on_delta=_on_delta,
            )
            if _delta_seen:
                emit("stream_end")
            emit("thinking_end")

            # 没有工具调用 → 得到最终回答
            if not getattr(msg, "tool_calls", None):
                return finish(msg.content or "")

            # 有工具调用前，模型可能同时给出一段思考文字
            if msg.content:
                emit("assistant_text", text=msg.content)

            # 记录本轮 assistant 的 tool_calls
            # 注意：带 tool_calls 时 content 用 None（空串不合规），
            # arguments 兜底 "{}"，否则接口会报 invalid parameter value
            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content or None,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments or "{}",
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                }
            )

            # 逐个执行工具，把结果追加回 messages
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                emit("tool_call", name=tc.function.name, args=args)
                result = self.tools.invoke(tc.function.name, args)
                emit("tool_result", name=tc.function.name, result=result)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": str(result),
                    }
                )

        return finish("⚠️ 已达到最大迭代次数，任务未能在限定步数内完成。")
