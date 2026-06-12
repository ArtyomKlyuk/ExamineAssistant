"""Захват системного звука через ScreenCaptureKit (macOS 13+).

Не требует BlackHole — берёт звук, который система выводит в динамики/наушники
(голос собеседника из Zoom/Teams/браузера), напрямую через Apple-фреймворк.

Требует разрешение «Запись экрана» (Screen Recording) в System Settings.
"""
from __future__ import annotations

import sys
import threading
import time
from typing import Callable

import numpy as np

# Доступно только на macOS 13+
SCK_AVAILABLE = False
if sys.platform == "darwin":
    try:
        import objc
        import ScreenCaptureKit as sck
        import CoreMedia as cm
        from Foundation import NSObject
        import libdispatch
        SCK_AVAILABLE = True
    except Exception as _e:  # pragma: no cover
        SCK_AVAILABLE = False


def is_available() -> bool:
    """ScreenCaptureKit-захват доступен (macOS 13+ и биндинги стоят)."""
    return SCK_AVAILABLE


# Целевой формат нашего пайплайна
TARGET_SR = 16000


class _AudioExtractor:
    """Достаёт float32-сэмплы из CMSampleBuffer (системный звук обычно
    48kHz float32, может быть стерео-планарный или интерливленный)."""

    @staticmethod
    def extract(sample_buffer) -> tuple[np.ndarray, int]:
        """Возвращает (mono_float32, sample_rate). Пустой массив при неудаче.

        ScreenCaptureKit-аудио: 48kHz, float32. ASBD приходит как tuple:
        (mSampleRate, mFormatID, mFormatFlags, mBytesPerPacket, mFramesPerPacket,
         mBytesPerFrame, mChannelsPerFrame, mBitsPerChannel, mReserved)
        """
        try:
            n = int(cm.CMSampleBufferGetNumSamples(sample_buffer))
            if n <= 0:
                return np.zeros(0, dtype=np.float32), 48000

            sr = 48000
            channels = 2
            bytes_per_frame = 4
            fmt = cm.CMSampleBufferGetFormatDescription(sample_buffer)
            if fmt is not None:
                asbd = cm.CMAudioFormatDescriptionGetStreamBasicDescription(fmt)
                if isinstance(asbd, (tuple, list)) and len(asbd) >= 8:
                    sr = int(asbd[0]) or 48000
                    bytes_per_frame = int(asbd[5]) or 4
                    channels = int(asbd[6]) or 2

            block = cm.CMSampleBufferGetDataBuffer(sample_buffer)
            if block is None:
                return np.zeros(0, dtype=np.float32), sr

            length = int(cm.CMBlockBufferGetDataLength(block))
            if length <= 0:
                return np.zeros(0, dtype=np.float32), sr

            # PyObjC: возвращает (err, filled_bytearray), а не пишет в out
            out = bytearray(length)
            ret = cm.CMBlockBufferCopyDataBytes(block, 0, length, out)
            if isinstance(ret, (tuple, list)):
                err, data = ret[0], ret[1]
            else:
                err, data = ret, out
            if err != 0 or data is None:
                return np.zeros(0, dtype=np.float32), sr

            samples = np.frombuffer(bytes(data), dtype=np.float32)
            if samples.size == 0:
                return np.zeros(0, dtype=np.float32), sr

            # Планарный (mBytesPerFrame == 4 при 2 каналах) vs интерливленный.
            # При планарном данные лежат [L L L ... R R R], при интерливленном [L R L R].
            if channels >= 2:
                is_interleaved = bytes_per_frame >= 4 * channels
                if is_interleaved:
                    usable = (samples.size // channels) * channels
                    mono = samples[:usable].reshape(-1, channels).mean(axis=1)
                else:
                    # планарный: первая половина — L, вторая — R. Усредняем.
                    half = (samples.size // channels)
                    if half > 0:
                        planes = samples[: half * channels].reshape(channels, half)
                        mono = planes.mean(axis=0)
                    else:
                        mono = samples
            else:
                mono = samples

            return mono.astype(np.float32), sr
        except Exception as e:
            print(f"[system_audio] extract error: {e}", file=sys.stderr)
            return np.zeros(0, dtype=np.float32), 48000


def _resample_to_16k(audio: np.ndarray, src_sr: int) -> np.ndarray:
    """Линейный ресэмплинг до 16kHz (быстро, достаточно для речи/Whisper)."""
    if audio.size == 0 or src_sr == TARGET_SR:
        return audio
    ratio = TARGET_SR / src_sr
    new_len = int(round(audio.size * ratio))
    if new_len <= 0:
        return np.zeros(0, dtype=np.float32)
    x_old = np.linspace(0, 1, audio.size, endpoint=False)
    x_new = np.linspace(0, 1, new_len, endpoint=False)
    return np.interp(x_new, x_old, audio).astype(np.float32)


if SCK_AVAILABLE:

    class _StreamDelegate(NSObject):
        """SCStreamOutput + SCStreamDelegate — принимает аудио-сэмплы."""

        def initWithCallback_(self, callback):
            self = objc.super(_StreamDelegate, self).init()
            if self is None:
                return None
            self._callback = callback  # (mono_float32_16k: np.ndarray) -> None
            self._count = 0
            return self

        # SCStreamOutput protocol: -stream:didOutputSampleBuffer:ofType:
        def stream_didOutputSampleBuffer_ofType_(self, stream, sample_buffer, output_type):
            if int(output_type) != 1:  # только аудио
                return
            mono, sr = _AudioExtractor.extract(sample_buffer)
            if mono.size == 0:
                return
            mono16 = _resample_to_16k(mono, sr)
            if mono16.size:
                try:
                    self._callback(mono16)
                except Exception as e:
                    print(f"[system_audio] callback error: {e}", file=sys.stderr)

        # SCStreamDelegate protocol
        def stream_didStopWithError_(self, stream, error):
            print(f"[system_audio] stream stopped: {error}", file=sys.stderr)


class SystemAudioCapture:
    """Высокоуровневый захват системного звука. Колбэк получает float32 16kHz mono."""

    def __init__(self, on_audio: Callable[[np.ndarray], None]):
        self._on_audio = on_audio
        self._stream = None
        self._delegate = None
        self._running = False
        self._error: str | None = None

    @property
    def error(self) -> str | None:
        return self._error

    def start(self) -> bool:
        """Запускает захват. True если стартовал успешно."""
        if not SCK_AVAILABLE:
            self._error = "ScreenCaptureKit недоступен (нужна macOS 13+)"
            return False

        done = threading.Event()
        result = {"ok": False}

        def _content_handler(content, error):
            try:
                if error is not None or content is None:
                    self._error = f"Нет доступа к захвату экрана: {error}"
                    done.set()
                    return

                displays = content.displays()
                if not displays or len(displays) == 0:
                    self._error = "Не найдено ни одного дисплея"
                    done.set()
                    return
                display = displays[0]

                # Фильтр: весь дисплей, без исключений
                filt = sck.SCContentFilter.alloc().initWithDisplay_excludingWindows_(
                    display, []
                )

                config = sck.SCStreamConfiguration.alloc().init()
                config.setCapturesAudio_(True)
                config.setExcludesCurrentProcessAudio_(True)  # не писать свой звук
                config.setSampleRate_(48000)
                config.setChannelCount_(2)
                # Минимизируем видео-нагрузку (звук всё равно требует видео-стрим)
                config.setWidth_(2)
                config.setHeight_(2)
                config.setMinimumFrameInterval_(cm.CMTimeMake(1, 1))  # 1 fps

                self._delegate = _StreamDelegate.alloc().initWithCallback_(self._on_audio)

                stream = sck.SCStream.alloc().initWithFilter_configuration_delegate_(
                    filt, config, self._delegate
                )

                # Добавляем audio output на отдельной очереди
                queue = libdispatch.dispatch_queue_create(b"sysaudio.queue", None)
                ok, add_err = stream.addStreamOutput_type_sampleHandlerQueue_error_(
                    self._delegate, 1, queue, None  # type 1 = audio
                )
                if not ok:
                    self._error = f"Не удалось добавить audio output: {add_err}"
                    done.set()
                    return

                def _start_handler(start_err):
                    if start_err is not None:
                        self._error = f"Не удалось запустить захват: {start_err}"
                    else:
                        self._stream = stream
                        self._running = True
                        result["ok"] = True
                    done.set()

                stream.startCaptureWithCompletionHandler_(_start_handler)
            except Exception as e:
                self._error = f"Ошибка инициализации: {e}"
                done.set()

        # Запрашиваем доступный контент (это вызовет prompt на Screen Recording)
        sck.SCShareableContent.getShareableContentWithCompletionHandler_(_content_handler)

        # Ждём завершения асинхронной цепочки (с таймаутом)
        done.wait(timeout=10.0)
        return result["ok"]

    def stop(self) -> None:
        self._running = False
        if self._stream is not None:
            try:
                self._stream.stopCaptureWithCompletionHandler_(lambda e: None)
            except Exception:
                pass
            self._stream = None
