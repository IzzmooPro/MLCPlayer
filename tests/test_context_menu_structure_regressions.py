"""Video sağ-tık menüsünün YAPI ve DURUM regresyonları.

Menü düz bir liste yerine gruplanmış bir hiyerarşi olmalı; her satır gerçek
bir ürün metodunu TAM BİR KEZ çağırmalı ve metinler gerçek oynatıcı
durumundan okunmalı.

`Klasör Aç` ve `Son Açılanlar` davranışı ayrı dosyada ölçülür
(`test_open_folder_recent_regressions.py`); işlevsiz VLC satırları yoktur.
"""
import os
import sys
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtWidgets import (
    QApplication, QLabel, QMainWindow, QSlider, QVBoxLayout, QWidget)

from app import track_labels

EXPECTED_TOP = [
    "Oynat", "Durdur", "Önceki", "Sonraki",
    "---",
    "Medya Aç",
    "---",
    "Oynatma Listesi",
    "---",
    "Ses", "Altyazı", "Görüntü", "Oynatma",
    "Medya Bilgisi",
    "---",
    "Uygulamadan Çık",
]
MEDIA_ROWS = ["Dosya Aç", "Klasör Aç", "Bağlantıdan Oynat", "---",
              "Son Açılanlar"]
AUDIO_ROWS = ["Sessiz", "Ses Parçası", "Ses Çıkışı"]
SUBTITLE_ROWS = ["Altyazıları Göster", "Altyazı Parçası",
                 "Altyazı Dosyası Ekle", "Altyazı Bul", "Altyazı Ayarları"]
VIDEO_ROWS = ["Tam Ekran", "Ekran Görüntüsü Al", "Video Ayarları"]
PLAYBACK_ROWS = ["5 Saniye Geri", "5 Saniye İleri", "30 Saniye Geri",
                 "30 Saniye İleri", "Zamana Git", "Oynatma Hızı", "---",
                 "Tek Dosyayı Tekrarla", "Oynatma Listesini Tekrarla",
                 "Karıştır"]
SPEEDS = ["0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2.0x"]

FORBIDDEN_ROWS = [
    "Disk Aç", "Yakalama Aygıtı Aç",
    "DVD", "Blu-ray", "Kayıt", "Görselleştirme", "Kırpma", "Yakınlaştırma",
    "Deinterlace", "Her zaman üstte", "Aygıtları Yenile", "Otomatik Seç",
    "Ses Kanalı", "Ses Kanalları", "Ses Dili", "Ses Aygıtı", "Altyazılar",
    "Dili Seç",
]

AUDIO_TRACKS = [
    {"type": "audio", "id": 1, "lang": "eng", "codec": "eac3",
     "demux-channels": "5.1(side)", "audio-channels": 6,
     "demux-samplerate": 48000, "default": True},
    {"type": "audio", "id": 2, "lang": "tur", "codec": "ac3",
     "demux-channels": "stereo", "audio-channels": 2},
]
SUB_TRACKS = [
    {"type": "sub", "id": 1, "lang": "eng"},
    {"type": "sub", "id": 2, "lang": "tr", "external": True,
     "external-filename": "C:/x/film.srt"},
]
DEVICES = [
    {"name": "auto", "description": "Otomatik"},
    {"name": "wasapi/spk", "description": "Hoparlör (Realtek)"},
    {"name": "wasapi/hdmi", "description": "HDMI (NVIDIA)"},
]


# --- Sahte oynatıcı --------------------------------------------------

class Recorder:
    def __init__(self):
        self.calls = []

    def method(self, name):
        def call(*args, **kwargs):
            self.calls.append((name, args, kwargs))
        return call

    def names(self):
        return [name for name, _a, _k in self.calls]

    def args_for(self, name):
        return [args for called, args, _k in self.calls if called == name]


class StubMpv:
    def __init__(self, tracks, aid, sid, device, sub_visibility,
                 raise_tracks=False, devices=None):
        self.aid = aid
        self.sid = sid
        self.audio_device = device
        self.sub_visibility = sub_visibility
        self.speed = 1.0
        self._tracks = tracks
        self._raise = raise_tracks
        self.audio_device_list = DEVICES if devices is None else devices

    @property
    def track_list(self):
        if self._raise:
            raise RuntimeError("track_list okunamadi")
        return self._tracks

    def command(self, *args, **kwargs):
        return None


