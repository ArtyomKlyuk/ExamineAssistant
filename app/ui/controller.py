"""Контроллер — связывает UI, worker и хоткеи."""
from __future__ import annotations

from PyQt6.QtCore import QObject, QThread
from PyQt6.QtWidgets import QDialog

from app.core import billing as core_billing
from app.core import profiles as core_profiles
from app.core.profiles import Profile

from .hotkeys import HotkeyManager
from .macos import make_window_invisible_to_capture
from .main_window import MainWindow
from .profile_editor import ProfileEditor
from .worker import AssistantWorker


class Controller(QObject):
    def __init__(self):
        super().__init__()
        self.profiles = core_profiles.load_profiles()
        self.window = MainWindow(self.profiles)
        self.worker = AssistantWorker()
        self.thread = QThread()
        self.worker.moveToThread(self.thread)
        self.hotkeys = HotkeyManager()
        self._wire_signals()

    def _wire_signals(self) -> None:
        # Кнопки UI
        self.window.ask_btn.clicked.connect(self._on_ask)
        self.window.note_btn.clicked.connect(self._on_note_toggle)
        self.window.clear_btn.clicked.connect(self._on_clear)
        self.window.profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        self.window.edit_profile_btn.clicked.connect(self._on_edit_profile)
        self.window.new_profile_btn.clicked.connect(self._on_new_profile)

        # Подменяем обработчик «отправить заметку» из main_window
        self.window._on_send_note = self._on_send_note

        # Worker → UI
        self.worker.status_changed.connect(self.window.set_status)
        self.worker.transcript_ready.connect(self.window.set_transcript)
        self.worker.answer_ready.connect(self.window.set_answer)
        self.worker.error.connect(self._on_error)
        self.worker.cost_updated.connect(self._on_cost_updated)

        # Запуск worker'а
        self.thread.started.connect(self.worker.run)

        # Хоткеи → UI
        self.hotkeys.answer_requested.connect(self._on_ask)
        self.hotkeys.note_requested.connect(self._on_note_toggle)
        self.hotkeys.clear_requested.connect(self._on_clear)
        self.hotkeys.hide_requested.connect(self._on_toggle_visibility)

    # ── Запуск ──────────────────────────────────────────────────────────
    def start(self) -> None:
        # Дефолтный профиль
        default = core_profiles.get_default(self.profiles)
        idx = self.window.profile_combo.findData(default.id)
        if idx >= 0:
            self.window.profile_combo.setCurrentIndex(idx)
        self.worker.set_profile(default)

        # Показ окна
        self.window.show()
        # Невидимость для записи
        ok = make_window_invisible_to_capture(int(self.window.winId()))
        if ok:
            print("✓ Окно невидимо для screen capture (Zoom/Teams не увидят)")
        else:
            print("⚠ Не удалось сделать окно невидимым (на не-Mac или PyObjC недоступен)")

        # Аудио + хоткеи
        sys_idx, mic_idx = self.worker.start_audio()
        print(f"✓ Audio: sys={sys_idx}, mic={mic_idx}")
        self.hotkeys.start()
        self.thread.start()

    def stop(self) -> None:
        self.hotkeys.stop()
        self.worker.stop_audio()
        self.thread.quit()
        self.thread.wait(2000)

    # ── Действия ────────────────────────────────────────────────────────
    def _on_ask(self) -> None:
        # Если открыто поле заметки — отправляем её
        if self.window.note_input.isVisible():
            self._on_send_note()
            return
        self.worker.request_answer()

    def _on_note_toggle(self) -> None:
        if self.window.note_input.isVisible():
            self.window.hide_note_input()
        else:
            self.window.show_note_input()
            self.window.raise_()
            self.window.activateWindow()

    def _on_send_note(self) -> None:
        text = self.window.hide_note_input()
        if text:
            self.worker.request_answer(user_note=text)

    def _on_clear(self) -> None:
        self.worker.clear_state()
        self.window.set_transcript("")
        self.window.set_answer("")
        self.window.set_status("listening", "Очищено · Слушаю")

    def _on_profile_changed(self, _idx: int) -> None:
        pid = self.window.current_profile_id()
        if pid and pid in self.profiles:
            self.worker.set_profile(self.profiles[pid], clear_history=True)
            self.window.set_status("listening", f"Профиль: {self.profiles[pid].name}")

    def _on_toggle_visibility(self) -> None:
        if self.window.isVisible():
            self.window.hide()
        else:
            self.window.show()
            self.window.raise_()

    def _on_error(self, msg: str) -> None:
        self.window.set_status("error", "Ошибка")
        self.window.show_error(msg)

    def _on_cost_updated(self, cost: core_billing.Cost) -> None:
        self.window.set_cost(cost.format_short())

    # ── Управление профилями ────────────────────────────────────────────
    def _on_new_profile(self) -> None:
        dlg = ProfileEditor(self.window, profile=None)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        data = dlg.get_form_data()
        new_id = core_profiles.make_id(data["name"], self.profiles)
        profile = Profile(
            id=new_id,
            name=data["name"],
            description=data["description"],
            icon=data["icon"],
            answer_length=data["answer_length"],
            system_prompt=data["system_prompt"],
        )
        core_profiles.save_profile(profile)
        self.profiles = core_profiles.load_profiles()
        self.window.refresh_profiles(self.profiles, select_id=new_id)

    def _on_edit_profile(self) -> None:
        pid = self.window.current_profile_id()
        if not pid or pid not in self.profiles:
            return
        current = self.profiles[pid]
        dlg = ProfileEditor(self.window, profile=current)
        result = dlg.exec()
        if result == QDialog.DialogCode.Accepted:
            data = dlg.get_form_data()
            updated = Profile(
                id=current.id,
                name=data["name"],
                description=data["description"],
                icon=data["icon"],
                answer_length=data["answer_length"],
                system_prompt=data["system_prompt"],
            )
            core_profiles.save_profile(updated)
            self.profiles = core_profiles.load_profiles()
            self.window.refresh_profiles(self.profiles, select_id=current.id)
            # Применяем новый промпт без очистки истории (это просто правка)
            self.worker.set_profile(self.profiles[current.id], clear_history=False)
        elif result == 2:  # удаление
            if core_profiles.delete_profile(current.id):
                self.profiles = core_profiles.load_profiles()
                default = core_profiles.get_default(self.profiles)
                self.window.refresh_profiles(self.profiles, select_id=default.id)
                self.worker.set_profile(default, clear_history=True)
