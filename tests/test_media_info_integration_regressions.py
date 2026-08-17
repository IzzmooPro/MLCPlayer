# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Medya Bilgisi baglantisi: menu + sag-tik + player yasam dongusu (3. tur).

Builder (`app/media_info.py`) ve pencere (`app/media_info_dialog.py`) burada
YENIDEN test EDILMEZ; yalniz import edilip kullanilir.

Kilitlenen sozlesmeler
----------------------
- Tek merkezi acma noktasi `menu_actions.show_media_info(player)`; menu,
  sag-tik ve player facade AYNI yolu kullanir.
- Modeless tekil pencere: ikinci cagri YENI pencere uretmez.
- `destroyed` geri cagrisi yalniz HALA ayni dialog referansiysa temizler.
- Tazeleme yalniz anahtar degistiginde `set_snapshot()` cagirir.
- Dialog KAPALIYKEN hicbir mpv property okunmaz.
- Kapanis sirasi: dialog kapat -> mpv `stop()` -> `terminate()`.
- Yeni timer, thread, `exec()` veya `observe_property` YOK.
"""
import os
import re
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtWidgets import (QApplication, QLabel, QMainWindow, QMenu, QSlider,
                             QVBoxLayout, QWidget)

import app.menu_actions as menu_actions
from app.media_info_dialog import MediaInfoDialog

MEDIA_INFO_TEXT = "Medya Bilgisi"

TRACKS = [
    {"id": 1, "type": "video", "selected": True, "codec": "h264",
     "demux-w": 1920, "demux-h": 1080, "demux-fps": 24.0},
    {"id": 1, "type": "audio", "selected": True, "lang": "tur",
     "codec": "eac3", "demux-channels": "5.1(side)"},
    {"id": 2, "type": "audio", "selected": False, "lang": "eng",
     "codec": "aac", "demux-channels": "stereo"},
]

PLAYER_METHODS = (
    "add_to_playlist", "close", "goto_time", "load_playlist", "open_file",
    "open_folder", "open_subtitle", "open_subtitle_center", "open_url",
    "play_next", "play_pause", "play_previous", "refresh_chapters",
    "save_playlist", "set_loop_file", "set_loop_playlist",
    "setup_video_adjustments", "show_about", "show_log_management",
    "show_media_info", "show_playlist", "show_shortcuts",
    "show_subtitle_settings", "stop", "take_screenshot", "toggle_fullscreen",
    "toggle_mute", "toggle_shuffle", "toggle_subtitles",
    "open_path", "seek_relative", "select_audio_track", "select_audio_device",
    "select_subtitle_language", "seek_position", "set_playback_speed",
)


class Recorder:
    def __init__(self):
        self.calls = []

    def method(self, name):
        def call(*args, **kwargs):
            self.calls.append((name, args, kwargs))
        return call

    def names(self):
        return [name for name, _a, _k in self.calls]


class StubMpv:
    """Yalniz okunan yuzeyi taklit eder ve property okumalarini SAYAR."""

    def __init__(self, tracks=None, values=None, raise_property=False):
        self.track_list = list(tracks or [])
        self.aid = 1
        self.sid = 1
        self.audio_device = "auto"
        self.sub_visibility = False
        self.speed = 1.0
        self.audio_device_list = []
        self.property_reads = []
        self._values = dict(values or {})
        self._raise = raise_property
        self.stopped = []

    def _get_property(self, name):
        self.property_reads.append(name)
        if self._raise:
            raise RuntimeError("property okunamadi")
        return self._values.get(name)

    def command(self, *args, **kwargs):
        return None

    def stop(self):
        self.stopped.append("stop")

    def terminate(self):
        self.stopped.append("terminate")


@pytest.fixture
def qt_app(tmp_path):
    app = QApplication.instance() or QApplication([])
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      str(tmp_path))
    return app


@pytest.fixture
def player_factory(qt_app, tmp_path):
    """Gercek `setup_menu()` ve gercek `VideoFrame` ile calisan iskele."""
    created = []

    def factory(current_file="", tracks=None, values=None,
                raise_property=False, with_menu=True, with_frame=False):
        recorder = Recorder()
        window = QMainWindow()
        window.central_widget = QWidget(window)
        window.setCentralWidget(window.central_widget)
        window.main_layout = QVBoxLayout(window.central_widget)
        window.current_file = current_file
        window.duration = 120.0 if current_file else 0.0
        window.position = 0.0
        window.is_paused = False
        window.is_muted = False
        window.playlist = []
        window.current_playlist_index = 0
        window.loop_file = False
        window.loop_playlist = False
        window.shuffle = False
        window.recent_files = []
        window.last_dir = ""
        window._updating_position_slider = False
        window._pending_subs = []
        window._media_info_dialog = None
        window._media_info_refresh_key = None
        window.volume_slider = QSlider(Qt.Orientation.Horizontal)
        window.position_slider = QSlider()
        window.current_time_label = QLabel()
        window.total_time_label = QLabel()
        window.play_button = SimpleNamespace(setIcon=lambda icon: None)
        window.play_icon = object()
        window.pause_icon = object()
        window.update_time_label = lambda: None
        window.settings = QSettings()
        window.mpv_player = StubMpv(
            TRACKS if tracks is None else tracks, values, raise_property)
        for name in PLAYER_METHODS:
            setattr(window, name, recorder.method(name))
        if with_frame:
            from app.video_frame import VideoFrame

            window.video_frame = VideoFrame(window)
        if with_menu:
            menu_actions.setup_menu(window)
        created.append(window)
        qt_app.processEvents()
        return SimpleNamespace(window=window, recorder=recorder, app=qt_app)

    yield factory

    for window in created:
        try:
            menu_actions.close_media_info(window)
        except Exception:
            pass
        window.close()
        window.deleteLater()
    qt_app.processEvents()


def rows(menu):
    result = []
    for action in menu.actions():
        result.append("---" if action.isSeparator() else action.text())
    return result


def media_menu(window):
    for action in window.menuBar().actions():
        if action.text() == "Ortam":
            return action.menu()
    raise AssertionError("`Ortam` menüsü yok")


def all_texts(menu, seen=None):
    """Menu agacindaki BUTUN eylem metinleri (alt menuler dahil)."""
    seen = seen if seen is not None else set()
    if id(menu) in seen:
        return []
    seen.add(id(menu))
    found = []
    for action in menu.actions():
        if action.isSeparator():
            continue
        found.append(action.text())
        submenu = action.menu()
        if submenu is not None:
            found.extend(all_texts(submenu, seen))
    return found


# =====================================================================
# 1-2. Menu yerlesimi ve uc nokta MIRASI
# =====================================================================

def test_the_media_menu_places_the_action_before_exit(player_factory):
    window = player_factory().window
    lines = rows(media_menu(window))

    assert MEDIA_INFO_TEXT in lines, f"eylem yok: {lines}"
    recent = lines.index("Son Açılanlar")
    info = lines.index(MEDIA_INFO_TEXT)
    exit_row = lines.index("Çıkış")
    assert recent < info < exit_row, f"sıra yanlış: {lines}"
    assert lines[info - 1] == "---", f"ayraç yok: {lines}"


def test_the_action_starts_disabled_without_media(player_factory):
    window = player_factory(current_file="").window

    assert window.media_info_action.isEnabled() is False


def test_the_action_is_enabled_when_media_exists(player_factory):
    window = player_factory(current_file="C:/x/Film.mkv").window

    assert window.media_info_action.isEnabled() is True


def test_the_overflow_menu_inherits_exactly_one_action(player_factory):
    from app.title_bar import TitleBar

    window = player_factory(current_file="C:/x/Film.mkv").window
    title_bar = TitleBar(window)

    texts = all_texts(title_bar.build_overflow_menu())

    assert texts.count(MEDIA_INFO_TEXT) == 1, f"kopya eylem: {texts}"


def test_the_menu_action_calls_the_shared_player_facade(player_factory):
    built = player_factory(current_file="C:/x/Film.mkv")

    built.window.media_info_action.trigger()

    assert built.recorder.names() == ["show_media_info"]


# =====================================================================
# 3-4. Sag-tik
# =====================================================================

def test_the_context_menu_has_a_single_row_before_the_exit_separator(
        player_factory):
    built = player_factory(current_file="C:/x/Film.mkv", with_frame=True)
    lines = rows(built.window.video_frame.build_context_menu())

    assert lines.count(MEDIA_INFO_TEXT) == 1, f"satır sayısı: {lines}"
    info = lines.index(MEDIA_INFO_TEXT)
    assert lines.index("Oynatma") < info
    assert lines[info + 1] == "---"
    assert lines[info + 2] == "Uygulamadan Çık"


def test_the_context_row_follows_the_media_state(player_factory):
    with_media = player_factory(current_file="C:/x/Film.mkv", with_frame=True)
    without = player_factory(current_file="", with_frame=True)

    def action_of(built):
        menu = built.window.video_frame.build_context_menu()
        for action in menu.actions():
            if action.text() == MEDIA_INFO_TEXT:
                return action
        raise AssertionError("satır yok")

    assert action_of(with_media).isEnabled() is True
    assert action_of(without).isEnabled() is False


def test_both_menu_paths_reach_the_same_facade(player_factory):
    built = player_factory(current_file="C:/x/Film.mkv", with_frame=True)

    built.window.media_info_action.trigger()
    for action in built.window.video_frame.build_context_menu().actions():
        if action.text() == MEDIA_INFO_TEXT:
            action.trigger()

    assert built.recorder.names() == ["show_media_info", "show_media_info"]


# =====================================================================
# 5-8. Modeless singleton
# =====================================================================

def test_the_first_call_opens_one_modeless_dialog(player_factory):
    window = player_factory(current_file="C:/x/Film.mkv",
                            with_menu=False).window

    dialog = menu_actions.show_media_info(window)

    assert isinstance(dialog, MediaInfoDialog)
    assert dialog.isModal() is False
    assert dialog.isVisible() is True
    assert dialog.parent() is window
    assert window._media_info_dialog is dialog


def test_a_second_call_reuses_the_same_window(player_factory):
    window = player_factory(current_file="C:/x/Film.mkv",
                            with_menu=False).window

    first = menu_actions.show_media_info(window)
    second = menu_actions.show_media_info(window)

    assert first is second


def test_no_dialog_is_created_without_media(player_factory):
    window = player_factory(current_file="", with_menu=False).window

    assert menu_actions.show_media_info(window) is None
    assert window._media_info_dialog is None


def test_closing_the_dialog_clears_the_player_reference(qt_app,
                                                        player_factory):
    window = player_factory(current_file="C:/x/Film.mkv",
                            with_menu=False).window
    dialog = menu_actions.show_media_info(window)

    dialog.close()
    qt_app.processEvents()

    assert window._media_info_dialog is None
    assert window._media_info_refresh_key is None


def test_a_late_destroyed_signal_never_clears_a_newer_dialog(qt_app,
                                                             player_factory):
    """Eski pencerenin GEC gelen `destroyed` sinyali yeniyi silmemeli."""
    window = player_factory(current_file="C:/x/Film.mkv",
                            with_menu=False).window
    first = menu_actions.show_media_info(window)
    first.close()                      # referans temizlenir
    second = menu_actions.show_media_info(window)
    assert second is not first

    qt_app.processEvents()             # eski `destroyed` simdi islenir

    assert window._media_info_dialog is second


def test_a_deleted_wrapper_is_detected_without_a_raw_error(qt_app,
                                                           player_factory):
    from PyQt6 import sip

    window = player_factory(current_file="C:/x/Film.mkv",
                            with_menu=False).window
    dialog = menu_actions.show_media_info(window)
    sip.delete(dialog)                 # C++ nesnesi yok, Python sarmalayici var

    fresh = menu_actions.show_media_info(window)

    assert isinstance(fresh, MediaInfoDialog)
    assert fresh is not dialog


# =====================================================================
# 9-12. Tazeleme
# =====================================================================

def test_an_unchanged_key_never_calls_set_snapshot(qt_app, player_factory,
                                                   monkeypatch):
    window = player_factory(current_file="C:/x/Film.mkv",
                            with_menu=False).window
    dialog = menu_actions.show_media_info(window)
    calls = []
    monkeypatch.setattr(dialog, "set_snapshot",
                        lambda snapshot: calls.append(snapshot))

    menu_actions.refresh_media_info(window)
    menu_actions.refresh_media_info(window)

    assert calls == [], "anahtar degismeden snapshot uretildi"


def test_a_selection_change_refreshes_the_same_dialog(qt_app, player_factory,
                                                      monkeypatch):
    window = player_factory(current_file="C:/x/Film.mkv",
                            with_menu=False).window
    dialog = menu_actions.show_media_info(window)
    calls = []
    monkeypatch.setattr(dialog, "set_snapshot",
                        lambda snapshot: calls.append(snapshot))

    swapped = [dict(track) for track in TRACKS]
    swapped[1]["selected"] = False
    swapped[2]["selected"] = True
    window.mpv_player.track_list = swapped
    menu_actions.refresh_media_info(window)

    assert len(calls) == 1
    assert window._media_info_dialog is dialog


def test_late_metadata_refreshes_the_same_dialog(qt_app, player_factory,
                                                 monkeypatch):
    window = player_factory(current_file="C:/x/Film.mkv",
                            with_menu=False).window
    dialog = menu_actions.show_media_info(window)
    calls = []
    monkeypatch.setattr(dialog, "set_snapshot",
                        lambda snapshot: calls.append(snapshot))

    window.mpv_player._values = {"file-format": "matroska",
                                 "metadata": {"title": "Bolum Bir"}}
    menu_actions.refresh_media_info(window)

    assert len(calls) == 1


def test_a_media_change_moves_the_title_and_the_copy_target(qt_app,
                                                            player_factory):
    window = player_factory(current_file="C:/x/Eski.mkv",
                            with_menu=False).window
    dialog = menu_actions.show_media_info(window)
    assert dialog.windowTitle().endswith("Eski.mkv")

    window.current_file = "C:/x/Yeni.mkv"
    menu_actions.refresh_media_info(window)

    assert window._media_info_dialog is dialog
    assert dialog.windowTitle() == "Medya Bilgisi — Yeni.mkv"
    copied = []
    dialog._copy_text = copied.append
    dialog.copy_button.click()
    assert copied == ["C:/x/Yeni.mkv"]


def test_a_lost_snapshot_never_keeps_showing_the_old_media(qt_app,
                                                           player_factory):
    window = player_factory(current_file="C:/x/Film.mkv",
                            with_menu=False).window
    dialog = menu_actions.show_media_info(window)

    window.current_file = ""
    menu_actions.refresh_media_info(window)
    qt_app.processEvents()

    assert window._media_info_dialog is None


def test_a_closed_dialog_reads_no_mpv_property(player_factory):
    built = player_factory(current_file="C:/x/Film.mkv", with_menu=False)

    menu_actions.refresh_media_info(built.window)

    assert built.window.mpv_player.property_reads == [], (
        f"kapalı pencerede property okundu: "
        f"{built.window.mpv_player.property_reads}")


def test_an_open_dialog_reads_only_the_safe_property_set(player_factory):
    """Yalniz GEREKEN guvenli property'ler; liste urunun kendi sabitinden."""
    from app.media_info import VIDEO_PARAM_PROPERTIES

    built = player_factory(current_file="C:/x/Film.mkv", with_menu=False)

    menu_actions.show_media_info(built.window)

    expected = {"file-format", "metadata"} | set(VIDEO_PARAM_PROPERTIES)
    assert set(built.window.mpv_player.property_reads) == expected


