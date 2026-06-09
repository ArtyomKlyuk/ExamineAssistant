"""Глобальные хоткеи через pynput. Шлёт Qt-сигналы в UI."""
from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal
from pynput import keyboard

# Зеркальные пары EN/RU
ANSWER_KEYS = {"r", "к"}    # ⌘+R / ⌘+К  → ответить
CLEAR_KEYS = {"e", "у"}     # ⌘+E / ⌘+У  → очистить
NOTE_KEYS = {"y", "н"}      # ⌘+Y / ⌘+Н  → заметка
HIDE_KEYS = {"h", "р"}      # ⌘+H / ⌘+Р  → свернуть/показать окно

# macOS virtual key codes для русской раскладки (где char отсутствует)
_VK_MAP = {15: "r", 14: "e", 16: "y", 4: "h"}


class HotkeyManager(QObject):
    answer_requested = pyqtSignal()
    clear_requested = pyqtSignal()
    note_requested = pyqtSignal()
    hide_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._cmd_down = False
        self._listener: keyboard.Listener | None = None

    def start(self) -> None:
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.start()

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()
            self._listener = None

    def _key_char(self, key) -> str | None:
        ch = getattr(key, "char", None)
        if ch:
            return ch.lower()
        vk = getattr(key, "vk", None)
        if vk in _VK_MAP:
            return _VK_MAP[vk]
        return None

    def _on_press(self, key):
        try:
            if key in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r):
                self._cmd_down = True
                return
            if not self._cmd_down:
                return
            ch = self._key_char(key)
            if ch is None:
                return
            if ch in ANSWER_KEYS:
                self.answer_requested.emit()
            elif ch in NOTE_KEYS:
                self.note_requested.emit()
            elif ch in CLEAR_KEYS:
                self.clear_requested.emit()
            elif ch in HIDE_KEYS:
                self.hide_requested.emit()
        except Exception as e:
            print(f"[hotkeys] error: {e}")

    def _on_release(self, key):
        if key in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r):
            self._cmd_down = False
