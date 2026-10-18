.PHONY: help install dev lint format test clean

PYTHON ?= python
SRC := src

help:
	@echo "可用命令："
	@echo "  make install   安装依赖（含开发依赖）"
	@echo "  make dev       启动 LangGraph 开发服务器"
	@echo "  make lint      代码检查（ruff + mypy）"
	@echo "  make format    代码格式化（ruff）"
	@echo "  make test      运行测试（pytest）"
	@echo "  make clean     清理缓存"

install:
	$(PYTHON) -m pip install -e ".[dev]"

dev:
	langgraph dev

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m mypy $(SRC)

format:
	$(PYTHON) -m ruff format .
	$(PYTHON) -m ruff check --select I --fix .

test:
	$(PYTHON) -m pytest

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache build dist *.egg-info
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
