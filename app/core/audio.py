"""Захват аудио: кольцевой буфер + выбор устройств + callback'и."""
from __future__ import annotations

import collections
import os
import sys
import threading
from dataclasses import dataclass

import numpy as np
import sounddevice as sd

from .config import SAMPLE_RATE


class RollingAudioBuffer:
    """Кольцевой буфер для последних N секунд аудио."""

    def __init__(self, seconds: int, sample_rate: int = SAMPLE_RATE):
        self.sample_rate = sample_rate
        self.max_samples = seconds * sample_rate
        self.buf: collections.deque[float] = collections.deque(maxlen=self.max_samples)
        self.lock = threading.Lock()

    def append(self, chunk: np.ndarray) -> None:
        with self.lock:
            self.buf.extend(chunk.tolist())

    def last_seconds(self, seconds: int) -> np.ndarray:
        n = min(seconds * self.sample_rate, len(self.buf))
        with self.lock:
            if n == 0:
                return np.zeros(0, dtype=np.float32)
            data = list(self.buf)[-n:]
        return np.array(data, dtype=np.float32)

    def current_seconds(self) -> float:
        with self.lock:
            return len(self.buf) / self.sample_rate

    def rms(self, window_sec: float = 0.5) -> float:
        """Громкость последних window_sec секунд (для индикатора звука)."""
        n = min(int(window_sec * self.sample_rate), len(self.buf))
        if n == 0:
            return 0.0
        with self.lock:
            data = np.array(list(self.buf)[-n:], dtype=np.float32)
        return float(np.sqrt(np.mean(data ** 2)))

    def clear(self) -> None:
        with self.lock:
            self.buf.clear()


@dataclass
class DevicePick:
    system_idx: int | None  # BlackHole — собеседник
    mic_idx: int | None     # микрофон — я

    def has_system(self) -> bool: return self.system_idx is not None
    def has_mic(self) -> bool: return self.mic_idx is not None


def pick_devices() -> DevicePick:
    """Автоматически подбирает BlackHole (для собеседника) и микрофон (для меня).
    ENV override: AUDIO_DEVICE_SYSTEM, AUDIO_DEVICE_MIC.
    """
    devices = sd.query_devices()
    candidates = [(i, d) for i, d in enumerate(devices) if d["max_input_channels"] > 0]

    sys_idx: int | None = None
    mic_idx: int | None = None

    # 1) Системный звук — BlackHole / Loopback / Aggregate
    for i, d in candidates:
        n = d["name"].lower()
        if "blackhole" in n or "loopback" in n:
            sys_idx = i
            break
    if sys_idx is None:
        for i, d in candidates:
            if "aggregate" in d["name"].lower():
                sys_idx = i
                break

    # 2) Микрофон — не-loopback. Предпочитаем MacBook/встроенный
    def _is_loopback(name: str) -> bool:
        n = name.lower()
        return "blackhole" in n or "loopback" in n or "aggregate" in n

    for i, d in candidates:
        n = d["name"].lower()
        if _is_loopback(n):
            continue
        if "macbook" in n or "встроен" in n or "built" in n:
            mic_idx = i
            break
    if mic_idx is None:
        for i, d in candidates:
            if not _is_loopback(d["name"]):
                mic_idx = i
                break

    # ENV override
    env_sys = os.environ.get("AUDIO_DEVICE_SYSTEM") or os.environ.get("AUDIO_DEVICE")
    env_mic = os.environ.get("AUDIO_DEVICE_MIC")
    if env_sys:
        try: sys_idx = int(env_sys)
        except ValueError: pass
    if env_mic:
        try: mic_idx = int(env_mic)
        except ValueError: pass

    if sys_idx is None and mic_idx is None:
        raise RuntimeError(
            "Не найдено ни одного устройства ввода. Проверь Audio MIDI Setup."
        )
    return DevicePick(system_idx=sys_idx, mic_idx=mic_idx)


def list_input_devices() -> list[tuple[int, str, int]]:
    """Список всех устройств ввода: [(idx, name, sample_rate), ...]"""
    return [
        (i, d["name"], int(d["default_samplerate"]))
        for i, d in enumerate(sd.query_devices())
        if d["max_input_channels"] > 0
    ]


def device_name(idx: int) -> str:
    try:
        return sd.query_devices(idx)["name"]
    except Exception:
        return f"device #{idx}"


def make_callback(buffer: RollingAudioBuffer, label: str = ""):
    """Создаёт sounddevice callback, который пишет в указанный буфер."""
    def _cb(indata, frames, time_info, status):
        if status:
            print(f"[audio:{label}] {status}", file=sys.stderr)
        mono = indata.mean(axis=1) if indata.shape[1] > 1 else indata[:, 0]
        buffer.append(mono.astype(np.float32))
    return _cb
