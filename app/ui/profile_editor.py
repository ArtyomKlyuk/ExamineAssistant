"""Диалог создания / редактирования профиля."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtGui import QColor

from app.core.profiles import Profile

from .theme import COLORS, STYLESHEET

ICONS = ["📚", "💻", "💬", "🗓️", "🌍", "🚀", "🎓", "🩺", "⚖️", "💼", "🎨", "🔬", "📊", "🧠", "🛠️", "📝"]
LENGTHS = [
    ("short", "Короткий (~30 сек)"),
    ("medium", "Средний (~1 мин)"),
    ("long", "Развёрнутый (~2-4 мин)"),
]


class ProfileEditor(QDialog):
    """Модальное окно для создания или редактирования профиля.

    Использование:
        dlg = ProfileEditor(parent, profile=existing)  # None = создание
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_profile = dlg.get_profile()
    """

    def __init__(self, parent: QWidget | None, profile: Profile | None = None):
        super().__init__(parent)
        self._editing = profile is not None
        self._original = profile
        self._build()
        self.setStyleSheet(STYLESHEET)
        if profile:
            self._fill(profile)

    def _build(self) -> None:
        self.setWindowTitle("Профиль" if self._editing else "Новый профиль")
        self.setMinimumSize(520, 540)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(14)

        title = QLabel("Редактирование профиля" if self._editing else "Новый профиль")
        title.setObjectName("title")
        title.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {COLORS['text']};")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # Иконка
        icon_row = QHBoxLayout()
        self.icon_combo = QComboBox()
        for ic in ICONS:
            self.icon_combo.addItem(ic)
        self.icon_combo.setFixedWidth(90)
        icon_row.addWidget(self.icon_combo)
        icon_row.addStretch(1)
        form.addRow(self._label("Иконка"), self._wrap(icon_row))

        # Название
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Например: История России")
        self.name_edit.setStyleSheet(self._line_style())
        form.addRow(self._label("Название"), self.name_edit)

        # Описание
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("Короткое описание для списка")
        self.desc_edit.setStyleSheet(self._line_style())
        form.addRow(self._label("Описание"), self.desc_edit)

        # Длина ответа
        self.length_combo = QComboBox()
        for v, label in LENGTHS:
            self.length_combo.addItem(label, userData=v)
        form.addRow(self._label("Длина ответа"), self.length_combo)

        layout.addLayout(form)

        # System prompt — большое поле
        prompt_label = QLabel("Системный промпт (инструкции для Claude)")
        prompt_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        layout.addWidget(prompt_label)

        self.prompt_edit = QTextEdit()
        self.prompt_edit.setObjectName("noteInput")
        self.prompt_edit.setPlaceholderText(
            "Опиши кто ты, по какому предмету, как должен отвечать.\n\n"
            "Например:\n"
            "Ты — мой помощник на экзамене по истории России.\n"
            "Отвечай от моего лица, короткими ответами по 30 секунд...\n"
        )
        layout.addWidget(self.prompt_edit, stretch=1)

        # Кнопки
        btns = QDialogButtonBox()
        self.save_btn = QPushButton("Сохранить")
        self.save_btn.setObjectName("primary")
        self.save_btn.clicked.connect(self._on_save)

        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        if self._editing and self._original.id not in {"general", "study", "interview_it"}:
            self.delete_btn = QPushButton("Удалить")
            self.delete_btn.clicked.connect(self._on_delete)
            self.delete_btn.setStyleSheet(
                f"color: {COLORS['danger']};"
            )
            btn_row.addWidget(self.delete_btn)
            btn_row.addStretch(1)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

    def _label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        return lbl

    def _line_style(self) -> str:
        return (
            f"background-color: {COLORS['bg_elev']};"
            f"color: {COLORS['text']};"
            f"border: 1px solid {COLORS['border']};"
            f"border-radius: 7px;"
            f"padding: 6px 10px;"
            f"font-size: 13px;"
        )

    def _wrap(self, layout) -> QWidget:
        w = QWidget()
        w.setLayout(layout)
        return w

    def _fill(self, profile: Profile) -> None:
        # Иконка
        if profile.icon in ICONS:
            self.icon_combo.setCurrentIndex(ICONS.index(profile.icon))
        else:
            self.icon_combo.insertItem(0, profile.icon)
            self.icon_combo.setCurrentIndex(0)
        self.name_edit.setText(profile.name)
        self.desc_edit.setText(profile.description)
        # Длина
        for i in range(self.length_combo.count()):
            if self.length_combo.itemData(i) == profile.answer_length:
                self.length_combo.setCurrentIndex(i)
                break
        self.prompt_edit.setPlainText(profile.system_prompt)

    def _on_save(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Ошибка", "Название не может быть пустым")
            return
        if not self.prompt_edit.toPlainText().strip():
            QMessageBox.warning(self, "Ошибка", "Системный промпт не может быть пустым")
            return
        self.accept()

    def _on_delete(self) -> None:
        reply = QMessageBox.question(
            self, "Удалить профиль?",
            f"Удалить «{self._original.name}»? Это действие нельзя отменить.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.done(2)  # 2 = «удалить» — отличается от accept (1) и reject (0)

    # ── Геттеры ─────────────────────────────────────────────────────────
    def get_form_data(self) -> dict:
        return {
            "name": self.name_edit.text().strip(),
            "description": self.desc_edit.text().strip(),
            "icon": self.icon_combo.currentText(),
            "answer_length": self.length_combo.currentData() or "short",
            "system_prompt": self.prompt_edit.toPlainText().strip(),
        }
