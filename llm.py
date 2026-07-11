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
import time
from typing import Generator

import tiktoken
from dotenv import load_dotenv
from openai import OpenAI, APIError, APITimeoutError, RateLimitError, APIConnectionError

from _env import get_base_url, get_api_key, get_model_id

load_dotenv()

# 重试配置
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # 基础等待秒数
RETRYABLE_ERRORS = (APITimeoutError, RateLimitError, APIConnectionError)


def _retry_with_backoff(func, *args, **kwargs):
    """带指数退避的重试包装器。"""
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            return func(*args, **kwargs)
        except RETRYABLE_ERRORS as e:
            last_error = e
            if attempt >= MAX_RETRIES:
                raise
            delay = RETRY_BASE_DELAY * (2 ** attempt)
            print(f"[LLM] 请求失败 (第{attempt+1}次): {type(e).__name__}, {delay:.1f}s 后重试...")
            time.sleep(delay)
    raise last_error  # type: ignore[misc]


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
        def _call():
            return self.client.chat.completions.create(
                model=self.model, messages=messages, stream=False, **kwargs
            )
        resp = _retry_with_backoff(_call)
        return resp.choices[0].message.content or ""

    def chat_stream(self, messages: list[dict], **kwargs) -> Generator[str, None, None]:
        """流式调用，逐 chunk yield 文本片段。兼容 reasoning_content (思维链模型)。"""
        def _call():
            return self.client.chat.completions.create(
                model=self.model, messages=messages, stream=True, **kwargs
            )
        resp = _retry_with_backoff(_call)
        for chunk in resp:
            text = self._delta_text(chunk)
            if text:
                yield text

    def count_tokens(self, text: str) -> int:
        """统计文本的 token 数。"""
        return len(self.enc.encode(text))

    def embed(self, text: str, model: str | None = None) -> list[float]:
        """获取文本的向量表示，带重试保护。"""
        model = model or os.getenv("EMBEDDING_MODEL", "hunyuan-embedding")

        def _call():
            return self.client.embeddings.create(model=model, input=text)

        resp = _retry_with_backoff(_call)
        return resp.data[0].embedding
