"""Локальный счётчик стоимости — себестоимость по API. Без наценок, без отчётов."""
from __future__ import annotations

from dataclasses import dataclass, field

from .config import (
    PRICE_CLAUDE_INPUT_PER_M_USD,
    PRICE_CLAUDE_OUTPUT_PER_M_USD,
    PRICE_TRANSCRIBE_PER_MIN_USD,
    USD_TO_RUB,
)


@dataclass
class Cost:
    transcribe_sec: float = 0.0
    claude_input_tokens: int = 0
    claude_output_tokens: int = 0
    requests: int = 0

    def add_transcribe(self, seconds: float) -> None:
        self.transcribe_sec += seconds

    def add_claude(self, input_tokens: int, output_tokens: int) -> None:
        self.claude_input_tokens += input_tokens
        self.claude_output_tokens += output_tokens
        self.requests += 1

    @property
    def usd(self) -> float:
        return (
            (self.transcribe_sec / 60.0) * PRICE_TRANSCRIBE_PER_MIN_USD
            + self.claude_input_tokens / 1_000_000 * PRICE_CLAUDE_INPUT_PER_M_USD
            + self.claude_output_tokens / 1_000_000 * PRICE_CLAUDE_OUTPUT_PER_M_USD
        )

    @property
    def rub(self) -> float:
        return self.usd * USD_TO_RUB

    def format_short(self) -> str:
        rub = self.rub
        if rub < 1:
            return f"{rub*100:.0f}коп"
        if rub < 10:
            return f"{rub:.1f}₽"
        return f"{rub:.0f}₽"
