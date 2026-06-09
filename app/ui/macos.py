"""macOS-специфичные вещи: невидимость окна для записи, иконка в menubar."""
from __future__ import annotations

import sys

# NSWindowSharingType.None = 0 → окно не видно в screen capture
NS_WINDOW_SHARING_NONE = 0


def make_window_invisible_to_capture(qwindow_winid: int) -> bool:
    """Скрывает окно из захвата экрана (Zoom/Teams/Meet не увидят).
    Возвращает True если получилось.
    """
    if sys.platform != "darwin":
        return False
    try:
        # Импортируем тут, потому что PyObjC может быть не установлен на других платформах
        import objc
        from AppKit import NSApp  # noqa: F401
        from Foundation import NSObject  # noqa: F401

        # PyQt6 winId() возвращает PyCapsule, оборачивающий NSView*
        # Можно достать NSWindow через стандартный AppKit-механизм:
        from AppKit import NSView
        nsview = objc.objc_object(c_void_p=qwindow_winid)
        if nsview is None:
            return False
        nswindow = nsview.window()
        if nswindow is None:
            return False
        nswindow.setSharingType_(NS_WINDOW_SHARING_NONE)
        return True
    except Exception as e:
        print(f"[macos] не смог сделать окно невидимым: {e}", file=sys.stderr)
        return False
