"""bash 工具（带安全闸门）。"""

import re
import subprocess

DANGER_PATTERNS = [
    r"rm\s+(-\w+\s+)*(/|~)",
    r"sudo\s+",
    r"curl\s+.*\|\s*(ba)?sh",
]


def bash(command: str, workdir: str = ".", timeout: int = 30, max_output: int = 50000) -> str:
    """在工作目录下执行 shell 命令，带安全闸门。

    Args:
        command: 要执行的命令
        workdir: 工作目录
        timeout: 超时秒数
        max_output: 最大输出字符数
    """
    # 1. 危险命令拦截
    for pattern in DANGER_PATTERNS:
        if re.search(pattern, command):
            return f"❌ 已拒绝执行高危命令: {command}"

    # 2. 执行命令（带超时）
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return f"❌ 命令执行超时（超过 {timeout}s）: {command}"
    except Exception as e:
        return f"❌ 命令执行失败: {e}"

    # 3. 合并输出
    output = (result.stdout or "") + (result.stderr or "")

    # 4. 输出截断
    if len(output) > max_output:
        output = output[:max_output] + "\n...（输出过长已截断）"

    if not output:
        return f"(命令已执行，无输出，退出码 {result.returncode})"
    return output