@pytest.fixture
def frame_factory(tmp_path):
    app = QApplication.instance() or QApplication([])
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      str(tmp_path))
    created = []

    def factory(current_file="C:/video.mkv", tracks=None, aid=1, sid=2,
                is_paused=False, is_muted=False, sub_visibility=False,
                playlist=None, index=0, loop_file=False, loop_playlist=False,
                shuffle=False, fullscreen=False, device="wasapi/spk",
                raise_tracks=False, devices=None, speed=1.0):
        from app.video_frame import VideoFrame

        recorder = Recorder()
        window = QMainWindow()
        window.central_widget = QWidget(window)
        window.setCentralWidget(window.central_widget)
        window.main_layout = QVBoxLayout(window.central_widget)
        window.duration = 600.0
        window.position = 0.0
        window.current_file = current_file
        window.is_paused = is_paused
        window.is_muted = is_muted
        window.playlist = playlist if playlist is not None else []
        window.current_playlist_index = index
        window.loop_file = loop_file
        window.loop_playlist = loop_playlist
        window.shuffle = shuffle
        window._updating_position_slider = False
        window._pending_subs = []
        window.recent_files = []
        window.volume_slider = QSlider(Qt.Orientation.Horizontal)
        window.position_slider = QSlider()
        window.current_time_label = QLabel()
        window.total_time_label = QLabel()
        window.play_button = SimpleNamespace(setIcon=lambda icon: None)
        window.play_icon = object()
        window.pause_icon = object()
        window.update_time_label = lambda: None
        window.mpv_player = StubMpv(
            tracks if tracks is not None else AUDIO_TRACKS + SUB_TRACKS,
            aid, sid, device, sub_visibility, raise_tracks, devices)
        window.mpv_player.speed = speed
        for name in ("open_file", "open_folder", "open_url", "open_path",
                     "play_pause", "stop",
                     "play_previous", "play_next", "show_playlist",
                     "toggle_mute", "select_audio_track",
                     "select_audio_device", "toggle_subtitles",
                     "select_subtitle_language", "open_subtitle",
                     "open_subtitle_center", "show_subtitle_settings",
                     "toggle_fullscreen", "take_screenshot",
                     "setup_video_adjustments", "seek_relative", "goto_time",
                     "set_playback_speed", "set_loop_file",
                     "set_loop_playlist", "toggle_shuffle", "close",
                     "seek_position", "show_media_info"):
            setattr(window, name, recorder.method(name))
        frame = VideoFrame(window)
        frame.is_video_fullscreen = fullscreen
        window.video_frame = frame
        created.append(window)
        app.processEvents()
        return SimpleNamespace(app=app, frame=frame, window=window,
                               recorder=recorder)

    yield factory

    for window in created:
        window.close()
        window.deleteLater()
    app.processEvents()


def rows(menu):
    """Menü satırları; ayırıcılar `---` olarak temsil edilir."""
    result = []
    for action in menu.actions():
        result.append("---" if action.isSeparator() else action.text())
    return result


def submenu(menu, title):
    for action in menu.actions():
        if action.text() == title and action.menu() is not None:
            return action.menu()
    return None


def find_action(menu, title):
    for action in menu.actions():
        if action.text() == title:
            return action
    return None


def all_texts(menu, depth=0):
    texts = []
    if depth > 3:
        return texts
    for action in menu.actions():
        if action.isSeparator():
            continue
        texts.append(action.text())
        child = action.menu()
        if child is not None:
            texts.extend(all_texts(child, depth + 1))
    return texts


# =====================================================================
# 1. Yapı
# =====================================================================

def test_top_level_order_and_separators(frame_factory):
    # NOT: ilk satirin METNI duruma baglidir (Oynat/Duraklat); yapiyi
    # olcmek icin duraklatilmis durum kullanilir.
    env = frame_factory(is_paused=True)

    assert rows(env.frame.build_context_menu()) == EXPECTED_TOP


def test_media_submenu_has_only_two_rows(frame_factory):
    env = frame_factory()

    menu = submenu(env.frame.build_context_menu(), "Medya Aç")

    assert rows(menu) == MEDIA_ROWS


def test_audio_submenu_rows(frame_factory):
    env = frame_factory()

    menu = submenu(env.frame.build_context_menu(), "Ses")

    assert rows(menu) == AUDIO_ROWS