def test_a_failing_property_read_breaks_neither_dialog_nor_player(
        qt_app, player_factory):
    built = player_factory(current_file="C:/x/Film.mkv", with_menu=False,
                           raise_property=True)

    dialog = menu_actions.show_media_info(built.window)
    menu_actions.refresh_media_info(built.window)

    assert isinstance(dialog, MediaInfoDialog)
    assert dialog.isVisible() is True


# =====================================================================
# 13-15. Kapanis ve yasak altyapi
# =====================================================================

def test_close_media_info_is_idempotent_and_quiet(qt_app, player_factory):
    window = player_factory(current_file="C:/x/Film.mkv",
                            with_menu=False).window
    menu_actions.show_media_info(window)

    menu_actions.close_media_info(window)
    menu_actions.close_media_info(window)
    qt_app.processEvents()

    assert window._media_info_dialog is None


def test_the_close_event_closes_the_dialog_before_stop_and_terminate():
    """Kaynak sirasi: dialog kapat -> mpv `stop()` -> `terminate()`."""
    import inspect

    from app.player import MPVPlayer

    source = inspect.getsource(MPVPlayer.closeEvent)
    close_at = source.index("close_media_info")
    stop_at = source.index("mpv_player.stop()")
    terminate_at = source.index("mpv_player.terminate()")

    assert close_at < stop_at < terminate_at, "kapanış sırası yanlış"


