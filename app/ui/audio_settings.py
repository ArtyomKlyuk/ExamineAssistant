"""Диалог выбора аудиоустройств."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core import audio as core_audio

from .theme import COLORS, STYLESHEET


class AudioSettings(QDialog):
    """Выбор устройства собеседника (BlackHole) и микрофона.

    Использование:
        dlg = AudioSettings(parent, current_system=1, current_mic=4)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            sys_idx, mic_idx = dlg.get_selection()
    """

    def __init__(self, parent: QWidget | None, current_system: int | None, current_mic: int | None):
        super().__init__(parent)
        self._devices = core_audio.list_input_devices()  # [(idx, name, sr)]
        self._build(current_system, current_mic)
        self.setStyleSheet(STYLESHEET)

    def _build(self, current_system: int | None, current_mic: int | None) -> None:
        self.setWindowTitle("Настройки звука")
        self.setMinimumWidth(460)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(14)

        title = QLabel("Аудиоустройства")
        title.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {COLORS['text']};")
        layout.addWidget(title)

        hint = QLabel(
            "Собеседник — это системный звук (BlackHole), его слышит приложение из Zoom/Teams.\n"
            "Микрофон — твой голос."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        layout.addWidget(hint)

        form = QFormLayout()
        form.setSpacing(10)

        self.system_combo = QComboBox()
        self.mic_combo = QComboBox()
        self.system_combo.addItem("— выключено —", userData=None)
        self.mic_combo.addItem("— выключено —", userData=None)
        for idx, name, sr in self._devices:
            label = f"[{idx}] {name}"
            self.system_combo.addItem(label, userData=idx)
            self.mic_combo.addItem(label, userData=idx)

        self._select(self.system_combo, current_system)
        self._select(self.mic_combo, current_mic)

        form.addRow(self._label("🔊 Собеседник"), self.system_combo)
        form.addRow(self._label("🎙 Микрофон"), self.mic_combo)
        layout.addLayout(form)

        # Кнопки
        btn_row = QHBoxLayout()
        refresh = QPushButton("⟳ Обновить список")
        refresh.clicked.connect(self._refresh)
        btn_row.addWidget(refresh)
        btn_row.addStretch(1)

        cancel = QPushButton("Отмена")
        cancel.clicked.connect(self.reject)
        apply = QPushButton("Применить")
        apply.setObjectName("primary")
        apply.clicked.connect(self.accept)
        btn_row.addWidget(cancel)
        btn_row.addWidget(apply)
        layout.addLayout(btn_row)

    def _label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        return lbl

    def _select(self, combo: QComboBox, idx: int | None) -> None:
        pos = combo.findData(idx)
        if pos >= 0:
            combo.setCurrentIndex(pos)

    def _refresh(self) -> None:
        cur_sys = self.system_combo.currentData()
        cur_mic = self.mic_combo.currentData()
        self._devices = core_audio.list_input_devices()
        self.system_combo.clear()
        self.mic_combo.clear()
        self.system_combo.addItem("— выключено —", userData=None)
        self.mic_combo.addItem("— выключено —", userData=None)
        for idx, name, sr in self._devices:
            label = f"[{idx}] {name}"
            self.system_combo.addItem(label, userData=idx)
            self.mic_combo.addItem(label, userData=idx)
        self._select(self.system_combo, cur_sys)
        self._select(self.mic_combo, cur_mic)

    def get_selection(self) -> tuple[int | None, int | None]:
        return self.system_combo.currentData(), self.mic_combo.currentData()
