"""Главное окно — overlay с тёмной темой, перетаскиваемое, поверх всех."""
from __future__ import annotations

from PyQt6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QSize,
    Qt,
    QTimer,
)
from PyQt6.QtGui import QColor, QPainter, QPainterPath
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizeGrip,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.config import DEFAULT_WINDOW_SEC
from app.core.profiles import Profile

from .theme import COLORS, STYLESHEET


class _DraggableHeader(QWidget):
    """Шапка которая ловит drag для перетаскивания окна."""

    def __init__(self, parent):
        super().__init__(parent)
        self._drag_offset: QPoint | None = None

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = ev.globalPosition().toPoint() - self.window().pos()
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if self._drag_offset is not None and ev.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(ev.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        self._drag_offset = None
        super().mouseReleaseEvent(ev)


class MainWindow(QWidget):
    """Основное окно ассистента."""

    def __init__(self, profiles: dict[str, Profile]):
        super().__init__()
        self.profiles = profiles
        self._current_profile_id: str | None = None
        self._setup_window()
        self._build_ui()
        self.setStyleSheet(STYLESHEET)

    # ── Setup ────────────────────────────────────────────────────────────
    def _setup_window(self) -> None:
        self.setObjectName("rootWindow")
        self.setWindowTitle("Assistant")
        # Frameless + всегда поверх
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool  # не показывается в Dock
        )
        # Прозрачный фон — рисуем скруглённые углы сами
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(480, 380)
        self.setMinimumSize(380, 280)

    def _build_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("root")
        # Мягкая тень вокруг окна
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 160))
        root.setGraphicsEffect(shadow)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 12, 20, 28)  # место под тень
        outer.addWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Шапка ──
        layout.addWidget(self._build_header())

        # ── Центр: транскрипт + ответ ──
        content = QVBoxLayout()
        content.setContentsMargins(14, 12, 14, 12)
        content.setSpacing(10)

        self.transcript_label = QLabel("Транскрипт появится здесь после ⌘R")
        self.transcript_label.setObjectName("transcript")
        self.transcript_label.setWordWrap(True)
        self.transcript_label.setMaximumHeight(80)
        content.addWidget(self.transcript_label)

        self.answer_view = QTextEdit()
        self.answer_view.setObjectName("answer")
        self.answer_view.setReadOnly(True)
        self.answer_view.setPlaceholderText("Здесь появится ответ Claude. Нажми ⌘R или ⌘Y чтобы начать.")
        content.addWidget(self.answer_view, stretch=1)

        # Скрытое поле для ввода заметки (раскрывается по ⌘Y)
        self.note_input = QTextEdit()
        self.note_input.setObjectName("noteInput")
        self.note_input.setPlaceholderText("Напиши свой вопрос или уточнение... ⌘↵ — отправить, Esc — отмена")
        self.note_input.setMaximumHeight(80)
        self.note_input.setVisible(False)
        self.note_input.installEventFilter(self)
        content.addWidget(self.note_input)

        layout.addLayout(content, stretch=1)

        # ── Низ: кнопки + счётчик ──
        layout.addWidget(self._build_footer())

    def _build_header(self) -> QWidget:
        header = _DraggableHeader(self)
        header.setObjectName("header")
        header.setFixedHeight(48)
        h = QHBoxLayout(header)
        h.setContentsMargins(14, 0, 10, 0)
        h.setSpacing(8)

        self.status_dot = QLabel("●")
        self.status_dot.setObjectName("statusDot")
        self.status_dot.setStyleSheet(f"color: {COLORS['success']}; font-size: 14px;")

        self.status_label = QLabel("Слушаю")
        self.status_label.setObjectName("title")

        h.addWidget(self.status_dot)
        h.addWidget(self.status_label)
        h.addStretch(1)

        self.profile_combo = QComboBox()
        for pid, profile in self.profiles.items():
            self.profile_combo.addItem(f"{profile.icon}  {profile.name}", userData=pid)
        h.addWidget(self.profile_combo)

        # Закрыть
        close_btn = QPushButton("✕")
        close_btn.setObjectName("iconBtn")
        close_btn.setFixedSize(28, 28)
        close_btn.clicked.connect(QApplication.instance().quit)
        h.addWidget(close_btn)

        return header

    def _build_footer(self) -> QWidget:
        footer = QWidget(self)
        footer.setObjectName("footer")
        footer.setFixedHeight(50)
        h = QHBoxLayout(footer)
        h.setContentsMargins(14, 8, 14, 8)
        h.setSpacing(8)

        self.ask_btn = QPushButton(f"⌘R · Ответить")
        self.ask_btn.setObjectName("primary")

        self.note_btn = QPushButton("⌘Y · Заметка")
        self.clear_btn = QPushButton("⌘E · Очистить")

        h.addWidget(self.ask_btn)
        h.addWidget(self.note_btn)
        h.addWidget(self.clear_btn)
        h.addStretch(1)

        self.cost_badge = QLabel("0₽")
        self.cost_badge.setObjectName("costBadge")
        h.addWidget(self.cost_badge)

        # Уголок для ресайза
        grip = QSizeGrip(footer)
        grip.setStyleSheet("background: transparent;")
        h.addWidget(grip, alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)

        return footer

    # ── API (вызывается контроллером) ────────────────────────────────────
    def set_status(self, status: str, detail: str) -> None:
        color_map = {
            "listening": COLORS["success"],
            "transcribing": COLORS["warning"],
            "thinking": COLORS["accent"],
            "error": COLORS["danger"],
        }
        color = color_map.get(status, COLORS["text_secondary"])
        self.status_dot.setStyleSheet(f"color: {color}; font-size: 14px;")
        self.status_label.setText(detail)
        # Анимация пульсации когда не «listening»
        if status in ("transcribing", "thinking"):
            self._start_pulse()
        else:
            self._stop_pulse()

    def _start_pulse(self) -> None:
        if hasattr(self, "_pulse_timer") and self._pulse_timer.isActive():
            return
        self._pulse_phase = 0
        if not hasattr(self, "_pulse_timer"):
            self._pulse_timer = QTimer(self)
            self._pulse_timer.timeout.connect(self._pulse_step)
        self._pulse_timer.start(80)

    def _stop_pulse(self) -> None:
        if hasattr(self, "_pulse_timer"):
            self._pulse_timer.stop()
        # Возвращаем нормальный размер
        cur = self.status_dot.styleSheet()
        if "font-size:" in cur:
            self.status_dot.setStyleSheet(cur.split(";")[0] + "; font-size: 14px;")

    def _pulse_step(self) -> None:
        import math
        self._pulse_phase = (self._pulse_phase + 1) % 100
        # Размер 12..18px по синусу
        size = 13 + int(3 * (math.sin(self._pulse_phase / 8) + 1))
        cur = self.status_dot.styleSheet().split(";")[0]
        self.status_dot.setStyleSheet(f"{cur}; font-size: {size}px;")

    def set_transcript(self, text: str) -> None:
        if not text:
            self.transcript_label.setText("(тишина)")
        else:
            # Показываем сжато — последние 250 символов хватит для контекста
            shown = text if len(text) <= 250 else "…" + text[-250:]
            self.transcript_label.setText(shown)

    def set_answer(self, text: str) -> None:
        self.answer_view.setPlainText(text)
        # Прокручиваем наверх (актуально для длинных ответов)
        self.answer_view.verticalScrollBar().setValue(0)

    def set_cost(self, cost_str: str) -> None:
        self.cost_badge.setText(cost_str)

    def show_note_input(self) -> None:
        self.note_input.setVisible(True)
        self.note_input.setFocus()

    def hide_note_input(self) -> str:
        text = self.note_input.toPlainText().strip()
        self.note_input.clear()
        self.note_input.setVisible(False)
        return text

    def current_profile_id(self) -> str:
        return self.profile_combo.currentData()

    def show_error(self, message: str) -> None:
        # Просто кладём в ответ — некритично, надо быстро
        self.answer_view.setPlainText(f"⚠ {message}")

    # ── Перехват клавиш в поле заметки ──────────────────────────────────
    def eventFilter(self, obj, ev):
        if obj is self.note_input and ev.type().value == 6:  # QEvent::KeyPress
            from PyQt6.QtCore import QEvent
            from PyQt6.QtGui import QKeyEvent
            if isinstance(ev, QKeyEvent):
                # Esc → отмена
                if ev.key() == Qt.Key.Key_Escape:
                    self.hide_note_input()
                    return True
                # Cmd+Enter → отправка
                if (ev.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                        and ev.modifiers() & Qt.KeyboardModifier.MetaModifier):
                    # Сигнал «отправить заметку» эмитим через метод контроллера
                    if hasattr(self, "_on_send_note"):
                        self._on_send_note()
                    return True
        return super().eventFilter(obj, ev)

    # ── Рисуем тень/прозрачный фон (через QSS) ──────────────────────────
    def paintEvent(self, ev):
        # Прозрачный фон — root-виджет рисует свой стиль
        super().paintEvent(ev)
