"""Тёмная тема и шрифты для PyQt6."""

# Цветовая палитра в стиле Linear/Arc/Raycast — тёмная, мягкая, без чистого чёрного
COLORS = {
    "bg": "#1a1a1f",            # фон окна
    "bg_elev": "#23232b",       # карточки, поднятые блоки
    "bg_hover": "#2d2d36",
    "border": "#2e2e38",
    "border_subtle": "#26262e",

    "text": "#e8e8ec",          # основной текст
    "text_secondary": "#9a9aa8",
    "text_muted": "#6a6a78",

    "accent": "#7c5cff",        # фиолетовый акцент
    "accent_hover": "#9477ff",
    "accent_dim": "#4d3ba6",

    "success": "#3ecf8e",       # запись идёт
    "warning": "#f5a524",
    "danger": "#f43f5e",

    "scrollbar": "#3a3a44",
    "scrollbar_hover": "#4a4a55",
}


STYLESHEET = f"""
* {{
    color: {COLORS['text']};
    font-family: -apple-system, "SF Pro Text", "Inter", "Segoe UI", sans-serif;
    font-size: 13px;
    outline: none;
}}

QWidget#root {{
    background-color: {COLORS['bg']};
    border-radius: 14px;
    border: 1px solid {COLORS['border']};
}}

QWidget#header {{
    background-color: transparent;
    border-bottom: 1px solid {COLORS['border_subtle']};
}}

QWidget#footer {{
    background-color: transparent;
    border-top: 1px solid {COLORS['border_subtle']};
}}

QLabel#title {{
    color: {COLORS['text']};
    font-size: 13px;
    font-weight: 600;
}}

QLabel#subtitle {{
    color: {COLORS['text_secondary']};
    font-size: 11px;
}}

QLabel#statusDot {{
    color: {COLORS['success']};
    font-size: 11px;
}}

QLabel#transcript {{
    color: {COLORS['text_secondary']};
    font-size: 12px;
    padding: 6px 10px;
    background-color: {COLORS['bg_elev']};
    border-radius: 8px;
}}

QTextEdit#answer {{
    background-color: transparent;
    color: {COLORS['text']};
    border: none;
    font-size: 15px;
    line-height: 1.5;
    padding: 4px;
}}

QTextEdit#noteInput {{
    background-color: {COLORS['bg_elev']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    font-size: 13px;
    padding: 8px;
}}

QTextEdit#noteInput:focus {{
    border: 1px solid {COLORS['accent']};
}}

QPushButton {{
    background-color: {COLORS['bg_elev']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 7px 14px;
    font-size: 12px;
    font-weight: 500;
}}

QPushButton:hover {{
    background-color: {COLORS['bg_hover']};
    border: 1px solid {COLORS['accent_dim']};
}}

QPushButton:pressed {{
    background-color: {COLORS['accent_dim']};
}}

QPushButton:disabled {{
    color: {COLORS['text_muted']};
    background-color: {COLORS['bg_elev']};
}}

QPushButton#primary {{
    background-color: {COLORS['accent']};
    border: 1px solid {COLORS['accent']};
    color: white;
    font-weight: 600;
}}

QPushButton#primary:hover {{
    background-color: {COLORS['accent_hover']};
    border: 1px solid {COLORS['accent_hover']};
}}

QPushButton#iconBtn {{
    background-color: transparent;
    border: none;
    padding: 4px 8px;
    font-size: 14px;
    color: {COLORS['text_secondary']};
}}

QPushButton#iconBtn:hover {{
    color: {COLORS['text']};
    background-color: {COLORS['bg_hover']};
    border-radius: 6px;
}}

QComboBox {{
    background-color: {COLORS['bg_elev']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border']};
    border-radius: 7px;
    padding: 5px 10px;
    font-size: 12px;
    min-width: 180px;
}}

QComboBox:hover {{
    border: 1px solid {COLORS['accent_dim']};
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {COLORS['text_secondary']};
    margin-right: 8px;
}}

QComboBox QAbstractItemView {{
    background-color: {COLORS['bg_elev']};
    border: 1px solid {COLORS['border']};
    border-radius: 7px;
    padding: 4px;
    selection-background-color: {COLORS['accent_dim']};
    color: {COLORS['text']};
}}

QLabel#costBadge {{
    color: {COLORS['text_muted']};
    font-size: 11px;
    padding: 3px 8px;
    background-color: {COLORS['bg_elev']};
    border-radius: 10px;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {COLORS['scrollbar']};
    border-radius: 4px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background: {COLORS['scrollbar_hover']};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
    border: none;
    height: 0;
}}
"""
