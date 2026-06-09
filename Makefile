.PHONY: help install run cli clean reset

VENV       := .venv
PY         := $(VENV)/bin/python
PIP        := $(VENV)/bin/pip

help:  ## Список команд
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "} {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install:  ## Создать .venv и поставить зависимости
	@if [ ! -x $(PIP) ]; then \
		echo "→ создаю venv..."; \
		rm -rf $(VENV); \
		python3 -m venv $(VENV); \
	fi
	@$(PIP) install -q --upgrade pip
	@$(PIP) install -q -r requirements.txt
	@test -f .env || (cp .env.example .env && echo "→ создан .env — впиши ключи!")
	@echo "✓ Готово. Запуск: make run"

run:  ## Запустить десктоп-приложение
	@$(PY) main.py

cli:  ## Запустить CLI-версию (для отладки)
	@$(PY) cli.py

clean:  ## Удалить кэш Python
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ Кэш очищен"

reset:  ## Полный сброс: удалить venv и кэш (требует переустановки)
	@rm -rf $(VENV)
	@$(MAKE) clean
	@echo "✓ venv удалён. Установка: make install"
