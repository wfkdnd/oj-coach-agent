"""bash 工具 — 第5章实现。"""

import subprocess
import re

DANGER_PATTERNS = [
    # 破坏性文件操作
    r"rm\s+(-\w+\s+)*(/|~)",
    r"rmdir\s+(-\w+\s+)*(/|~)",
    r">\s*/dev/sd[a-z]",
    r"dd\s+if=",
    r"mkfs\.",
    # 权限提升
    r"sudo\s+",
    r"su\s+-",
    # 远程代码执行
    r"curl\s+.*\|\s*(ba)?sh",
    r"wget\s+.*\|\s*(ba)?sh",
    r"curl\s+.*\|\s*python",
    # fork bomb / 资源耗尽
    r":\(\)\s*\{",
    r"chmod\s+.*777",
    # 危险系统操作
    r"shutdown\s+",
    r"reboot\s+",
    r"init\s+[0-6]",
]


def bash(command: str, workdir: str = ".", timeout: int = 30, max_output: int = 50000) -> str:
    """在工作目录下执行 shell 命令，带安全闸门。

    Args:
        command: 要执行的命令
        workdir: 工作目录
        timeout: 超时秒数
        max_output: 最大输出字符数
    """
  
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
