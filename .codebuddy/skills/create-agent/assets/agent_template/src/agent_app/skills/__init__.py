"""Skills 系统（底盘 · 渐进式加载的领域能力包）。

## 分层加载模型（Progressive Disclosure）

Level 1 · 元数据层（always in system prompt）
    只暴露每个 skill 的 name + 一句话 brief
Level 2 · 详细指令层（on demand，通过 load_skill 工具）
    读取 SKILL.md 全文
Level 3 · 资源层（just in time）
    SKILL.md 中引用的 scripts / references，通过已有 read_file 工具按需读取

## 磁盘布局

    <skills_dir>/
    ├── some-skill/
    │   ├── SKILL.md                    # 必需
    │   ├── scripts/
    │   └── references/
    └── ...

说明：这是「Agent 自己可加载的 skill」子系统，与本仓库无关时可整包删除
（同时去掉 core.py 中对它的引用即可）。
"""

from .commands import Passthrough, Reply, Rewrite, preprocess
from .loader import SkillLoader
from .models import Skill, SkillMeta
from .tools import register_skill_tools

__all__ = [
    "Passthrough",
    "Reply",
    "Rewrite",
    "Skill",
    "SkillLoader",
    "SkillMeta",
    "preprocess",
    "register_skill_tools",
]
