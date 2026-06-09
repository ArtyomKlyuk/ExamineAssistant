"""Транскрипция аудио через OpenAI."""
from __future__ import annotations

import concurrent.futures
import io
from dataclasses import dataclass

import numpy as np
import soundfile as sf
from openai import OpenAI

from .config import (
    OPENAI_API_KEY,
    SAMPLE_RATE,
    TRANSCRIBE_FALLBACKS,
    TRANSCRIBE_MODEL,
)

_client = OpenAI(api_key=OPENAI_API_KEY)


@dataclass
class TranscribeResult:
    text: str          # склеенный диалог [Собеседник]/[Я]
    sys_text: str
    mic_text: str
    seconds_billed: float  # сек аудио ушедших в API (для счётчика)


def _is_silence(audio: np.ndarray) -> bool:
    if audio.size == 0:
        return True
    rms = float(np.sqrt(np.mean(audio ** 2)))
    return rms < 1e-4


def transcribe_one(audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> str:
    """Один поток → текст. Возвращает пустую строку для тишины."""
    if _is_silence(audio):
        return ""

    buf = io.BytesIO()
    sf.write(buf, audio, sample_rate, format="WAV", subtype="PCM_16")
    raw = buf.getvalue()

    last_err: Exception | None = None
    for model in [TRANSCRIBE_MODEL, *TRANSCRIBE_FALLBACKS]:
        try:
            file_buf = io.BytesIO(raw)
            file_buf.name = "audio.wav"
            resp = _client.audio.transcriptions.create(
                model=model, file=file_buf, language="ru"
            )
            return resp.text.strip()
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(f"Все модели транскрипции недоступны: {last_err}")


def transcribe_dialog(
    sys_audio: np.ndarray,
    mic_audio: np.ndarray,
    sample_rate: int = SAMPLE_RATE,
) -> TranscribeResult:
    """Параллельная транскрипция двух потоков. Результат с метками говорящих."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        f_sys = ex.submit(transcribe_one, sys_audio, sample_rate)
        f_mic = ex.submit(transcribe_one, mic_audio, sample_rate)
        sys_text = f_sys.result()
        mic_text = f_mic.result()

    parts: list[str] = []
    if sys_text:
        parts.append(f"[Собеседник]: {sys_text}")
    if mic_text:
        parts.append(f"[Я]: {mic_text}")

    # Считаем для биллинга только не-тишинные секунды
    seconds = 0.0
    if sys_text:
        seconds += sys_audio.size / sample_rate
    if mic_text:
        seconds += mic_audio.size / sample_rate

    return TranscribeResult(
        text="\n".join(parts),
        sys_text=sys_text,
        mic_text=mic_text,
        seconds_billed=seconds,
    )
