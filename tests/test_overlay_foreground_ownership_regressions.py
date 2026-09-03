# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Yüzen yüzeylerin gerçek foreground sahipliğine bağlanması.

Kullanıcının 1. ekran görüntüsü: Explorer öne geldiğinde alt kontrol/timeline
yüzeyi görünür kalıyor. Native composition smoke'ta aynı hata, foreground
başka bir sürece geçtiği hâlde overlay'in görünür kalmasıyla ölçüldü.

Kök neden: karar `QApplication.activeWindow()`a bakıyordu. Bu değer bir Tool
yüzeyi döndürebiliyor veya Qt aktivasyon isteği Windows tarafından
reddedildiğinde gerçekle çelişebiliyor. Karar, sürecin gerçek foreground
sahipliğine bağlanmalıdır.

Not: offscreen platformda gerçek foreground kavramı yoktur; bu yüzden ürün
ölçümü orada devre dışıdır ve testler kararı doğrudan yamalayarak ölçer.
"""
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QEvent, QPoint, QRect, QSettings, Qt
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QMainWindow, QSlider, QVBoxLayout,
    QWidget)

from app.config import MAX_VOLUME
import app.video_frame as video_frame_module
from app.video_frame import VideoFrame


class _SetWindowPosRecorder:
    def __init__(self, result=1):
        self.result = result
        self.calls = []

    def SetWindowPos(self, *args):
        self.calls.append(args)
        return self.result


class _NativeOverlaySurface:
    def __init__(self):
        self.qt_raise_calls = 0

    def winId(self):
        return 1234

    def raise_(self):
        self.qt_raise_calls += 1


def test_native_overlay_zorder_update_never_requests_qt_activation(monkeypatch):
    """Windows z-order guncellemesi NOACTIVATE ile yapilmali.

    ``QWidget.raise_()`` odak kabul etmeyen top-level Tool yuzeyinde Qt'nin
    ``requestActivate()`` uyarisini ve gereksiz aktivasyon istegini uretiyor.
    """
    user32 = _SetWindowPosRecorder()
    surface = _NativeOverlaySurface()
    monkeypatch.setattr(video_frame_module, "_user32", user32)
    monkeypatch.setattr(video_frame_module,
                        "_native_overlay_zorder_supported", lambda: True)

    assert video_frame_module._raise_overlay_without_activation(surface)
    assert surface.qt_raise_calls == 0
    assert len(user32.calls) == 1
    flags = user32.calls[0][-1]
    assert flags & 0x0010, "SetWindowPos SWP_NOACTIVATE icermiyor"


def test_failed_native_overlay_zorder_does_not_fall_back_to_qt_raise(
        monkeypatch):
    """Gercek Windows'ta hata, ayni aktivasyon kusuruna geri dusmemeli."""
    user32 = _SetWindowPosRecorder(result=0)
    surface = _NativeOverlaySurface()
    monkeypatch.setattr(video_frame_module, "_user32", user32)
    monkeypatch.setattr(video_frame_module,
                        "_native_overlay_zorder_supported", lambda: True)

    assert not video_frame_module._raise_overlay_without_activation(surface)
    assert surface.qt_raise_calls == 0


def test_offscreen_overlay_zorder_keeps_qt_layout_fallback(monkeypatch):
    surface = _NativeOverlaySurface()
    monkeypatch.setattr(video_frame_module,
                        "_native_overlay_zorder_supported", lambda: False)

    assert video_frame_module._raise_overlay_without_activation(surface)
    assert surface.qt_raise_calls == 1