def test_subtitle_submenu_rows(frame_factory):
    env = frame_factory()

    menu = submenu(env.frame.build_context_menu(), "Altyazı")

    assert rows(menu) == SUBTITLE_ROWS


def test_video_submenu_rows(frame_factory):
    env = frame_factory()

    menu = submenu(env.frame.build_context_menu(), "Görüntü")

    assert rows(menu) == VIDEO_ROWS


def test_playback_submenu_rows(frame_factory):
    env = frame_factory()

    menu = submenu(env.frame.build_context_menu(), "Oynatma")

    assert rows(menu) == PLAYBACK_ROWS


def test_speed_submenu_matches_the_main_menu(frame_factory):
    env = frame_factory()

    playback = submenu(env.frame.build_context_menu(), "Oynatma")
    speed = submenu(playback, "Oynatma Hızı")

    assert rows(speed) == SPEEDS


@pytest.mark.parametrize("forbidden", FORBIDDEN_ROWS)
def test_unimplemented_rows_are_absent(frame_factory, forbidden):
    env = frame_factory()

    texts = all_texts(env.frame.build_context_menu())

    assert forbidden not in texts, forbidden


# =====================================================================
# 2. Dinamik durum
# =====================================================================

@pytest.mark.parametrize("current_file,is_paused,expected", [
    ("", False, "Oynat"),
    ("C:/video.mkv", True, "Oynat"),
    ("C:/video.mkv", False, "Duraklat"),
])
def test_play_pause_text(frame_factory, current_file, is_paused, expected):
    env = frame_factory(current_file=current_file, is_paused=is_paused)

    assert rows(env.frame.build_context_menu())[0] == expected


@pytest.mark.parametrize("current_file,enabled", [("", False),
                                                  ("C:/video.mkv", True)])
def test_stop_enabled_state(frame_factory, current_file, enabled):
    env = frame_factory(current_file=current_file)

    menu = env.frame.build_context_menu()
    assert find_action(menu, "Durdur").isEnabled() is enabled


@pytest.mark.parametrize("playlist,index,loop,previous,following", [
    ([], 0, False, False, False),
    (["a", "b", "c"], 0, False, False, True),
    (["a", "b", "c"], 1, False, True, True),
    (["a", "b", "c"], 2, False, True, False),
    (["a", "b", "c"], 2, True, True, True),
    (["a", "b", "c"], 0, True, True, True),
])
def test_previous_next_enabled_state(frame_factory, playlist, index, loop,
                                     previous, following):
    env = frame_factory(playlist=playlist, index=index, loop_playlist=loop)

    menu = env.frame.build_context_menu()
    assert find_action(menu, "Önceki").isEnabled() is previous
    assert find_action(menu, "Sonraki").isEnabled() is following


@pytest.mark.parametrize("is_muted,expected", [(True, "Sesi Aç"),
                                               (False, "Sessiz")])
def test_mute_text(frame_factory, is_muted, expected):
    env = frame_factory(is_muted=is_muted)

    audio = submenu(env.frame.build_context_menu(), "Ses")
    assert rows(audio)[0] == expected


@pytest.mark.parametrize("visible,expected", [
    (True, "Altyazıları Gizle"), (False, "Altyazıları Göster")])
def test_subtitle_toggle_text(frame_factory, visible, expected):
    env = frame_factory(sub_visibility=visible)

    subtitle = submenu(env.frame.build_context_menu(), "Altyazı")
    assert rows(subtitle)[0] == expected


@pytest.mark.parametrize("fullscreen", [True, False])
def test_fullscreen_checked_state(frame_factory, fullscreen):
    env = frame_factory(fullscreen=fullscreen)

    video = submenu(env.frame.build_context_menu(), "Görüntü")
    action = find_action(video, "Tam Ekran")
    assert action.isCheckable() is True
    assert action.isChecked() is fullscreen


@pytest.mark.parametrize("loop_file,loop_playlist,shuffle", [
    (True, False, False), (False, True, False), (False, False, True),
    (True, True, True), (False, False, False)])
def test_loop_and_shuffle_checked_state(frame_factory, loop_file,
                                        loop_playlist, shuffle):
    env = frame_factory(loop_file=loop_file, loop_playlist=loop_playlist,
                        shuffle=shuffle)

    playback = submenu(env.frame.build_context_menu(), "Oynatma")
    assert find_action(playback, "Tek Dosyayı Tekrarla").isChecked() is loop_file
    assert find_action(
        playback, "Oynatma Listesini Tekrarla").isChecked() is loop_playlist
    assert find_action(playback, "Karıştır").isChecked() is shuffle


