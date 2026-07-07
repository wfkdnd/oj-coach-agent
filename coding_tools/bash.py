"""bash 工具 — 第5章实现。"""

import subprocess
import re

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
    # TODO: 参考 exercises/05 的 ex_5_3.py
    #   1. 危险命令拦截
    #   2. subprocess.run 执行
    #   3. 超时处理
    #   4. 输出截断
    if any(re.search(pattern, command) for pattern in DANGER_PATTERNS):
        return f"❌ 危险命令被拦截:{command}"
    
    try:
        result = subprocess.run(
            command, cwd=workdir, shell=True, 
            timeout=timeout, capture_output=True, text=True
        )
    except subprocess.TimeoutExpired:
        return f"❌ 命令超时({timeout}s):{command}"
    output = (result.stdout or "") + (result.stderr or "")
    if len(output) > max_output:
      output = output[:max_output] + "\n... [输出被截断]"
    return output