def test_the_update_loop_keeps_the_action_state_and_refresh():
    import inspect

    from app.player import MPVPlayer

    source = inspect.getsource(MPVPlayer.update_ui)
    assert "media_info_action" in source, "enable durumu update_ui'da yok"
    assert "refresh_media_info" in source, "tazeleme update_ui'da yok"


def test_the_integration_adds_no_timer_thread_or_observer():
    with open(menu_actions.__file__, encoding="utf-8") as handle:
        source = handle.read()

    # YALNIZ bu turda eklenen blok taranır: dosyanın geri kalanındaki
    # `show_shortcuts().exec()` MEVCUT ve bu turla ilgisiz bir çağrıdır.
    start = source.index("def media_info_property_reader")
    block = source[start:source.index("def show_shortcuts", start)]
    for forbidden in ("QTimer", "QThread", "threading", "observe_property",
                      ".exec(", "subprocess"):
        assert forbidden not in block, f"yasak altyapı: {forbidden}"


def test_the_property_reader_uses_the_real_python_mpv_api():
    """`_get_property` gercek python-mpv yoludur; tahmini `getattr` degil."""
    import inspect

    text = inspect.getsource(menu_actions.media_info_property_reader)
    assert "_get_property" in text
    assert re.search(r"file-format|metadata", text) is None, (
        "property adlari okuyucuda sabitlenmemeli; builder karar verir")
