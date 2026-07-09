"""让 `python -m agent_app` 等价于运行 CLI 入口。"""

from .cli import main

if __name__ == "__main__":
    main()