def test_speed_selection_is_exclusive_and_reflects_state(frame_factory):
    env = frame_factory(speed=1.5)

    playback = submenu(env.frame.build_context_menu(), "Oynatma")
    speed = submenu(playback, "Oynatma Hızı")
    actions = speed.actions()

    assert [a.isChecked() for a in actions] == [False, False, False, False,
                                                True, False]
    groups = {a.actionGroup() for a in actions}
    assert len(groups) == 1 and None not in groups
    assert groups.pop().isExclusive() is True


def test_seek_and_goto_disabled_without_media(frame_factory):
    env = frame_factory(current_file="")

    playback = submenu(env.frame.build_context_menu(), "Oynatma")
    for title in ("5 Saniye Geri", "5 Saniye İleri", "30 Saniye Geri",
                  "30 Saniye İleri", "Zamana Git"):
        assert find_action(playback, title).isEnabled() is False, title


def test_screenshot_disabled_without_media(frame_factory):
    env = frame_factory(current_file="")

    video = submenu(env.frame.build_context_menu(), "Görüntü")
    assert find_action(video, "Ekran Görüntüsü Al").isEnabled() is False


def test_state_is_reread_on_every_build(frame_factory):
    env = frame_factory(is_muted=False, fullscreen=False)
    assert rows(submenu(env.frame.build_context_menu(), "Ses"))[0] == "Sessiz"

    env.window.is_muted = True
    env.frame.is_video_fullscreen = True

    menu = env.frame.build_context_menu()
    assert rows(submenu(menu, "Ses"))[0] == "Sesi Aç"
    assert find_action(submenu(menu, "Görüntü"), "Tam Ekran").isChecked() is True


# =====================================================================
# 3. Bağlantılar
# =====================================================================

@pytest.mark.parametrize("path,title,method", [
    ([], "Durdur", "stop"),
    ([], "Önceki", "play_previous"),
    ([], "Sonraki", "play_next"),
    ([], "Oynatma Listesi", "show_playlist"),
    ([], "Uygulamadan Çık", "close"),
    (["Medya Aç"], "Dosya Aç", "open_file"),
    (["Medya Aç"], "Bağlantıdan Oynat", "open_url"),
    (["Ses"], "Sessiz", "toggle_mute"),
    (["Altyazı"], "Altyazıları Göster", "toggle_subtitles"),
    (["Altyazı"], "Altyazı Dosyası Ekle", "open_subtitle"),
    (["Altyazı"], "Altyazı Bul", "open_subtitle_center"),
    (["Altyazı"], "Altyazı Ayarları", "show_subtitle_settings"),
    (["Görüntü"], "Tam Ekran", "toggle_fullscreen"),
    (["Görüntü"], "Ekran Görüntüsü Al", "take_screenshot"),
    (["Görüntü"], "Video Ayarları", "setup_video_adjustments"),
    (["Oynatma"], "Zamana Git", "goto_time"),
    ([], "Medya Bilgisi", "show_media_info"),
])
def test_action_calls_the_product_method_once(frame_factory, path, title,
                                              method):
    env = frame_factory(playlist=["a", "b", "c"], index=1)

    menu = env.frame.build_context_menu()
    for step in path:
        menu = submenu(menu, step)
    find_action(menu, title).trigger()

    assert env.recorder.names().count(method) == 1, env.recorder.names()


def test_play_pause_action_calls_play_pause(frame_factory):
    env = frame_factory()

    menu = env.frame.build_context_menu()
    menu.actions()[0].trigger()

    assert env.recorder.names() == ["play_pause"]


@pytest.mark.parametrize("title,delta", [
    ("5 Saniye Geri", -5), ("5 Saniye İleri", 5),
    ("30 Saniye Geri", -30), ("30 Saniye İleri", 30)])
def test_seek_values(frame_factory, title, delta):
    env = frame_factory()

    playback = submenu(env.frame.build_context_menu(), "Oynatma")
    find_action(playback, title).trigger()

    assert env.recorder.args_for("seek_relative") == [(delta,)]


def test_every_speed_sends_its_own_value(frame_factory):
    env = frame_factory()

    playback = submenu(env.frame.build_context_menu(), "Oynatma")
    speed = submenu(playback, "Oynatma Hızı")
    for action in speed.actions():
        action.trigger()

    assert env.recorder.args_for("set_playback_speed") == [
        (0.5,), (0.75,), (1.0,), (1.25,), (1.5,), (2.0,)]


