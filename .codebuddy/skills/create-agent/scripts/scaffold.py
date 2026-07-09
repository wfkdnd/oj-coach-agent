#!/usr/bin/env python3
"""
scaffold.py —— 从 agent_template 生成一个新的 Agent 项目。

把 skill 内 assets/agent_template/ 拷贝到目标目录，并把默认包名
`agent_app` 与命令名 `agent-app` 替换成用户指定的名字。拷贝后，
使用者只需改 core.py 的 SYSTEM_PROMPT 和 agent_tools/ 里的工具即可。

用法：
    scaffold.py --dest <目标目录> [--package <python包名>] [--command <命令名>]

示例：
    scaffold.py --dest ./my-support-bot --package support_bot --command support-bot

说明：
- --package 必须是合法 Python 包名（字母/数字/下划线，不以数字开头），默认 agent_app
- --command 是可执行命令名（可含连字符），默认由 package 推导（下划线转连字符）
- 目标目录已存在且非空时会报错退出，避免误覆盖
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

TEMPLATE_PKG = "agent_app"
TEMPLATE_CMD = "agent-app"

# 需要做文本替换的文件后缀 / 文件名
_TEXT_SUFFIXES = {".py", ".toml", ".md", ".txt", ".cfg", ".ini", ".example"}
_TEXT_NAMES = {".env.example"}

_PKG_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _template_dir() -> Path:
    # scripts/ 与 assets/ 是同级目录
    return Path(__file__).resolve().parent.parent / "assets" / "agent_template"


def _is_text_file(p: Path) -> bool:
    return p.suffix in _TEXT_SUFFIXES or p.name in _TEXT_NAMES


def scaffold(dest: Path, package: str, command: str) -> int:
    template = _template_dir()
    if not template.is_dir():
        print(f"❌ 找不到模板目录: {template}")
        return 1

    if not _PKG_RE.match(package):
        print(f"❌ 非法 Python 包名: {package!r}（只能字母/数字/下划线，且不以数字开头）")
        return 1

    dest = dest.resolve()
    if dest.exists() and any(dest.iterdir()):
        print(f"❌ 目标目录已存在且非空: {dest}")
        return 1

    # 1. 整体拷贝
    shutil.copytree(template, dest, dirs_exist_ok=True)

    # 2. 重命名包目录 src/agent_app -> src/<package>
    src_pkg = dest / "src" / TEMPLATE_PKG
    if src_pkg.is_dir() and package != TEMPLATE_PKG:
        src_pkg.rename(dest / "src" / package)

    # 3. 文本替换：包名 + 命令名
    for path in dest.rglob("*"):
        if not path.is_file() or not _is_text_file(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        new = text
        if package != TEMPLATE_PKG:
            new = new.replace(TEMPLATE_PKG, package)
        if command != TEMPLATE_CMD:
            # 只替换命令名字符串，避免误伤（命令名含连字符，与包名不冲突）
            new = new.replace(TEMPLATE_CMD, command)
        if new != text:
            path.write_text(new, encoding="utf-8")

    print(f"✅ 已生成 Agent 项目: {dest}")
    print(f"   Python 包名: {package}")
    print(f"   命令名:      {command}")
    print()
    print("下一步：")
    print(f"  1. 编辑 src/{package}/core.py 的 SYSTEM_PROMPT / APP_NAME / APP_TAGLINE")
    print(f"  2. 在 src/{package}/agent_tools/ 里写你的工具并注册")
    print("  3. cp .env.example .env 并填写 BASE_URL / API_KEY / MODEL_ID")
    print(f"  4. uv sync && uv run {command}   (或 pip install -e . 后运行)")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="从 agent_template 生成新的 Agent 项目")
    parser.add_argument("--dest", required=True, help="目标目录")
    parser.add_argument("--package", default=TEMPLATE_PKG, help="Python 包名（默认 agent_app）")
    parser.add_argument("--command", default=None, help="命令名（默认由 package 推导）")
    args = parser.parse_args()

    command = args.command or args.package.replace("_", "-")
    sys.exit(scaffold(Path(args.dest), args.package, command))


if __name__ == "__main__":
    main()
