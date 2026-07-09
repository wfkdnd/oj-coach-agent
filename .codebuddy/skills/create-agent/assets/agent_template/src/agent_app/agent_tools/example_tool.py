"""示例场景工具 —— 用来演示「怎么写一个工具」，请替换成你自己的。"""

from __future__ import annotations

from datetime import datetime


def get_current_time(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """获取当前本地时间。当用户询问现在几点 / 今天日期时调用。

    Args:
        fmt: strftime 格式串，默认 "%Y-%m-%d %H:%M:%S"
    """
    return datetime.now().strftime(fmt)
