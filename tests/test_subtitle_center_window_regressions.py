# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Altyazı Merkezi PENCERE davranışı regresyonları.

Kullanıcının bildirdiği üç sorun:

1. Cinematic playback overlay'i Altyazı Merkezi'nin ÜSTÜNE çiziliyordu.
   Kök neden: `_player_owns_foreground()` yalnız SÜREÇ (PID) sahipliğini
   ölçüyor. Aynı süreçteki bir dialog öne geldiğinde ölçüm hâlâ "player
   önde" diyor, owner olayları overlay'i diriltiyor ve `raise_()` onu
   top-level Tool penceresi olarak dialogun üstüne taşıyordu.
2. Sağdan açılan ayar çekmecesi ana arama alanını birkaç karaktere
   sıkıştırıyordu.
3. Ayarlar API anahtarının ZORUNLU olduğunu anlatmıyordu; kullanıcı yalnız
   kullanıcı adı/parola girip arama yapmayı denedi.

Bu dosya offscreen ölçümlerle davranışı kilitler; gerçek Windows z-order
kanıtı `tests/subtitle_center_zorder_smoke_child.py` içindedir.
"""
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtWidgets import QApplication, QDialog, QMainWindow

from app.subtitle_center import (
    DEFAULT_SIZE, MINIMUM_SIZE, SubtitleCenterDialog)
from app.subtitle_center_composition import SubtitleCenterCoordinator
from app.subtitle_center_settings_dialog import SubtitleCenterSettingsDialog
from app.subtitle_settings import SubtitleSettingsStore

VIDEO = "Resident.Alien.S01E01.Pilot.1080p.AMZN.WEB-DL.mkv"
API_KEY = "APIKEYSUPERSECRET123"
LONG_TITLE = ("Bir Zamanlar Anadolu'da Cok Uzun Bir Film Adi "
              "Devam Eden Bolum Basligi 2026 Yeniden")


class FakeCredentialStore:
    def __init__(self, api_key=API_KEY):
        self.secrets = {"api": api_key} if api_key else {}

    def set_api_key(self, value):
        self.secrets["api"] = value
        return "credential_manager"

    def get_api_key(self):
        return self.secrets.get("api")

    def delete_api_key(self):
        self.secrets.pop("api", None)
        return True

    def set_password(self, username, value):
        self.secrets["pw"] = value
        return "credential_manager"

    def get_password(self, username):
        return self.secrets.get("pw")

    def delete_password(self, username):
        self.secrets.pop("pw", None)
        return True


class SpyVideoFrame:
    """Overlay bastırma sözleşmesini kaydeden sahte video yüzeyi."""

    def __init__(self):
        self.suppressed = None
        self.calls = []
        self.osd_messages = []

    def set_overlay_suppressed(self, suppressed):
        self.suppressed = bool(suppressed)
        self.calls.append(bool(suppressed))

    def show_osd(self, text, duration=1200):
        self.osd_messages.append(text)

    def _update_overlay_subtitle_state(self):
        pass


class StubPlayer(QMainWindow):
    def __init__(self, current_file):
        super().__init__()
        self.current_file = current_file
        self.video_frame = SpyVideoFrame()
        self.mpv_player = SimpleNamespace(
            track_list=[], sid="no", sub_visibility=False,
            sub_add=lambda p, *a: None, sub_remove=lambda s: None)


@pytest.fixture
def bench(tmp_path):
    app = QApplication.instance() or QApplication([])
    created = []

    def factory(api_key=API_KEY):
        path = tmp_path / VIDEO
        path.write_bytes(b"\0" * (140 * 1024))
        player = StubPlayer(str(path))
        store = SubtitleSettingsStore(
            settings=QSettings(str(tmp_path / "settings.ini"),
                               QSettings.Format.IniFormat),
            credentials=FakeCredentialStore(api_key))
        coordinator = SubtitleCenterCoordinator(
            player, client_factory=lambda **kwargs: SimpleNamespace(),
            settings_store=store)
        player._subtitle_center = coordinator
        created.append((player, coordinator))
        return SimpleNamespace(app=app, player=player, store=store,
                               coordinator=coordinator, tmp=tmp_path)

    yield factory

    for player, coordinator in created:
        coordinator.shutdown(wait_ms=3000)
        try:
            player.close()
            player.deleteLater()
        except RuntimeError:
            pass
    app.processEvents()


@pytest.fixture
def dialog_factory(tmp_path):
    app = QApplication.instance() or QApplication([])
    created = []

    def factory(size=None, media=None):
        window = QMainWindow()
        dialog = SubtitleCenterDialog(window, media=media or {
            "title": "Resident Alien", "season": 1, "episode": 1,
            "is_series": True, "file_name": str(tmp_path / VIDEO),
            "target_name": "x.srt"})
        dialog.resize(*(size or DEFAULT_SIZE))
        dialog.show()
        app.processEvents()
        created.append((window, dialog))
        return app, dialog

    yield factory

    for window, dialog in created:
        for widget in (dialog, window):
            try:
                widget.close()
                widget.deleteLater()
            except RuntimeError:
                pass
    app.processEvents()


# =====================================================================
# 1. Z-order: overlay Altyazı Merkezi'nin üstüne çıkmamalı
# =====================================================================

def test_opening_the_center_suppresses_the_playback_overlay(bench):
    env = bench()

    env.coordinator.open()

    assert env.player.video_frame.suppressed is True, (
        "Altyazi Merkezi acikken oynatma overlay'i bastirilmadi")


def test_closing_the_center_restores_the_playback_overlay(bench):
    env = bench()
    env.coordinator.open()

    env.coordinator.dialog.close()
    env.app.processEvents()

    assert env.player.video_frame.suppressed is False


def test_shutdown_restores_the_playback_overlay(bench):
    env = bench()
    env.coordinator.open()

    env.coordinator.shutdown(wait_ms=2000)

    assert env.player.video_frame.suppressed is False


def test_reopen_suppresses_again(bench):
    env = bench()
    env.coordinator.open()
    env.coordinator.dialog.close()
    env.app.processEvents()

    env.coordinator.open()

    assert env.player.video_frame.suppressed is True
    assert env.player.video_frame.calls[-3:] == [True, False, True]


def test_video_frame_exposes_the_suppression_contract():
    from app.video_frame import VideoFrame

    assert callable(getattr(VideoFrame, "set_overlay_suppressed", None))
    assert callable(getattr(VideoFrame, "overlay_suppressed", None))


def test_suppressed_overlay_is_never_raised_or_shown():
    """Bastırılmışken owner olayları overlay'i diriltmemeli."""
    import inspect

    from app.video_frame import VideoFrame

    for name in ("fade_overlay_in", "update_overlay_geometry",
                 "show_overlay_for_interaction",
                 "_restore_overlay_if_owner_visible",
                 "_restore_overlay_after_activation"):
        source = inspect.getsource(getattr(VideoFrame, name))
        assert "_overlay_suppressed" in source or "overlay_suppressed" in source, (
            f"{name} bastirma bayragini dikkate almiyor")


