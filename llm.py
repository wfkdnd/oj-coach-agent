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

    def chat(self, messages: list[dict], **kwargs) -> str:
        """非流式调用，返回完整回复文本。"""
        resp = self.client.chat.completions.create(model=self.model, messages=messages, stream=True, **kwargs)
        contents = ""
        for chunk in resp:
            if chunk.choices and chunk.choices[0].delta.content:
                contents += chunk.choices[0].delta.content
        return contents

    def chat_stream(self, messages: list[dict], **kwargs) -> Generator[str, None, None]:
        """流式调用，逐 chunk yield 文本片段。"""
        resp = self.client.chat.completions.create(model=self.model, messages=messages, stream=True, **kwargs)
        for chunk in resp:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def count_tokens(self, text: str) -> int:
        """统计文本的 token 数。"""
        return len(self.enc.encode(text))