@pytest.mark.parametrize("title,method", [
    ("Tek Dosyayı Tekrarla", "set_loop_file"),
    ("Oynatma Listesini Tekrarla", "set_loop_playlist"),
    ("Karıştır", "toggle_shuffle")])
def test_loop_and_shuffle_call_their_methods_once(frame_factory, title,
                                                  method):
    env = frame_factory()

    playback = submenu(env.frame.build_context_menu(), "Oynatma")
    find_action(playback, title).trigger()

    assert env.recorder.names().count(method) == 1


def test_audio_track_selection_sends_the_right_id(frame_factory):
    env = frame_factory()

    audio = submenu(env.frame.build_context_menu(), "Ses")
    tracks = submenu(audio, "Ses Parçası")
    tracks.actions()[1].trigger()

    assert env.recorder.args_for("select_audio_track") == [(2,)]


def test_subtitle_track_selection_sends_the_right_id(frame_factory):
    env = frame_factory()

    subtitle = submenu(env.frame.build_context_menu(), "Altyazı")
    tracks = submenu(subtitle, "Altyazı Parçası")
    tracks.actions()[1].trigger()

    assert env.recorder.args_for("select_subtitle_language") == [(2,)]


def test_audio_device_selection_sends_the_device_name(frame_factory):
    from app.menu_actions import detect_audio_devices

    env = frame_factory()
    detect_audio_devices(env.window)

    audio = submenu(env.frame.build_context_menu(), "Ses")
    devices = submenu(audio, "Ses Çıkışı")
    devices.actions()[1].trigger()

    assert env.recorder.args_for("select_audio_device") == [("wasapi/hdmi",)]


# =====================================================================
# 4. Ses Çıkışı: ortak kaynak, tarama yok
# =====================================================================

def test_audio_output_lists_cached_devices_without_rescanning(frame_factory):
    from app.menu_actions import detect_audio_devices

    env = frame_factory()
    detect_audio_devices(env.window)
    # Menü açılışında YENİ tarama yapılmamalı: liste erişilemez hâle gelse
    # bile önbellekten okunur.
    env.window.mpv_player.audio_device_list = None

    audio = submenu(env.frame.build_context_menu(), "Ses")
    devices = submenu(audio, "Ses Çıkışı")

    assert rows(devices) == ["Hoparlör (Realtek)", "HDMI (NVIDIA)"]


def test_audio_output_marks_the_active_device(frame_factory):
    from app.menu_actions import detect_audio_devices

    env = frame_factory(device="wasapi/hdmi")
    detect_audio_devices(env.window)

    devices = submenu(submenu(env.frame.build_context_menu(), "Ses"),
                      "Ses Çıkışı")
    actions = devices.actions()

    assert [a.isChecked() for a in actions] == [False, True]
    groups = {a.actionGroup() for a in actions}
    assert len(groups) == 1 and None not in groups
    assert groups.pop().isExclusive() is True


def test_audio_output_shows_a_safe_row_when_empty(frame_factory):
    from app.menu_actions import detect_audio_devices

    env = frame_factory(devices=[])
    detect_audio_devices(env.window)

    devices = submenu(submenu(env.frame.build_context_menu(), "Ses"),
                      "Ses Çıkışı")

    assert len(devices.actions()) == 1
    assert devices.actions()[0].isEnabled() is False


def test_main_menu_and_context_menu_share_the_device_source(frame_factory):
    from app.menu_actions import audio_devices, detect_audio_devices

    env = frame_factory()
    detect_audio_devices(env.window)

    cached = audio_devices(env.window)
    devices = submenu(submenu(env.frame.build_context_menu(), "Ses"),
                      "Ses Çıkışı")

    assert [name for name, _label in cached] == [
        a.data() for a in devices.actions()]


def test_context_menu_does_not_steal_main_menu_actions(frame_factory):
    from app.menu_actions import detect_audio_devices

    env = frame_factory()
    detect_audio_devices(env.window)
    first = submenu(submenu(env.frame.build_context_menu(), "Ses"),
                    "Ses Çıkışı").actions()
    second = submenu(submenu(env.frame.build_context_menu(), "Ses"),
                     "Ses Çıkışı").actions()

    assert len(first) == len(second) == 2
    assert set(first).isdisjoint(set(second)), "aynı QAction taşındı"


