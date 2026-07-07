"""
第4章产出：Memory
==================

补全这个类，让 tests/test_memory.py 全部通过。
"""

from __future__ import annotations

import json
import math
import os

from llm import LLMClient


class Memory:
    def __init__(self, llm: LLMClient):
        self._entries: list[tuple[str, list[float]]] = []
        self._llm = llm

    def _get_embedding(self, text: str) -> list[float]:
        """获取文本的向量表示。"""
        resp = self._llm.client.embeddings.create(model=os.getenv("EMBEDDING_MODEL", "hunyuan-embedding"), input=text)
        return resp.data[0].embedding

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """余弦相似度。"""
        dot = sum(a[i] * b[i] for i in range(len(a)))
        norm_a = math.sqrt(sum(a[i] ** 2 for i in range(len(a))))
        norm_b = math.sqrt(sum(b[i] ** 2 for i in range(len(b))))
        return dot / (norm_a * norm_b)

    def add(self, text: str) -> None:
        """存入一条记忆。"""
        self._entries.append((text, self._get_embedding(text)))

    def search(self, query: str, k: int = 3) -> list[tuple[float, str]]:
        """检索最相关的 k 条，返回 [(similarity, text), ...]。"""
        query_embedding = self._get_embedding(query)
        similarities = [(self._cosine_similarity(query_embedding, entry[1]), entry[0]) for entry in self._entries]
        similarities.sort(reverse=True)
        return similarities[:k] 

    def save(self, path: str) -> None:
        """持久化到 JSON 文件。"""
        with open(path, "w") as f:
            json.dump(self._entries, f)

    def load(self, path: str) -> None:
        """从 JSON 文件加载。"""
        with open(path, "r") as f:
            self._entries = json.load(f)
