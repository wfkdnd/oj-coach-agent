"""
Memory（底盘 · 可选，通常无需修改）
====================================

极简向量记忆：用 embedding + 余弦相似度做语义检索。
可持久化到 JSON。若不需要长期记忆，可在 core.py 里不接入。
"""

from __future__ import annotations

import json
import math
import os

from .llm import LLMClient


class Memory:
    def __init__(self, llm: LLMClient):
        self._entries: list[tuple[str, list[float]]] = []
        self._llm = llm

    def _get_embedding(self, text: str) -> list[float]:
        """获取文本的向量表示。"""
        model = os.getenv("EMBEDDING_MODEL_ID", "text-embedding-3-small")
        resp = self._llm.client.embeddings.create(model=model, input=text)
        return resp.data[0].embedding

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """余弦相似度。"""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def add(self, text: str) -> None:
        """存入一条记忆。"""
        embedding = self._get_embedding(text)
        self._entries.append((text, embedding))

    def search(self, query: str, k: int = 3) -> list[tuple[float, str]]:
        """检索最相关的 k 条，返回 [(similarity, text), ...]。"""
        if not self._entries:
            return []
        query_emb = self._get_embedding(query)
        scored = [
            (self._cosine_similarity(query_emb, emb), text)
            for text, emb in self._entries
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:k]

    def save(self, path: str) -> None:
        """持久化到 JSON 文件。"""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._entries, f, ensure_ascii=False)

    def load(self, path: str) -> None:
        """从 JSON 文件加载。"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # JSON 反序列化得到 list，统一转回 tuple 结构
        self._entries = [(text, emb) for text, emb in data]
