"""Загрузка конфигурации: ключи API, модели, пути."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent

# .env рядом с проектом
load_dotenv(ROOT / ".env")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


def ensure_keys() -> None:
    """Падаем рано если ключей нет, вместо непонятных ошибок API позже."""
    if not OPENAI_API_KEY or not ANTHROPIC_API_KEY:
        sys.exit(
            "ОШИБКА: нет API-ключей.\n"
            "Создай файл .env рядом с main.py со строками:\n"
            "  OPENAI_API_KEY=sk-...\n"
            "  ANTHROPIC_API_KEY=sk-ant-...\n"
            "Шаблон в .env.example"
        )


# Модели
CLAUDE_MODEL = "claude-sonnet-4-6"
CLAUDE_FALLBACKS = ["claude-sonnet-4-5", "claude-opus-4-5", "claude-3-5-sonnet-latest"]
TRANSCRIBE_MODEL = "gpt-4o-transcribe"
TRANSCRIBE_FALLBACKS = ["gpt-4o-mini-transcribe", "whisper-1"]

# Аудио
SAMPLE_RATE = 16000
CHANNELS = 1
BUFFER_SECONDS = 120
DEFAULT_WINDOW_SEC = 60

# Пути
PROFILES_DIR = ROOT / "profiles"
OUTPUTS_DIR = ROOT / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)


# Стоимости (для счётчика — себестоимость, без наценки)
# https://platform.openai.com/docs/pricing  +  https://docs.anthropic.com/en/docs/about-claude/pricing
USD_TO_RUB = 80.0  # фиксированный курс для простоты

PRICE_TRANSCRIBE_PER_MIN_USD = 0.006   # gpt-4o-transcribe
PRICE_CLAUDE_INPUT_PER_M_USD = 3.0     # sonnet 4.6 input
PRICE_CLAUDE_OUTPUT_PER_M_USD = 15.0   # sonnet 4.6 output
