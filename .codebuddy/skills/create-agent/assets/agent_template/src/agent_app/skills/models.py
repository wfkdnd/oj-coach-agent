"""Skill 相关的数据类。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SkillMeta:
    """Level 1 元数据：一句话摘要，用于装进 system prompt 的索引。

    - name: 目录名，作为 skill 的唯一 id
    - brief: 一句话描述（取 SKILL.md 第一个非空非标题行）
    """

    name: str
    brief: str


@dataclass(frozen=True)
class Skill:
    """完整 Skill：元数据 + 路径 + SKILL.md 全文。"""

    meta: SkillMeta
    path: Path
    content: str
