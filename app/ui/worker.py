"""Фоновый рабочий поток: аудио → транскрипция → Claude → сигналы в UI."""
from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass

import sounddevice as sd
from PyQt6.QtCore import QObject, QThread, pyqtSignal

from app.core import audio as core_audio
from app.core import billing as core_billing
from app.core import claude as core_claude
from app.core import system_audio as core_system_audio
from app.core import transcribe as core_transcribe
from app.core.config import BUFFER_SECONDS, DEFAULT_WINDOW_SEC, SAMPLE_RATE
from app.core.profiles import Profile


@dataclass
class Request:
    window_sec: int
    user_note: str = ""


class AssistantWorker(QObject):
    """Один объект, работающий в QThread.
    Держит аудио буферы, обрабатывает запросы, шлёт сигналы в UI.
    """

    # Сигналы наружу
    status_changed = pyqtSignal(str, str)        # status, detail (e.g. "listening", "Слушаю собеседника")
    transcript_ready = pyqtSignal(str)           # текст диалога с метками
    answer_ready = pyqtSignal(str)               # ответ Claude
    answer_chunk = pyqtSignal(str)               # для будущего стриминга — пока не используется
    error = pyqtSignal(str)
    cost_updated = pyqtSignal(object)            # core_billing.Cost
    audio_levels = pyqtSignal(float, float)      # rms sys, rms mic (0..1) для индикатора

    def __init__(self):
        super().__init__()
        self.sys_buffer = core_audio.RollingAudioBuffer(BUFFER_SECONDS)
        self.mic_buffer = core_audio.RollingAudioBuffer(BUFFER_SECONDS)
        self.history: list[dict] = []
        self.cost = core_billing.Cost()
        self.profile: Profile | None = None
        self._queue: queue.Queue[Request] = queue.Queue()
        self._streams: list = []
        self._running = True
        self._levels_timer: threading.Thread | None = None
        self._levels_running = False
        self.current_system_idx: int | None = None
        self.current_mic_idx: int | None = None
        # ScreenCaptureKit-захват системного звука (без BlackHole)
        self._sck_capture: core_system_audio.SystemAudioCapture | None = None
        self.system_source: str = "none"   # "screencapturekit" | "blackhole" | "none"

    # ── Управление профилем ─────────────────────────────────────────────
    def set_profile(self, profile: Profile, clear_history: bool = True) -> None:
        self.profile = profile
        if clear_history:
            self.history.clear()

    # ── Старт/стоп аудио потоков ────────────────────────────────────────
    def start_audio(
        self,
        system_idx: int | None = None,
        mic_idx: int | None = None,
        auto: bool = True,
        prefer_sck: bool = True,
    ) -> core_audio.DevicePick:
        """Запускает захват.

        Системный звук (собеседник):
          1. ScreenCaptureKit (без BlackHole) — если доступен и prefer_sck=True
          2. иначе BlackHole/Loopback через sounddevice
        Микрофон (я): всегда через sounddevice.
        """
        if auto:
            devices = core_audio.pick_devices()
        else:
            devices = core_audio.DevicePick(system_idx=system_idx, mic_idx=mic_idx)

        self.current_mic_idx = devices.mic_idx

        # ── Системный звук ──
        self.system_source = "none"
        sck_started = False
        if prefer_sck and core_system_audio.is_available():
            self._sck_capture = core_system_audio.SystemAudioCapture(
                on_audio=self.sys_buffer.append
            )
            sck_started = self._sck_capture.start()
            if sck_started:
                self.system_source = "screencapturekit"
                self.current_system_idx = None  # SCK не использует device index
            else:
                # не получилось (нет разрешения Screen Recording) → попробуем BlackHole
                self._sck_capture = None

        if not sck_started and devices.has_system():
            stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                device=devices.system_idx,
                callback=core_audio.make_callback(self.sys_buffer, "sys"),
                blocksize=int(SAMPLE_RATE * 0.1),
            )
            stream.start()
            self._streams.append(stream)
            self.system_source = "blackhole"
            self.current_system_idx = devices.system_idx
        elif sck_started:
            pass  # уже работает через SCK
        else:
            self.current_system_idx = None

        # ── Микрофон ──
        if devices.has_mic():
            stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                device=devices.mic_idx,
                callback=core_audio.make_callback(self.mic_buffer, "mic"),
                blocksize=int(SAMPLE_RATE * 0.1),
            )
            stream.start()
            self._streams.append(stream)

        if not self._levels_running:
            self._start_level_monitor()
        return devices

    def restart_audio(
        self, system_idx: int | None, mic_idx: int | None, prefer_sck: bool = False
    ) -> core_audio.DevicePick:
        """Останавливает текущие потоки и запускает с новыми устройствами.
        Используется при ручном выборе устройств в UI.
        prefer_sck=False — раз пользователь явно выбрал устройство, используем его,
        не перехватываем через ScreenCaptureKit."""
        self._stop_all_inputs()
        self.sys_buffer.clear()
        self.mic_buffer.clear()
        return self.start_audio(
            system_idx=system_idx, mic_idx=mic_idx, auto=False, prefer_sck=prefer_sck
        )

    def _stop_all_inputs(self) -> None:
        for s in self._streams:
            try:
                s.stop(); s.close()
            except Exception:
                pass
        self._streams.clear()
        if self._sck_capture is not None:
            try:
                self._sck_capture.stop()
            except Exception:
                pass
            self._sck_capture = None

    def _start_level_monitor(self) -> None:
        """Отдельный поток шлёт rms-сигналы каждые 100 мс для индикатора."""
        self._levels_running = True
        def _loop():
            while self._running:
                sys_rms = self.sys_buffer.rms(0.2)
                mic_rms = self.mic_buffer.rms(0.2)
                self.audio_levels.emit(sys_rms, mic_rms)
                time.sleep(0.1)
        t = threading.Thread(target=_loop, daemon=True)
        t.start()
        self._levels_timer = t

    def stop_audio(self) -> None:
        self._running = False
        self._stop_all_inputs()

    # ── Очередь запросов ────────────────────────────────────────────────
    def request_answer(self, window_sec: int = DEFAULT_WINDOW_SEC, user_note: str = "") -> None:
        self._queue.put(Request(window_sec=window_sec, user_note=user_note))

    def clear_state(self) -> None:
        self.sys_buffer.clear()
        self.mic_buffer.clear()
        self.history.clear()

    # ── Основной цикл обработки (запускается в QThread) ──────────────────
    def run(self) -> None:
        self.status_changed.emit("listening", "Слушаю")
        while self._running:
            try:
                req = self._queue.get(timeout=0.3)
            except queue.Empty:
                continue
            try:
                self._handle(req)
            except Exception as e:
                self.error.emit(str(e))
                self.status_changed.emit("listening", "Слушаю")

    def _handle(self, req: Request) -> None:
        if self.profile is None:
            self.error.emit("Профиль не выбран")
            return

        self.status_changed.emit("transcribing", "Транскрибирую…")
        sys_audio = self.sys_buffer.last_seconds(req.window_sec)
        mic_audio = self.mic_buffer.last_seconds(req.window_sec)

        t = core_transcribe.transcribe_dialog(sys_audio, mic_audio)
        self.cost.add_transcribe(t.seconds_billed)

        if t.text or req.user_note:
            self.transcript_ready.emit(t.text)
        else:
            self.error.emit("Тишина в обоих потоках. Подожди или напиши заметку.")
            self.status_changed.emit("listening", "Слушаю")
            return

        self.status_changed.emit("thinking", "Думаю в Claude…")
        result = core_claude.ask(
            transcript=t.text,
            history=self.history,
            system_prompt=self.profile.system_prompt,
            user_note=req.user_note,
        )
        self.cost.add_claude(result.input_tokens, result.output_tokens)

        # Автообрезка истории — экономит токены
        core_claude.trim_history(self.history, keep_pairs=10)

        self.answer_ready.emit(result.text)
        self.cost_updated.emit(self.cost)
        self.status_changed.emit("listening", "Слушаю")


def create_worker_thread(worker: AssistantWorker) -> QThread:
    """Запускает worker в отдельном QThread."""
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    return thread