@pytest.mark.parametrize("factory_name", ["center", "settings"])
def test_no_window_uses_stays_on_top(bench, factory_name):
    env = bench()
    env.coordinator.open()
    dialog = env.coordinator.dialog
    if factory_name == "settings":
        dialog.settings_icon_button.click()
        env.app.processEvents()
        dialog = env.coordinator.settings_dialog

    assert dialog is not None
    assert not (dialog.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)


# =====================================================================
# 2. Ayarlar ARTIK ayrı pencere; arama alanını ezmiyor
# =====================================================================

def test_settings_open_in_a_separate_dialog(bench):
    env = bench()
    env.coordinator.open()

    env.coordinator.dialog.settings_icon_button.click()
    env.app.processEvents()

    settings = env.coordinator.settings_dialog
    assert isinstance(settings, SubtitleCenterSettingsDialog)
    assert settings.isVisible()
    assert settings.parent() is env.coordinator.dialog


def test_settings_dialog_is_a_single_instance(bench):
    env = bench()
    env.coordinator.open()
    dialog = env.coordinator.dialog

    dialog.settings_icon_button.click()
    env.app.processEvents()
    first = env.coordinator.settings_dialog
    dialog.settings_icon_button.click()
    env.app.processEvents()

    assert env.coordinator.settings_dialog is first
    open_dialogs = [w for w in env.app.topLevelWidgets()
                    if isinstance(w, SubtitleCenterSettingsDialog)]
    assert len(open_dialogs) == 1