@pytest.fixture
def player_window(monkeypatch, tmp_path):
    monkeypatch.delenv("MLCPLAYER_CLASSIC_UI", raising=False)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      str(tmp_path))
    app = QApplication.instance() or QApplication([])
    created = []

    def factory(size=(1280, 720)):
        window = QMainWindow()
        window.cinematic_ui_enabled = True
        window.playlist = [r"C:\media\first.mkv"]
        window.current_playlist_index = 0
        window.current_file = window.playlist[0]
        window.duration = 600.0
        window.position = 0.0
        window.is_paused = False
        window.is_muted = False
        window._updating_position_slider = False
        window.volume_slider = QSlider(Qt.Orientation.Horizontal)
        window.volume_slider.setRange(0, MAX_VOLUME)
        window.volume_slider.setValue(70)
        window.position_slider = QSlider()
        window.position_slider.setRange(0, 1000)
        window.current_time_label = QLabel()
        window.total_time_label = QLabel()
        window.play_button = SimpleNamespace(setIcon=lambda icon: None)
        window.play_icon = object()
        window.pause_icon = object()
        window.update_time_label = lambda: None
        window.mpv_player = SimpleNamespace(time_pos=0.0, pause=False,
                                            track_list=[], sub_visibility=False,
                                            sid="no", stop=lambda: None)
        for name in ("play_previous", "play_next", "play_pause", "toggle_mute",
                     "toggle_subtitles", "toggle_fullscreen",
                     "setup_video_adjustments", "add_to_playlist",
                     "remove_from_playlist", "clear_playlist"):
            setattr(window, name, lambda *a: None)
        window.play_from_playlist = lambda index: None

        central = QWidget(window)
        window.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        window.media_container = QWidget(central)
        media_layout = QHBoxLayout(window.media_container)
        media_layout.setContentsMargins(0, 0, 0, 0)
        media_layout.setSpacing(0)
        window.playlist_dock_host = QWidget(window.media_container)
        window.playlist_dock_host.setFixedWidth(0)
        window.playlist_dock_host.hide()
        frame = VideoFrame(window)
        frame.setMinimumSize(200, 120)
        window.video_frame = frame
        media_layout.addWidget(frame, 1)
        media_layout.addWidget(window.playlist_dock_host, 0)
        root.addWidget(window.media_container, 1)
        window.resize(*size)
        window.show()
        app.processEvents()
        frame.update_overlay_geometry()
        frame.show_overlay_for_interaction()
        finish_fade(app, frame)
        app.processEvents()
        created.append((window, frame))
        return app, window, frame

    yield factory

    # NOT: Testler aktif pencereyi bilerek control_overlay gibi Tool
    # yüzeylerine taşıyor. Aktif pencere işaretçisi yok edilecek bir yüzeyi
    # gösterirken süreç kapanışında native abort (0xC0000409) oluşuyordu.
    QApplication.setActiveWindow(None)
    app.processEvents()
    for window, frame in created:
        if frame.is_video_fullscreen:
            frame.exit_fullscreen()
        # NOT: Çalışır durumda bırakılan fade/panel animasyonu, hedef widget
        # yok edildikten sonra yorumlayıcı kapanışında native abort
        # (0xC0000409) üretiyordu. Önce animasyonlar durdurulur.
        fade = getattr(frame, "overlay_fade", None)
        if fade is not None:
            fade.stop()
        panel = getattr(frame, "playlist_panel", None)
        if panel is not None:
            panel.animation.stop()
        frame.close_control_overlay()
        window.close()
        app.processEvents()
        window.deleteLater()
    app.processEvents()


def finish_fade(app, frame):
    animation = getattr(frame, "overlay_fade", None)
    if animation is not None and animation.state().name == "Running":
        animation.setCurrentTime(animation.duration())
    app.processEvents()


def set_foreground_owner(monkeypatch, frame, owned):
    """Gerçek foreground sahipliğini deterministik olarak yamalar."""
    monkeypatch.setattr(type(frame), "_player_owns_foreground",
                        lambda self: owned)


# --- 1. Ürün gerçek foreground sahipliğini ölçebilmeli ---

def test_video_frame_exposes_a_real_foreground_ownership_check(player_window):
    app, window, frame = player_window()

    assert hasattr(frame, "_player_owns_foreground"), (
        "gerçek foreground sahipliği ölçümü yok; karar activeWindow'a bağlı")
    assert isinstance(frame._player_owns_foreground(), bool)


def test_active_decision_is_false_when_foreground_is_external(
        player_window, monkeypatch):
    app, window, frame = player_window()
    QApplication.setActiveWindow(window)
    app.processEvents()
    assert frame._is_player_surface_active()

    set_foreground_owner(monkeypatch, frame, False)

    assert not frame._is_player_surface_active(), (
        "foreground dış süreçteyken oynatıcı yüzeyi aktif sayılıyor")


def test_a_tool_surface_alone_does_not_prove_the_player_is_active(
        player_window, monkeypatch):
    """activeWindow bir Tool yüzeyi döndürse bile gerçek foreground belirler."""
    app, window, frame = player_window()
    QApplication.setActiveWindow(frame.control_overlay)
    app.processEvents()

    set_foreground_owner(monkeypatch, frame, False)

    assert not frame._is_player_surface_active()


# --- 2. Dış uygulama öndeyken overlay ve OSD gizlenmeli ---

def test_deactivation_hides_the_control_overlay_when_foreground_is_external(
        player_window, monkeypatch):
    app, window, frame = player_window()
    assert frame.control_overlay.isVisible()

    set_foreground_owner(monkeypatch, frame, False)
    frame._hide_owned_surfaces_if_inactive()
    app.processEvents()

    assert not frame.control_overlay.isVisible(), (
        "dış uygulama öndeyken kontrol katmanı görünür kaldı")


