"""
第1章产出：LLMClient
=====================

补全这个类，让 tests/test_llm.py 全部通过。

依赖：
  - openai SDK
  - tiktoken
  - 环境变量：BASE_URL / API_KEY / MODEL_ID
"""

from __future__ import annotations

import os
from typing import Generator

import tiktoken
from dotenv import load_dotenv
from openai import OpenAI

from _env import get_base_url, get_api_key, get_model_id

load_dotenv()


class LLMClient:
    def __init__(self):
        self.client = OpenAI(base_url=get_base_url(), api_key=get_api_key())
        self.model = get_model_id()
        self.enc = tiktoken.get_encoding("cl100k_base")

    @staticmethod
    def _delta_text(chunk) -> str | None:
        """提取单个 chunk 中的文本内容。
        优先取 content，若无则取 reasoning_content（兼容思维链模型如 glm-5.0）。"""
        if not chunk.choices:
            return None
        delta = chunk.choices[0].delta
        content = getattr(delta, "content", None)
        if content:
            return content
        return getattr(delta, "reasoning_content", None) or None

    def chat(self, messages: list[dict], **kwargs) -> str:
        """非流式调用，返回完整回复文本。"""
        resp = self.client.chat.completions.create(model=self.model, messages=messages, stream=True, **kwargs)
        contents = ""
        for chunk in resp:
            text = self._delta_text(chunk)
            if text:
                contents += text
        return contents

    def chat_stream(self, messages: list[dict], **kwargs) -> Generator[str, None, None]:
        """流式调用，逐 chunk yield 文本片段。兼容 reasoning_content (思维链模型)。"""
        resp = self.client.chat.completions.create(model=self.model, messages=messages, stream=True, **kwargs)
        for chunk in resp:
            text = self._delta_text(chunk)
            if text:
                yield text

    def count_tokens(self, text: str) -> int:
        """统计文本的 token 数。"""
        return len(self.enc.encode(text))