# =====================================================================
# 5. Dayanıklılık
# =====================================================================

def test_menu_builds_safely_without_media(frame_factory):
    env = frame_factory(current_file="")

    assert rows(env.frame.build_context_menu()) == EXPECTED_TOP


def test_menu_builds_safely_with_none_track_list(frame_factory):
    env = frame_factory(tracks=None)
    env.window.mpv_player._tracks = None

    audio = submenu(env.frame.build_context_menu(), "Ses")
    tracks = submenu(audio, "Ses Parçası")

    assert len(tracks.actions()) == 1
    assert tracks.actions()[0].isEnabled() is False


def test_broken_track_list_shows_a_safe_disabled_row(frame_factory):
    env = frame_factory(raise_tracks=True)

    menu = env.frame.build_context_menu()
    tracks = submenu(submenu(menu, "Ses"), "Ses Parçası")
    subs = submenu(submenu(menu, "Altyazı"), "Altyazı Parçası")

    for child in (tracks, subs):
        assert len(child.actions()) == 1
        assert child.actions()[0].isEnabled() is False


def test_building_twice_does_not_duplicate_rows(frame_factory):
    env = frame_factory(is_paused=True)

    first = rows(env.frame.build_context_menu())
    second = rows(env.frame.build_context_menu())

    assert first == second == EXPECTED_TOP


def test_track_rows_use_the_shared_label_helper(frame_factory):
    env = frame_factory()

    menu = env.frame.build_context_menu()
    audio_rows = rows(submenu(submenu(menu, "Ses"), "Ses Parçası"))
    sub_rows = rows(submenu(submenu(menu, "Altyazı"), "Altyazı Parçası"))

    assert audio_rows == track_labels.audio_track_labels(AUDIO_TRACKS)
    assert sub_rows == track_labels.subtitle_track_labels(SUB_TRACKS)
    assert "Türkçe — Harici" in sub_rows


def test_no_technical_tokens_anywhere(frame_factory):
    env = frame_factory()

    for text in all_texts(env.frame.build_context_menu()):
        for token in ("(ID:", "(side)", "None"):
            assert token not in text, text
        lowered = f" {text.lower()} "
        for word in ("eng", "tur", "und"):
            assert f" {word} " not in lowered, text


def test_track_ids_live_only_in_action_data(frame_factory):
    env = frame_factory()

    menu = env.frame.build_context_menu()
    tracks = submenu(submenu(menu, "Ses"), "Ses Parçası")

    assert [a.data() for a in tracks.actions()] == [1, 2]


def test_action_groups_stay_alive_with_the_menu(frame_factory):
    env = frame_factory()

    menu = env.frame.build_context_menu()
    tracks = submenu(submenu(menu, "Ses"), "Ses Parçası")
    group = tracks.actions()[0].actionGroup()

    assert group is not None
    assert group.parent() is not None


def test_menu_is_parented_to_the_top_level_window(frame_factory):
    env = frame_factory()

    menu = env.frame.build_context_menu()

    assert menu.parent() is env.frame.window()
    assert menu.parent().isWindow() is True


# =====================================================================
# 6. Boolean toggle'lar: checked DEĞERİ metoda ULAŞMALI
# =====================================================================
#
# `MPVPlayer.set_loop_file(enabled)` / `set_loop_playlist(enabled)` /
# `toggle_shuffle(enabled)` ZORUNLU bir bool alır. Genel `Recorder` her
# argümanı kabul ettiği için gerçek imza hatasını gizliyordu; burada
# gerçek imzalı double kullanılır.

class StrictToggles:
    """Gerçek ürün imzası: `enabled` ZORUNLUDUR."""

    def __init__(self, loop_file=False, loop_playlist=False, shuffle=False):
        self.loop_file = loop_file
        self.loop_playlist = loop_playlist
        self.shuffle = shuffle
        self.calls = []

    def set_loop_file(self, enabled):
        self.calls.append(("set_loop_file", enabled))
        self.loop_file = enabled

    def set_loop_playlist(self, enabled):
        self.calls.append(("set_loop_playlist", enabled))
        self.loop_playlist = enabled

    def toggle_shuffle(self, enabled):
        self.calls.append(("toggle_shuffle", enabled))
        self.shuffle = enabled

    def args_for(self, name):
        return [(value,) for called, value in self.calls if called == name]