def test_osd_does_not_appear_while_another_process_is_foreground(
        player_window, monkeypatch):
    app, window, frame = player_window()
    set_foreground_owner(monkeypatch, frame, False)

    frame.show_osd("Ses: %50")
    app.processEvents()

    assert not frame.osd_label.isVisible(), (
        "OSD başka uygulamanın üstünde göründü")


def test_osd_still_appears_normally_when_the_player_owns_foreground(
        player_window, monkeypatch):
    app, window, frame = player_window()
    set_foreground_owner(monkeypatch, frame, True)

    frame.show_osd("Ses: %50")
    app.processEvents()

    assert frame.osd_label.isVisible()
    assert frame.osd_label.text() == "Ses: %50"


# --- 3. Qt aktivasyonu gerçeği ezmemeli (bayat geometri dirilmesi) ---

def test_activation_event_does_not_resurrect_overlay_without_real_foreground(
        player_window, monkeypatch):
    """Qt WindowActivate gelse bile foreground dışarıdaysa overlay dönmemeli.

    Native smoke'ta tam olarak bu görülmüştü: aktivasyon isteği Windows
    tarafından karşılanmadığı hâlde overlay geri geliyordu.
    """
    app, window, frame = player_window()
    set_foreground_owner(monkeypatch, frame, False)
    frame.hide_overlay_immediately()
    app.processEvents()

    frame._restore_overlay_after_activation()
    finish_fade(app, frame)

    assert not frame.control_overlay.isVisible(), (
        "gerçek foreground olmadan overlay dirildi")


def test_owner_show_event_does_not_resurrect_overlay_when_inactive(
        player_window, monkeypatch):
    app, window, frame = player_window()
    set_foreground_owner(monkeypatch, frame, False)
    frame.hide_overlay_immediately()
    app.processEvents()

    frame._restore_overlay_if_owner_visible()
    finish_fade(app, frame)

    assert not frame.control_overlay.isVisible()


def test_overlay_returns_after_real_foreground_is_regained(
        player_window, monkeypatch):
    app, window, frame = player_window()
    set_foreground_owner(monkeypatch, frame, False)
    frame._hide_owned_surfaces_if_inactive()
    app.processEvents()
    assert not frame.control_overlay.isVisible()

    set_foreground_owner(monkeypatch, frame, True)
    QApplication.setActiveWindow(window)
    frame._restore_overlay_after_activation()
    finish_fade(app, frame)

    assert frame.control_overlay.isVisible(), (
        "gerçek foreground geri geldiğinde kontroller dönmedi")


# --- 4. Yasaklı geçici çözümler kullanılmamalı ---

def test_no_global_always_on_top_flags_remain(player_window):
    app, window, frame = player_window()

    for surface in (frame.control_overlay, frame.osd_label):
        assert not (surface.windowFlags()
                    & Qt.WindowType.WindowStaysOnTopHint), (
            "global WindowStaysOnTopHint geçici makyajdır")


def test_no_periodic_foreground_polling_timer_is_created(player_window):
    """Foreground kararı için periyodik timer eklenmemeli."""
    app, window, frame = player_window()

    from PyQt6.QtCore import QTimer
    repeating = [timer for timer in frame.findChildren(QTimer)
                 if not timer.isSingleShot() and timer.isActive()]
    names = {timer.objectName() for timer in repeating}
    assert not any("foreground" in name.lower() for name in names), (
        f"foreground polling timer bulundu: {names}")


# --- 4b. Windows ölçümü BAŞARISIZ olduğunda güvenli tarafa düşmeli ---
#
# Yüzen overlay/OSD görünürlük koruması için "ölçemedim -> göster" yanlış
# yöndür: başarısız bir ölçüm, orijinal hatayı (başka uygulamanın üstünde
# asılı kalan kontrol katmanı) geri getirebilir.

class FakeUser32:
    """Win32 çağrılarını deterministik biçimde taklit eder.

    NOT: Hazır bir istisna NESNESİ saklanmaz, yalnızca mesaj saklanır ve her
    çağrıda tazesi üretilir. Raise edilmiş uzun ömürlü bir istisna, kendi
    `__traceback__`'i üzerinden test karelerini -- dolayısıyla Qt
    widget'larını -- canlı tutuyor; bu nesneler QApplication yok edildikten
    sonra yıkıldığı için süreç kapanışında native abort (0xC0000409)
    oluşuyordu.
    """

    def __init__(self, hwnd=0, pid=0, thread=1, error_message=None):
        self._hwnd = hwnd
        self._pid = pid
        self._thread = thread
        self._error_message = error_message

    def _maybe_raise(self):
        if self._error_message is not None:
            raise OSError(self._error_message)

    def GetForegroundWindow(self):
        self._maybe_raise()
        return self._hwnd

    def GetWindowThreadProcessId(self, hwnd, pid_ref):
        self._maybe_raise()
        pid_ref._obj.value = self._pid
        return self._thread


