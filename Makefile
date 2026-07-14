# OJ Coach Agent - 统一入口
# 灵感来源：niuma-coder 的 make web / make cli 双模式

.PHONY: help web cli install sync

# 默认目标
help:
	@echo "OJ Coach Agent - 算法刷题陪练工具"
	@echo ""
	@echo "用法："
	@echo "  make install    安装依赖（首次使用）"
	@echo "  make sync       同步依赖"
	@echo "  make web        启动 WebUI，浏览器打开 http://localhost:8866"
	@echo "  make cli        启动 CLI / TUI 终端模式"
	@echo ""

# 安装依赖
install:
	uv sync

# 同步依赖（锁定文件有变化时）
sync:
	uv sync --upgrade

# WebUI 模式：启动 FastAPI 服务器 + 静态前端
web:
	uv run uvicorn server:app --host 127.0.0.1 --port 8866 --reload

# CLI/TUI 模式：Rich 增强的终端交互
cli:
	uv run oj_coach_main.py
