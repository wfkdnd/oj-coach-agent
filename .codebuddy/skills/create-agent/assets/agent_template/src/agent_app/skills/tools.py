"""把 SkillLoader 暴露为 Agent 可调用的工具。

用「闭包工厂」把 loader 绑定进两个纯函数再注册；工具函数本身仍保持
`(参数) -> str` 的清爽签名，schema 自动生成。
"""

from __future__ import annotations

from ..tools import ToolRegistry
from .loader import SkillLoader


def register_skill_tools(registry: ToolRegistry, loader: SkillLoader) -> None:
    """向 registry 注册两个工具：list_skills / load_skill。

    Agent 通过它们完成 Level 2 的按需加载：
        list_skills()          → 得到全部 skill 索引
        load_skill(name=...)   → 拿到某个 skill 的 SKILL.md 全文
    """

    def list_skills() -> str:
        """列出当前可用的所有 skill（名字 + 一句话描述）。当你不确定有哪些能力可用时调用。"""
        metas = loader.list_metas()
        if not metas:
            return "(暂无可用 skill；skills 目录未配置或为空)"
        lines = [f"- {m.name}: {m.brief}" for m in metas]
        return "\n".join(lines)

    def load_skill(name: str) -> str:
        """按名字加载一个 skill 的完整工作规范（SKILL.md 全文）。

        使用时机：当 list_skills 中某个 skill 的描述与当前任务相关时，
        调用本工具拿到详细指令，随后按其规范执行任务。

        Args:
            name: skill 名（对应 skills 目录下的子目录名）
        """
        try:
            skill = loader.load(name)
        except (FileNotFoundError, ValueError) as e:
            return f"❌ 加载 skill 失败: {e}"
        except Exception as e:  # noqa: BLE001
            return f"❌ 加载 skill 出错: {e}"

        header = (
            f"# Skill: {skill.meta.name}\n"
            f"# 目录: {skill.path}\n"
            f"# 提示: SKILL.md 中引用的辅助文件可用 read_file 工具按需读取。\n"
            f"---\n"
        )
        return header + skill.content

    registry.register(list_skills)
    registry.register(load_skill)
