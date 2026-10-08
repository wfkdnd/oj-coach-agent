"""
LLMClient

提供非流式对话、流式对话、token 统计和文本向量接口。

依赖：
  - openai SDK
  - tiktoken
  - 项目根目录 .env：BASE_URL / API_KEY / MODEL_ID / EMBEDDING_MODEL
"""

from __future__ import annotations

from pathlib import Path
from typing import Generator

import tiktoken
from dotenv import dotenv_values
from openai import OpenAI


class LLMClient:
    def __init__(self):
        config = dotenv_values(Path(__file__).resolve().with_name(".env"))
        base_url = config.get("BASE_URL")
        api_key = config.get("API_KEY")
        model = config.get("MODEL_ID")
        if not base_url or not api_key or not model:
            missing = [name for name in ("BASE_URL", "API_KEY", "MODEL_ID") if not config.get(name)]
            raise EnvironmentError(f"请在 .env 中设置 {' / '.join(missing)}")

        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        self.embedding_model = config.get("EMBEDDING_MODEL")
        self.enc = tiktoken.get_encoding("cl100k_base")

    def chat(self, messages: list[dict], **kwargs) -> str:
        """非流式调用，返回完整回复文本。"""
        kwargs.pop("stream", None)  # 移除 stream 参数，确保非流式调用
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages, 
            stream=False,
            **kwargs,
        )
        return resp.choices[0].message.content or ""

    def chat_stream(self, messages: list[dict], **kwargs) -> Generator[str, None, None]:
        """流式调用，逐 chunk yield 文本片段。"""
        kwargs.pop("stream", None)  # 移除 stream 参数，确保流式调用
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages, 
            stream=True,
            **kwargs,
        )
        for chunk in resp:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def count_tokens(self, text: str) -> int:
        """统计文本的 token 数。"""
        return len(self.enc.encode(text))

    def embed(self, text: str, model: str | None = None) -> list[float]:
        """获取文本的向量表示。"""
        model = model or self.embedding_model
        if not model:
            raise EnvironmentError("请在 .env 中设置 EMBEDDING_MODEL，或通过 model 参数指定向量模型")
        resp = self.client.embeddings.create(model=model, input=text)
        return resp.data[0].embedding
