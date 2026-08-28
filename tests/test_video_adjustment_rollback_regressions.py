# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Video ayarı kontrolleri başarısız native yazımı doğru göstermez."""

from PyQt6.QtWidgets import QApplication, QDialog, QMainWindow, QSlider

from app.menu_actions import setup_video_adjustments


class RejectBrightness:
    brightness = 10
    contrast = 20
    saturation = 30
    gamma = 40

    def __setattr__(self, name, value):
        if name == "brightness":
            raise RuntimeError("brightness rejected")
        super().__setattr__(name, value)


def _open_dialog(monkeypatch, mpv):
    app = QApplication.instance() or QApplication([])
    captured = []
    monkeypatch.setattr(QDialog, "exec", lambda dialog: captured.append(dialog))
    player = QMainWindow()
    player.mpv_player = mpv
    setup_video_adjustments(player)
    assert len(captured) == 1
    sliders = captured[0].findChildren(QSlider)
    assert len(sliders) == 4
    return app, player, captured[0], sliders


def test_rejected_video_setting_restores_the_slider(monkeypatch):
    app, player, dialog, sliders = _open_dialog(
        monkeypatch, RejectBrightness())
    brightness = sliders[0]
    assert brightness.value() == 10

    brightness.setValue(65)
    app.processEvents()

    assert brightness.value() == 10
    dialog.deleteLater()
    player.deleteLater()


class RejectSecondReset:
    def __init__(self):
        self.brightness = 10
        self.contrast = 20
        self.saturation = 30
        self.gamma = 40

    def __setattr__(self, name, value):
        if name == "contrast" and hasattr(self, "contrast") and value == 0:
            raise RuntimeError("contrast reset rejected")
        super().__setattr__(name, value)


def test_reset_is_atomic_when_one_video_setting_is_rejected(monkeypatch):
    app, player, dialog, sliders = _open_dialog(
        monkeypatch, RejectSecondReset())
    reset = next(button for button in dialog.findChildren(
        __import__('PyQt6.QtWidgets', fromlist=['QPushButton']).QPushButton)
                 if button.text() == "Sıfırla")

    reset.click()
    app.processEvents()

    assert [player.mpv_player.brightness, player.mpv_player.contrast,
            player.mpv_player.saturation, player.mpv_player.gamma] == [
                10, 20, 30, 40]
    assert [slider.value() for slider in sliders] == [10, 20, 30, 40]
    dialog.deleteLater()
    player.deleteLater()


class SilentBrightness:
    brightness = 10
    contrast = 20
    saturation = 30
    gamma = 40

    def __setattr__(self, name, value):
        if name == "brightness" and hasattr(self, "brightness"):
            return
        super().__setattr__(name, value)


def test_silently_ignored_video_setting_restores_the_slider(monkeypatch):
    app, player, dialog, sliders = _open_dialog(
        monkeypatch, SilentBrightness())

    sliders[0].setValue(65)
    app.processEvents()

    assert player.mpv_player.brightness == 10
    assert sliders[0].value() == 10
    dialog.deleteLater()
    player.deleteLater()
