# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Modern güncelleme penceresinin görsel ve davranış sözleşmesi."""

import webbrowser

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton

from app import updater


@pytest.fixture
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def dialog(qt_app):
    return updater.UpdateDialog(
        "v0.38",
        "https://github.com/IzzmooPro/MLCPlayer/releases/download/"
        "v0.38/MLCPlayer_Setup_v0.38.exe",
        expected_sha256="a" * 64,
        expected_size=1024,
        signature_url="https://github.com/IzzmooPro/MLCPlayer/releases/"
                      "download/v0.38/MLCPlayer_Setup_v0.38.exe.sig")


def visible_text(dialog):
    labels = [item.text() for item in dialog.findChildren(QLabel)]
    buttons = [item.text() for item in dialog.findChildren(QPushButton)]
    return "\n".join(labels + buttons)


def test_dialog_matches_the_compact_split_design(dialog):
    assert (dialog.width(), dialog.height()) == updater.UPDATE_DIALOG_SIZE
    assert dialog.width() <= 540 and dialog.height() <= 330
    assert dialog.windowFlags() & Qt.WindowType.FramelessWindowHint

    brand = dialog.findChild(QLabel, "updateIcon").parentWidget()
    assert brand.objectName() == "updateBrandPanel"
    assert brand.width() == updater.UPDATE_BRAND_WIDTH
    assert dialog.findChild(QLabel, "updateHeading").text() == (
        "Yeni sürüm kullanıma hazır")
    assert dialog.findChild(QPushButton, "updatePrimary").text() == "Güncelle"
    assert dialog.findChild(QPushButton, "updateLater").text() == "Daha sonra"


def test_dialog_avoids_claims_that_are_not_true_for_every_release(dialog):
    text = visible_text(dialog)
    assert "Daha kararlı oynatma" not in text
    assert "Geliştirilmiş bağlantı desteği" not in text
    assert "Güvenlik iyileştirmeleri" not in text
    assert "Değişiklikleri sürüm notlarında inceleyebilirsiniz." in text
    assert "Sürüm notları →" in text


def test_release_notes_link_uses_the_exact_encoded_tag(qt_app, monkeypatch):
    opened = []
    monkeypatch.setattr(webbrowser, "open", opened.append)
    dialog = updater.UpdateDialog("v0.38/özel", "unused")

    dialog.open_release_notes()

    assert opened == [
        "https://github.com/IzzmooPro/MLCPlayer/releases/tag/"
        "v0.38%2F%C3%B6zel"]


def test_download_state_does_not_grow_the_window(qt_app, dialog):
    dialog.show()
    qt_app.processEvents()
    size = dialog.size()

    dialog._progress.setVisible(True)
    dialog._status.setVisible(True)
    dialog._status.setText("İndiriliyor…")
    qt_app.processEvents()

    assert dialog.size() == size
    assert dialog._progress.height() == 5


class FakeSignal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, *args):
        for callback in self._callbacks:
            callback(*args)


class FakeDownloader:

    created = None

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.started = False
        self.progress = FakeSignal()
        self.download_finished = FakeSignal()
        self.failed = FakeSignal()
        FakeDownloader.created = self

    def start(self):
        self.started = True


def test_real_update_action_enters_and_updates_download_state(
        qt_app, dialog, monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "UpdateDownloader", FakeDownloader)
    monkeypatch.setattr(updater.tempfile, "mkdtemp", lambda **_: str(tmp_path))

    dialog.start_update()
    worker = FakeDownloader.created

    assert worker is not None and worker.started
    assert not dialog._update_button.isEnabled()
    assert not dialog._later_button.isEnabled()
    assert not dialog._progress.isHidden()
    assert not dialog._status.isHidden()
    assert dialog._status.text() == "İndiriliyor…"

    worker.progress.emit(62)
    assert dialog._progress.value() == 62
    dialog._downloader = None
    FakeDownloader.created = None


def test_download_failure_returns_the_dialog_to_a_retryable_state(
        qt_app, dialog, monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "UpdateDownloader", FakeDownloader)
    monkeypatch.setattr(updater.tempfile, "mkdtemp", lambda **_: str(tmp_path))
    shown_errors = []
    monkeypatch.setattr(dialog, "show_error", shown_errors.append)

    dialog.start_update()
    FakeDownloader.created.failed.emit("İndirme başarısız")

    assert dialog._update_button.isEnabled()
    assert dialog._later_button.isEnabled()
    assert dialog._progress.isHidden()
    assert dialog._status.isHidden()
    assert shown_errors == ["İndirme başarısız"]
    dialog._downloader = None
    FakeDownloader.created = None