@pytest.fixture
def strict_toggle_frame(frame_factory):
    def factory(**state):
        env = frame_factory(**state)
        toggles = StrictToggles(
            loop_file=state.get("loop_file", False),
            loop_playlist=state.get("loop_playlist", False),
            shuffle=state.get("shuffle", False))
        # Gerçek imzalı metotlar sahte oynatıcıya BAĞLANIR.
        for name in ("set_loop_file", "set_loop_playlist", "toggle_shuffle"):
            setattr(env.window, name, getattr(toggles, name))
        env.toggles = toggles
        return env
    return factory


@pytest.mark.parametrize("title,method,state_attr", [
    ("Tek Dosyayı Tekrarla", "set_loop_file", "loop_file"),
    ("Oynatma Listesini Tekrarla", "set_loop_playlist", "loop_playlist"),
    ("Karıştır", "toggle_shuffle", "shuffle"),
])
@pytest.mark.parametrize("initial,expected", [(False, True), (True, False)])
def test_toggle_action_passes_the_checked_value(strict_toggle_frame, title,
                                                method, state_attr, initial,
                                                expected):
    env = strict_toggle_frame(**{state_attr: initial})

    playback = submenu(env.frame.build_context_menu(), "Oynatma")
    action = find_action(playback, title)
    assert action.isChecked() is initial
    action.trigger()

    assert env.toggles.args_for(method) == [(expected,)], (
        f"{method} yanlis argumanla cagrildi: {env.toggles.calls}")
    assert getattr(env.toggles, state_attr) is expected


@pytest.mark.parametrize("title,method", [
    ("Tek Dosyayı Tekrarla", "set_loop_file"),
    ("Oynatma Listesini Tekrarla", "set_loop_playlist"),
    ("Karıştır", "toggle_shuffle"),
])
def test_toggle_action_calls_the_method_exactly_once(strict_toggle_frame,
                                                     title, method):
    env = strict_toggle_frame()

    playback = submenu(env.frame.build_context_menu(), "Oynatma")
    find_action(playback, title).trigger()

    names = [called for called, _value in env.toggles.calls]
    assert names.count(method) == 1, env.toggles.calls


def test_toggle_actions_raise_no_exception(strict_toggle_frame):
    """Qt callback içinde TypeError oluşmadığı ölçülür."""
    import sys

    env = strict_toggle_frame()
    errors = []
    original = sys.excepthook

    def hook(kind, value, traceback):
        errors.append(value)

    sys.excepthook = hook
    try:
        playback = submenu(env.frame.build_context_menu(), "Oynatma")
        for title in ("Tek Dosyayı Tekrarla", "Oynatma Listesini Tekrarla",
                      "Karıştır"):
            find_action(playback, title).trigger()
    finally:
        sys.excepthook = original

    assert errors == []
    assert len(env.toggles.calls) == 3


def test_fullscreen_does_not_receive_the_checked_value(frame_factory):
    """`toggle_fullscreen()` parametre ALMAZ; checked değeri geçirilmemeli."""
    calls = []

    env = frame_factory()
    env.window.toggle_fullscreen = lambda: calls.append(True)

    video = submenu(env.frame.build_context_menu(), "Görüntü")
    find_action(video, "Tam Ekran").trigger()

    assert calls == [True]


# =====================================================================
# 7. Ses çıkışları açılışta TAM BİR KEZ taranır
# =====================================================================

class CountingMpv:
    """`audio_device_list` ERİŞİMİNİ sayan davranışsal spy."""

    def __init__(self, inner, devices):
        self._inner = inner
        self._devices = devices
        self.reads = 0

    @property
    def audio_device_list(self):
        self.reads += 1
        return self._devices

    def __getattr__(self, name):
        return getattr(self._inner, name)


def test_menu_openings_do_not_rescan_audio_devices(frame_factory):
    from app.menu_actions import detect_audio_devices

    env = frame_factory()
    spy = CountingMpv(env.window.mpv_player, DEVICES)
    env.window.mpv_player = spy

    detect_audio_devices(env.window)
    assert spy.reads == 1, "acilis taramasi bir kez olmali"

    for _ in range(2):
        submenu(submenu(env.frame.build_context_menu(), "Ses"), "Ses Çıkışı")

    assert spy.reads == 1, (
        f"menu acilisi yeniden tarama yapti (toplam {spy.reads})")