def test_settings_dialog_can_be_closed_and_reopened(bench):
    env = bench()
    env.coordinator.open()
    dialog = env.coordinator.dialog
    dialog.settings_icon_button.click()
    env.app.processEvents()
    env.coordinator.settings_dialog.close()
    env.app.processEvents()

    dialog.settings_icon_button.click()
    env.app.processEvents()

    assert env.coordinator.settings_dialog is not None
    assert env.coordinator.settings_dialog.isVisible()


def test_settings_dialog_width_is_compact(bench):
    env = bench()
    env.coordinator.open()
    env.coordinator.dialog.settings_icon_button.click()
    env.app.processEvents()

    width = env.coordinator.settings_dialog.width()
    assert 400 <= width <= 480, width


def test_center_geometry_is_untouched_by_the_settings_dialog(bench):
    env = bench()
    env.coordinator.open()
    dialog = env.coordinator.dialog
    env.app.processEvents()
    before = (dialog.width(), dialog.height())
    title_before = dialog.title_field.width()

    dialog.settings_icon_button.click()
    env.app.processEvents()

    assert (dialog.width(), dialog.height()) == before
    assert dialog.title_field.width() == title_before, (
        "ayar penceresi arama alanini daraltti")


def test_the_old_inline_drawer_is_gone():
    import inspect

    from app import subtitle_center

    source = inspect.getsource(subtitle_center)
    assert "settings_drawer" not in source, (
        "kullanilmayan gizli cekmece widget'lari geride birakildi")


# =====================================================================
# 3. Arama alanı gerçekten kullanılabilir
# =====================================================================

def test_title_field_has_usable_width_at_default_size(dialog_factory):
    app, dialog = dialog_factory()

    assert dialog.width() == DEFAULT_SIZE[0]
    assert dialog.title_field.width() >= 240, (
        f"baslik alani cok dar: {dialog.title_field.width()}px")


def test_title_field_stays_usable_at_minimum_size(dialog_factory):
    app, dialog = dialog_factory(size=MINIMUM_SIZE)

    assert dialog.title_field.width() >= 200, dialog.title_field.width()


def test_search_controls_stay_inside_the_dialog(dialog_factory):
    for size in (DEFAULT_SIZE, MINIMUM_SIZE):
        app, dialog = dialog_factory(size=size)
        for widget in dialog.search_row_widgets():
            if not widget.isVisible():
                continue
            right = widget.mapTo(dialog, widget.rect().topRight()).x()
            assert right <= dialog.width(), (
                f"{widget.accessibleName()} dialog disina tasti ({size})")
        assert dialog.search_button.isVisible()


def test_long_title_is_kept_in_full(dialog_factory):
    app, dialog = dialog_factory()

    dialog.title_field.setText(LONG_TITLE)

    assert dialog.title_field.text() == LONG_TITLE
    assert dialog.title_field.toolTip() == LONG_TITLE


@pytest.mark.parametrize("scale_width", [660, 825, 990])
def test_no_overflow_at_common_dpi_scales(dialog_factory, scale_width):
    """100%, 125% ve 150% ölçekte taşma olmamalı."""
    app, dialog = dialog_factory(size=(scale_width, 440))

    assert dialog.title_field.width() >= 240
    assert dialog.search_button.isVisible()
    right = dialog.search_button.mapTo(
        dialog, dialog.search_button.rect().topRight()).x()
    assert right <= dialog.width()
