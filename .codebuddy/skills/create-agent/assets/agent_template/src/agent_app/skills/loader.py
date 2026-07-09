"""SkillLoader：扫描 skills 目录，生成索引，按需读取全文。

设计要点：
- 惰性扫描：`__init__` 只保存路径，不做 IO；首次 `list_metas()` 时才扫描
- 索引缓存：扫描一次后 metas 缓存在内存；`refresh()` 可强制重扫
- 单文件读取：`load(name)` 才真正读 SKILL.md 全文（Level 2）
- 安全：所有对外方法都用 skill 目录做前缀校验，防目录穿越

## 目录约定（支持两种布局）

1) 扁平布局（推荐）：
       <skills_dir>/<name>/SKILL.md

2) 嵌套布局（兼容第三方 skill 包）：
       <skills_dir>/<pkg>/SKILL.md              # 可选
       <skills_dir>/<pkg>/skills/<name>/SKILL.md
"""

from __future__ import annotations

import re
from pathlib import Path

from .models import Skill, SkillMeta

# 单个 skill 目录内约定的入口文件
_ENTRY_FILE = "SKILL.md"

# 嵌套 skill 包内约定的二级目录名
_NESTED_DIR = "skills"

# 名称合法字符：字母数字/下划线/连字符/点，长度不超 64
_NAME_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")


class SkillLoader:
    """扫描并索引 <skills_dir> 下的 skill 目录。

    Args:
        skills_dir: skills 根目录。目录不存在时静默视为「无 skill」，不报错。
    """

    def __init__(self, skills_dir: str | Path):
        self.skills_dir = Path(skills_dir).expanduser().resolve()
        self._metas: list[SkillMeta] | None = None       # 索引缓存
        self._name_to_path: dict[str, Path] = {}         # name → 实际目录

    # ---------- Level 1：元数据索引 ----------
    def list_metas(self) -> list[SkillMeta]:
        """返回全部 skill 的一句话索引，按名字排序。缓存到内存。"""
        if self._metas is None:
            self._metas = self._scan()
        return self._metas

    def refresh(self) -> list[SkillMeta]:
        """强制重扫（用于开发时热更新）。"""
        self._metas = None
        self._name_to_path = {}
        return self.list_metas()

    # ---------- Level 2：读取单个 skill 全文 ----------
    def load(self, name: str) -> Skill:
        """按名字读取一个 skill 的完整内容。

        Raises:
            ValueError: 名字非法
            FileNotFoundError: 找不到该 skill 或 SKILL.md 缺失
        """
        self._validate_name(name)

        # 确保索引已建立（load 可能先于 list_metas 被调用）
        if self._metas is None:
            self.list_metas()

        skill_dir = self._name_to_path.get(name)
        if skill_dir is None:
            # 兜底：回退到扁平布局的直接寻址
            skill_dir = (self.skills_dir / name).resolve()

        # 目录穿越防护：解析后必须仍在 skills_dir 下
        if not self._is_inside(skill_dir, self.skills_dir):
            raise ValueError(f"非法 skill 名: {name!r}")

        entry = skill_dir / _ENTRY_FILE
        if not entry.is_file():
            raise FileNotFoundError(
                f"skill {name!r} 不存在或缺少 {_ENTRY_FILE}: {entry}"
            )

        text = entry.read_text(encoding="utf-8")
        brief = _extract_brief(text) or name
        return Skill(meta=SkillMeta(name=name, brief=brief), path=skill_dir, content=text)

    # ---------- 内部实现 ----------
    def _scan(self) -> list[SkillMeta]:
        """扫描 skills_dir，收集所有含 SKILL.md 的目录。"""
        self._name_to_path = {}
        if not self.skills_dir.is_dir():
            return []

        metas: dict[str, SkillMeta] = {}

        def _try_collect(child: Path) -> bool:
            """child 目录若合法且含 SKILL.md 就登记；返回是否登记成功。"""
            name = child.name
            if name.startswith(".") or not _NAME_RE.match(name):
                return False
            entry = child / _ENTRY_FILE
            if not entry.is_file():
                return False
            if name in metas:
                return False  # 冲突：保留先到先得
            try:
                head = entry.read_text(encoding="utf-8", errors="replace")[:4096]
            except Exception:
                return False
            brief = _extract_brief(head) or "(无描述)"
            metas[name] = SkillMeta(name=name, brief=brief)
            self._name_to_path[name] = child.resolve()
            return True

        # 第一轮：扁平布局
        top_dirs: list[Path] = []
        for child in sorted(self.skills_dir.iterdir()):
            if not child.is_dir():
                continue
            top_dirs.append(child)
            _try_collect(child)

        # 第二轮：嵌套布局 —— 对未被登记的顶级目录，向下看一层 `skills/`
        for top in top_dirs:
            nested_root = top / _NESTED_DIR
            if not nested_root.is_dir():
                continue
            for inner in sorted(nested_root.iterdir()):
                if not inner.is_dir():
                    continue
                _try_collect(inner)

        # 稳定顺序：按 name 排序
        return [metas[k] for k in sorted(metas)]

    @staticmethod
    def _validate_name(name: str) -> None:
        if not isinstance(name, str) or not _NAME_RE.match(name):
            raise ValueError(f"非法 skill 名: {name!r}")

    @staticmethod
    def _is_inside(target: Path, base: Path) -> bool:
        try:
            target.relative_to(base)
            return True
        except ValueError:
            return False


# ---------- 辅助：从 SKILL.md 提取一句话摘要 ----------
def _extract_brief(text: str, limit: int = 160) -> str:
    """规则：
    1) 若首部是 YAML front-matter (---)，并含 description: 字段，取该值
    2) 否则跳过 Markdown 标题（# / ##），取第一段非空文本的第一行
    """
    text = text.lstrip("\ufeff")  # 去 BOM

    # 尝试 YAML front-matter
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            front = text[3:end]
            m = re.search(r"^\s*description\s*:\s*(.+?)\s*$", front, re.MULTILINE)
            if m:
                return _truncate(m.group(1).strip().strip('"\''), limit)

    # 否则找第一个非标题非空行
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("---"):
            continue
        return _truncate(line, limit)
    return ""


def _truncate(s: str, limit: int) -> str:
    return s if len(s) <= limit else s[: limit - 1].rstrip() + "…"
