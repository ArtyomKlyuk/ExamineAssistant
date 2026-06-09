#!/usr/bin/env python3
"""ExamineAssistant — десктоп-приложение на Mac. Точка входа.

Запуск:
    python3 main.py

Хоткеи (работают глобально, требуют Accessibility доступа в System Settings):
    ⌘+R / ⌘+К  — ответить (последние 60 сек разговора)
    ⌘+Y / ⌘+Н  — открыть/закрыть поле ввода своей заметки
    ⌘+E / ⌘+У  — очистить буфер и историю
    ⌘+H / ⌘+Р  — скрыть/показать окно
"""
from __future__ import annotations

import signal
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from app.core.config import ensure_keys
from app.ui.controller import Controller


def main() -> int:
    # Проверка ключей — упадём рано если их нет
    ensure_keys()

    # Ctrl+C в терминале — корректное завершение Qt-приложения
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    app.setApplicationName("ExamineAssistant")
    app.setQuitOnLastWindowClosed(False)  # ⌘H не должен завершать программу

    # macOS — не показывать иконку в Dock (только overlay)
    if sys.platform == "darwin":
        try:
            from AppKit import NSApp, NSApplicationActivationPolicyAccessory
            NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
        except Exception:
            pass

    controller = Controller()
    controller.start()

    exit_code = app.exec()
    controller.stop()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
