# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QWidget

from app.empty_state import EMPTY_STATE_HINT, EMPTY_STATE_TITLE, EmptyStateOverlay
from app.config import UI_ACCENT
from app.modern_info_dialog import INFO_DIALOG_SIZE, ModernInfoDialog
from app.video_frame import VideoFrame


def test_empty_state_matches_the_approved_layout():
    app = QApplication.instance() or QApplication([])
    player = QMainWindow()
    player.calls = []
    player.open_file = lambda: player.calls.append("file")
    player.open_folder = lambda: player.calls.append("folder")
    frame = QWidget(player)
    frame.main_window = player
    surface = EmptyStateOverlay(frame)

    assert surface.title_label.text() == EMPTY_STATE_TITLE
    assert surface.hint_label.text() == EMPTY_STATE_HINT
    assert surface.open_file_button.text() == "Dosya Aç"
    assert surface.open_file_button.size().width() == 124
    assert surface.open_file_button.size().height() == 42
    assert surface.open_folder_button.text() == "Klasör Aç"
    assert surface.open_folder_button.size().width() == 124
    assert surface.open_folder_button.size().height() == 40
    assert f"background: {UI_ACCENT}" in surface.open_file_button.styleSheet()
    assert "background: #252B31" in surface.open_folder_button.styleSheet()
    for button in (surface.open_file_button, surface.open_folder_button):
        style = button.styleSheet()
        assert 'font-family: "Segoe UI Variable Text", "Segoe UI"' in style
        assert "font-size: 14px" in style
        assert "font-weight: 600" in style
    assert "border: 1px solid #414950" in \
        surface.open_folder_button.styleSheet()
    assert "#FF6A32" not in surface.open_folder_button.styleSheet()
    assert "QPushButton:focus { border-color: #707A84; }" in \
        surface.open_folder_button.styleSheet()
    assert surface.open_file_button.icon().isNull()
    assert surface.open_folder_button.icon().isNull()
    assert surface.parentWidget() is frame
    assert surface.isWindow() is False
    assert surface.testAttribute(Qt.WidgetAttribute.WA_NativeWindow)

    player.show()
    surface.show()
    app.processEvents()
    surface.open_file_button.click()
    assert surface.isVisible(), "Dosya Aç eski placeholder'ı açığa çıkardı"
    surface.open_folder_button.click()
    assert player.calls == ["file", "folder"]
    surface.close()
    player.close()
    app.processEvents()


def test_modern_info_dialog_matches_the_approved_compact_window():
    app = QApplication.instance() or QApplication([])
    parent = QMainWindow()
    dialog = ModernInfoDialog(parent, "Oynatma listesi",
                              "Listenin başındasınız.")

    assert INFO_DIALOG_SIZE == (300, 150)
    assert (dialog.width(), dialog.height()) == INFO_DIALOG_SIZE
    assert dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert dialog.title_label.text() == "Oynatma listesi"
    assert dialog.message_label.text() == "Listenin başındasınız."
    assert "font-size: 14px" in dialog.message_label.styleSheet()
    assert dialog.findChild(QLabel, "modernInfoIcon").text() == "ⓘ"

    dialog.close()
    parent.close()
    app.processEvents()


def test_empty_state_never_covers_an_already_selected_media():
    placeholder = SimpleNamespace(isHidden=lambda: False)
    frame = SimpleNamespace(
        placeholder_label=placeholder,
        main_window=SimpleNamespace(current_file="C:/video.mkv"))

    assert VideoFrame._empty_state_requested(frame) is False
    frame.main_window.current_file = ""
    assert VideoFrame._empty_state_requested(frame) is True
    frame.main_window.current_file = "https://example.test/video"
    frame.main_window._url_loading_active = True
    assert VideoFrame._empty_state_requested(frame) is True


def test_information_dialog_suppresses_owned_surfaces(monkeypatch):
    from app import modern_info_dialog

    calls = []
    frame = SimpleNamespace(
        overlay_suppressed=lambda: False,
        set_overlay_suppressed=lambda value: calls.append(value))
    parent = SimpleNamespace(video_frame=frame)

    class FakeDialog:
        def __init__(self, *args):
            calls.append(args[1:])

        def exec(self):
            calls.append("exec")
            return 1

    monkeypatch.setattr(modern_info_dialog, "ModernInfoDialog", FakeDialog)

    assert modern_info_dialog.show_information(parent, "Başlık", "Mesaj") == 1
    assert calls == [True, ("Başlık", "Mesaj"), "exec", False]
