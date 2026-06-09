.PHONY: help install run cli clean reset lock sync

# uv → быстро. pip → fallback если uv нет.
UV   := $(shell command -v uv 2>/dev/null)
VENV := .venv
PY   := $(VENV)/bin/python
PIP  := $(VENV)/bin/pip

help:  ## Список команд
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "} {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install:  ## Поставить зависимости (uv → быстро, иначе pip)
ifdef UV
	@echo "→ uv sync"
	@uv sync --quiet
else
	@echo "→ uv не найден, используем pip (медленнее)"
	@if [ ! -x $(PIP) ]; then \
		rm -rf $(VENV); \
		python3 -m venv $(VENV); \
	fi
	@$(PIP) install -q --upgrade pip
	@$(PIP) install -q -r requirements.txt
endif
	@test -f .env || (cp .env.example .env && echo "→ создан .env — впиши ключи!")
	@echo "✓ Готово. Запуск: make run"

run:  ## Запустить десктоп-приложение
ifdef UV
	@uv run python main.py
else
	@$(PY) main.py
endif

cli:  ## Запустить CLI-версию (для отладки)
ifdef UV
	@uv run python cli.py
else
	@$(PY) cli.py
endif

lock:  ## Обновить uv.lock из pyproject.toml
	@uv lock

sync:  ## Синхронизировать .venv с uv.lock
	@uv sync

clean:  ## Удалить кэш Python
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ Кэш очищен"

reset:  ## Полный сброс: удалить venv и кэш
	@rm -rf $(VENV)
	@$(MAKE) clean
	@echo "✓ venv удалён. Установка: make install"
