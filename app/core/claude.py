"""Запросы к Claude."""
from __future__ import annotations

from dataclasses import dataclass

from anthropic import Anthropic

from .config import ANTHROPIC_API_KEY, CLAUDE_FALLBACKS, CLAUDE_MODEL

_client = Anthropic(api_key=ANTHROPIC_API_KEY)


@dataclass
class ClaudeResult:
    text: str
    input_tokens: int
    output_tokens: int
    model: str


def ask(
    transcript: str,
    history: list[dict],
    system_prompt: str,
    user_note: str = "",
    max_tokens: int = 2048,
) -> ClaudeResult:
    """Спрашивает Claude. Мутирует history (добавляет user + assistant сообщения).
    Поддерживает 3 режима:
        - только текст (user_note без transcript)
        - только аудио (transcript без user_note)
        - аудио + текст
    """
    transcript = transcript.strip()
    user_note = user_note.strip()

    if user_note and not transcript:
        user_msg = (
            "Мой вопрос / задание (текстом, аудио нет):\n"
            "---\n"
            f"{user_note}\n"
            "---\n\n"
            "Ответь от моего лица — так, как я должен это сказать или написать."
        )
    elif user_note and transcript:
        user_msg = (
            "Транскрипт последних реплик (может быть с ошибками распознавания):\n"
            "---\n"
            f"{transcript}\n"
            "---\n\n"
            "Моя заметка / вопрос (приоритетный сигнал):\n"
            "---\n"
            f"{user_note}\n"
            "---\n\n"
            "Учитывай транскрипт как контекст, но отвечай именно на мою заметку — от моего лица."
        )
    else:
        user_msg = (
            "Транскрипт последних реплик (может быть с ошибками распознавания):\n"
            "---\n"
            f"{transcript if transcript else '(пусто)'}\n"
            "---\n\n"
            "Скажи от моего лица то, что я должен ответить прямо сейчас."
        )

    history.append({"role": "user", "content": user_msg})

    last_err: Exception | None = None
    for model in [CLAUDE_MODEL, *CLAUDE_FALLBACKS]:
        try:
            resp = _client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=history,
            )
            text = "".join(b.text for b in resp.content if hasattr(b, "text"))
            history.append({"role": "assistant", "content": text})
            return ClaudeResult(
                text=text,
                input_tokens=resp.usage.input_tokens,
                output_tokens=resp.usage.output_tokens,
                model=model,
            )
        except Exception as e:
            last_err = e
            continue

    # Откатываем неудачный user-message чтобы история не была кривой
    history.pop()
    raise RuntimeError(f"Все модели Claude недоступны: {last_err}")


def trim_history(history: list[dict], keep_pairs: int = 10) -> None:
    """Оставить только последние keep_pairs пар (user+assistant). Экономит токены."""
    if len(history) <= keep_pairs * 2:
        return
    del history[: len(history) - keep_pairs * 2]