@pytest.fixture
def forced_native_measurement(monkeypatch):
    """Offscreen kısayolunu kapatıp gerçek ölçüm yolunu zorlar."""
    from app import video_frame as video_frame_module

    monkeypatch.setattr(
        video_frame_module, "_foreground_measurement_supported", lambda: True)
    return video_frame_module


def test_zero_hwnd_means_the_player_does_not_own_foreground(
        player_window, forced_native_measurement, monkeypatch):
    app, window, frame = player_window()
    monkeypatch.setattr(forced_native_measurement, "_user32",
                        FakeUser32(hwnd=0, pid=os.getpid()))

    assert frame._player_owns_foreground() is False


def test_zero_pid_means_the_player_does_not_own_foreground(
        player_window, forced_native_measurement, monkeypatch):
    app, window, frame = player_window()
    monkeypatch.setattr(forced_native_measurement, "_user32",
                        FakeUser32(hwnd=1234, pid=0))

    assert frame._player_owns_foreground() is False


def test_win32_api_error_means_the_player_does_not_own_foreground(
        player_window, forced_native_measurement, monkeypatch):
    app, window, frame = player_window()
    monkeypatch.setattr(forced_native_measurement, "_user32",
                        FakeUser32(error_message="GetForegroundWindow failed"))

    assert frame._player_owns_foreground() is False


def test_zero_thread_id_means_the_player_does_not_own_foreground(
        player_window, forced_native_measurement, monkeypatch):
    app, window, frame = player_window()
    monkeypatch.setattr(forced_native_measurement, "_user32",
                        FakeUser32(hwnd=1234, pid=os.getpid(), thread=0))

    assert frame._player_owns_foreground() is False


def test_matching_pid_still_means_the_player_owns_foreground(
        player_window, forced_native_measurement, monkeypatch):
    app, window, frame = player_window()
    monkeypatch.setattr(forced_native_measurement, "_user32",
                        FakeUser32(hwnd=1234, pid=os.getpid()))

    assert frame._player_owns_foreground() is True


# NOT: FakeUser32 örnekleri parametrize içinde OLUŞTURULMAZ; orada üretilen
# nesneler modül import anında doğar ve bütün oturum boyunca yaşar. Test
# başına taze nesne üretmek için yalnızca kurucu argümanları geçirilir.
@pytest.mark.parametrize("kwargs, label", (
    ({"hwnd": 0, "pid": 1}, "sıfır HWND"),
    ({"hwnd": 9, "pid": 0}, "sıfır PID"),
    ({"error_message": "boom"}, "API hatası"),
))
def test_overlay_and_osd_stay_hidden_when_measurement_fails(
        player_window, forced_native_measurement, monkeypatch, kwargs, label):
    app, window, frame = player_window()
    monkeypatch.setattr(forced_native_measurement, "_user32",
                        FakeUser32(**kwargs))

    frame._hide_owned_surfaces_if_inactive()
    frame.show_osd("Ses: %50")
    frame._restore_overlay_after_activation()
    finish_fade(app, frame)

    assert not frame.control_overlay.isVisible(), (
        f"{label} durumunda kontrol katmanı görünür kaldı")
    assert not frame.osd_label.isVisible(), (
        f"{label} durumunda OSD görünür kaldı")


def test_win32_signatures_are_pointer_safe(forced_native_measurement):
    """64-bit HWND'nin int'e kırpılmaması için imzalar tanımlı olmalı."""
    from ctypes import wintypes

    from app import video_frame as module

    user32 = module._REAL_USER32
    assert user32 is not None
    assert user32.GetForegroundWindow.restype is wintypes.HWND
    assert user32.GetWindowThreadProcessId.restype is wintypes.DWORD
    assert user32.GetWindowThreadProcessId.argtypes[0] is wintypes.HWND


# --- 5. Mevcut davranışlar korunmalı ---

def test_auto_hide_and_interaction_rules_survive(player_window, monkeypatch):
    app, window, frame = player_window()
    set_foreground_owner(monkeypatch, frame, True)

    frame.hide_overlay_immediately()
    app.processEvents()
    frame.show_overlay_for_interaction()
    finish_fade(app, frame)

    assert frame.control_overlay.isVisible()
    assert frame.overlay_hide_timer.isActive()