def test_startup_scan_behaviour_in_a_real_player_process():
    """KALICI davranış testi: gerçek `MPVPlayer` başlangıcında TEK tarama.

    Kaynak taraması yeterli değildir (döngü veya dolaylı bir yol eklenirse
    geçer). Ölçüm gerçek constructor akışıyla, ayrı bir child süreçte
    yapılır; native MPV yaşam döngüsü pytest sürecine sızmaz.
    """
    import subprocess

    child = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "startup_audio_device_scan_child.py")
    try:
        completed = subprocess.run(
            [sys.executable, child], capture_output=True, text=True,
            timeout=180)
    except subprocess.TimeoutExpired:
        pytest.fail("child sureci zaman asimina ugradi")

    output = completed.stdout
    assert "STARTUP_SCAN_COUNT=1" in output, (output, completed.stderr[-800:])
    assert "AFTER_MAIN_MENU_COUNT=1" in output, output
    assert "AFTER_CONTEXT_MENU_COUNT=1" in output, output
    assert "RESULTS: failures=none" in output, output
    assert completed.returncode == 0, (
        f"EXIT={completed.returncode} stderr={completed.stderr[-800:]}")


def test_startup_scans_audio_devices_exactly_once():
    """Yardımcı koruma: kaynakta çift açılış çağrısı kalmasın.

    Asıl kanıt `test_startup_scan_behaviour_in_a_real_player_process`
    davranış testidir; bu yalnız erken uyarıdır.
    """
    import ast
    import inspect

    from app import player as player_module

    tree = ast.parse(inspect.getsource(player_module.MPVPlayer))
    calls = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = getattr(func, "attr", None) or getattr(func, "id", None)
        if name == "refresh_audio_devices":
            calls += 1
    # Biri delegasyon metodu (`def refresh_audio_devices(self): ...`),
    # biri de açılış çağrısı olmalı; ÜÇÜNCÜ bir çağrı çift taramadır.
    assert calls == 2, f"refresh_audio_devices {calls} yerde cagriliyor"


def test_both_menus_share_one_device_cache(frame_factory):
    from app.menu_actions import (audio_devices, detect_audio_devices,
                                  populate_audio_device_menu)
    from PyQt6.QtWidgets import QMenu

    env = frame_factory()
    detect_audio_devices(env.window)
    cached = audio_devices(env.window)

    main_menu = QMenu()
    populate_audio_device_menu(env.window, main_menu)
    context = submenu(submenu(env.frame.build_context_menu(), "Ses"),
                      "Ses Çıkışı")

    assert [a.text() for a in main_menu.actions()] == [
        a.text() for a in context.actions()]
    assert [a.data() for a in main_menu.actions()] == [
        name for name, _label in cached]
    assert set(main_menu.actions()).isdisjoint(set(context.actions()))


def test_failed_scan_is_not_cached_as_success(frame_factory):
    from app.menu_actions import audio_devices, detect_audio_devices

    env = frame_factory()

    class Broken:
        @property
        def audio_device_list(self):
            raise RuntimeError("mpv hazir degil")

    broken = Broken()
    real_mpv = env.window.mpv_player
    env.window.mpv_player = broken
    assert detect_audio_devices(env.window) is None

    # Başarısız tarama ÖNBELLEĞE ALINMAZ: sonraki erişim yeniden dener.
    env.window.mpv_player = real_mpv
    assert audio_devices(env.window) is not None


def test_real_player_toggle_signatures_are_compatible():
    """Gerçek `MPVPlayer` metotları tek zorunlu bool alır."""
    import inspect

    from app.player import MPVPlayer

    for name in ("set_loop_file", "set_loop_playlist", "toggle_shuffle"):
        parameters = list(
            inspect.signature(getattr(MPVPlayer, name)).parameters)
        assert len(parameters) == 2, f"{name}{parameters}"


def test_submenus_do_not_repeat_inline_stylesheets():
    import ast
    import inspect

    from app import video_frame

    tree = ast.parse(inspect.getsource(video_frame))
    inline = sum(1 for node in ast.walk(tree)
                 if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute)
                 and node.func.attr == "setStyleSheet"
                 and any(isinstance(arg, ast.Constant)
                         and isinstance(arg.value, str)
                         and "QMenu" in arg.value for arg in node.args))

    assert inline <= 1, f"{inline} yerde QMenu stili tekrarlaniyor"
