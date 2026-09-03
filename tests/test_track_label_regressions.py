# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Ses/altyazı parça ETİKETLERİ ve sadeleştirilmiş ses menüsü regresyonları.

Kullanıcıya görünen metin ham MPV metadata'sı değildir: `eng`, `und`,
`(ID: 1)`, `5.1(side)`, `None` gibi teknik artıklar menüde görünmemeli.
Ana menü ve video sağ-tık menüsü AYNI etiket üreticisini kullanmalıdır.

Bu tur ses/altyazı parça adlandırması ve ses menüsünün sadeleştirilmesiyle
sınırlıdır; sağ-tık menüsünün genel hiyerarşisi değişmez.
"""
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QActionGroup
from PyQt6.QtWidgets import (
    QApplication, QLabel, QMainWindow, QSlider, QVBoxLayout, QWidget)

from app import track_labels

FORBIDDEN_TOKENS = ("(ID:", "(side)", "None", "demux-channel-count",
                    "demux-samplerate", "demux-bitrate")
FORBIDDEN_WORDS = ("eng", "tur", "und")


def has_raw_code(text):
    """Kullanıcı metninde tek başına ham dil kodu var mı?"""
    lowered = f" {str(text).lower()} "
    for word in FORBIDDEN_WORDS:
        for suffix in (" ", ",", ".", "—", "·", ")"):
            if f" {word}{suffix}" in lowered:
                return True
    return False


def assert_clean(text):
    for token in FORBIDDEN_TOKENS:
        assert token not in text, f"teknik artik gorunuyor: {token!r} -> {text!r}"
    assert not has_raw_code(text), f"ham dil kodu gorunuyor: {text!r}"


# =====================================================================
# 1. Saf yardımcılar
# =====================================================================

@pytest.mark.parametrize("code,expected", [
    ("en", "İngilizce"), ("eng", "İngilizce"),
    ("tr", "Türkçe"), ("tur", "Türkçe"),
    ("de", "Almanca"), ("deu", "Almanca"), ("ger", "Almanca"),
    ("fr", "Fransızca"), ("fra", "Fransızca"), ("fre", "Fransızca"),
    ("es", "İspanyolca"), ("spa", "İspanyolca"),
    ("it", "İtalyanca"), ("ita", "İtalyanca"),
    ("pt", "Portekizce"), ("por", "Portekizce"),
    ("ru", "Rusça"), ("rus", "Rusça"),
    ("ar", "Arapça"), ("ara", "Arapça"),
    ("ja", "Japonca"), ("jpn", "Japonca"),
    ("ko", "Korece"), ("kor", "Korece"),
    ("zh", "Çince"), ("zho", "Çince"), ("chi", "Çince"),
    ("nl", "Felemenkçe"), ("nld", "Felemenkçe"), ("dut", "Felemenkçe"),
    ("pl", "Lehçe"), ("pol", "Lehçe"),
    ("uk", "Ukraynaca"), ("ukr", "Ukraynaca"),
])
def test_language_codes_map_to_turkish_names(code, expected):
    assert track_labels.language_name(code) == expected


@pytest.mark.parametrize("code", ["EN", "Eng", "TUR", "tUr"])
def test_language_codes_are_case_insensitive(code):
    assert track_labels.language_name(code) in ("İngilizce", "Türkçe")


@pytest.mark.parametrize("code", ["und", "", None, "zzz", 5])
def test_unknown_language_is_empty_not_raw(code):
    assert track_labels.language_name(code) == ""


@pytest.mark.parametrize("codec,expected", [
    ("eac3", "E-AC-3"), ("e-ac-3", "E-AC-3"), ("EAC3", "E-AC-3"),
    ("ac3", "AC-3"), ("aac", "AAC"), ("dts", "DTS"),
    ("truehd", "TrueHD"), ("flac", "FLAC"), ("opus", "Opus"), ("mp3", "MP3"),
])
def test_codec_normalisation(codec, expected):
    assert track_labels.codec_name(codec) == expected


@pytest.mark.parametrize("count,layout,expected", [
    (1, None, "Mono"),
    (2, None, "Stereo"),
    (6, None, "5.1"),
    (8, None, "7.1"),
    (None, "5.1(side)", "5.1"),
    (6, "5.1(side)", "5.1"),
    (None, "7.1", "7.1"),
])
def test_channel_normalisation(count, layout, expected):
    assert track_labels.channel_name(count, layout) == expected


def test_channel_layout_suffix_is_never_shown():
    assert "(side)" not in track_labels.channel_name(6, "5.1(side)")


@pytest.mark.parametrize("rate,expected", [
    (48000, "48 kHz"), (44100, "44,1 kHz"), (96000, "96 kHz"),
])
def test_sample_rate_labels(rate, expected):
    assert track_labels.sample_rate_label(rate) == expected


@pytest.mark.parametrize("bps,expected", [
    (640000, "640 kb/sn"), (192000, "192 kb/sn"),
])
def test_bitrate_labels(bps, expected):
    assert track_labels.bitrate_label(bps) == expected


@pytest.mark.parametrize("value", [None, 0, "", "abc"])
def test_numeric_helpers_are_safe_with_bad_metadata(value):
    assert track_labels.sample_rate_label(value) == ""
    assert track_labels.bitrate_label(value) == ""
    assert track_labels.channel_name(value, None) == ""


# =====================================================================
# 2. Ses parçası etiketleri
# =====================================================================

def audio(**kwargs):
    track = {"type": "audio", "id": kwargs.pop("id", 1)}
    track.update(kwargs)
    return track


def test_full_audio_label():
    label = track_labels.audio_track_label(audio(
        lang="eng", codec="eac3", **{"demux-channel-count": 6,
                                     "demux-samplerate": 48000,
                                     "demux-bitrate": 640000},
        default=True))

    assert label == "İngilizce — E-AC-3 · 5.1 · 48 kHz · 640 kb/sn · Varsayılan"


def test_partial_audio_label_has_no_empty_separators():
    label = track_labels.audio_track_label(audio(
        lang="tur", codec="ac3", **{"demux-channel-count": 2,
                                    "demux-bitrate": 192000}))

    assert label == "Türkçe — AC-3 · Stereo · 192 kb/sn"
    assert "··" not in label and not label.endswith("·")


def test_known_title_is_translated():
    label = track_labels.audio_track_label(audio(
        lang="eng", title="Director Commentary", codec="aac",
        **{"demux-channel-count": 2}))

    assert label == "İngilizce — Yönetmen Yorumu · AAC · Stereo"


def test_language_only_audio_label():
    assert track_labels.audio_track_label(audio(lang="eng")) == "İngilizce"


def test_unknown_language_falls_back_to_meaningful_title():
    label = track_labels.audio_track_label(audio(lang="und",
                                                 title="Isitme Engelli Mix"))

    assert label == "Isitme Engelli Mix"
    assert_clean(label)


def test_empty_audio_track_uses_a_safe_default():
    assert track_labels.audio_track_label(audio()) == "Ses Parçası"


def test_unknown_title_is_preserved_verbatim():
    label = track_labels.audio_track_label(audio(lang="tur",
                                                 title="Stüdyo Miksi 2"))

    assert "Stüdyo Miksi 2" in label


def test_long_title_is_truncated_but_keeps_technical_detail():
    long_title = "A" * 200
    label = track_labels.audio_track_label(audio(
        lang="eng", title=long_title, codec="aac",
        **{"demux-channel-count": 6}))

    assert len(label) <= track_labels.MAX_LABEL_CHARS
    assert label.startswith("İngilizce — ")
    assert "AAC" in label and "5.1" in label


@pytest.mark.parametrize("flag,expected", [
    ("default", "Varsayılan"), ("forced", "Zorunlu"), ("external", "Harici"),
])
def test_audio_flags(flag, expected):
    label = track_labels.audio_track_label(audio(lang="tur", **{flag: True}))

    assert label == f"Türkçe — {expected}"


def test_identical_tracks_are_disambiguated():
    tracks = [audio(id=1, lang="eng", codec="eac3",
                    **{"demux-channel-count": 6}),
              audio(id=2, lang="eng", codec="eac3",
                    **{"demux-channel-count": 6})]

    labels = track_labels.audio_track_labels(tracks)

    assert labels[0] != labels[1]
    assert labels[0].endswith("— Parça 1")
    assert labels[1].endswith("— Parça 2")


def test_distinct_tracks_are_not_numbered():
    tracks = [audio(id=1, lang="eng"), audio(id=2, lang="tur")]

    labels = track_labels.audio_track_labels(tracks)

    assert labels == ["İngilizce", "Türkçe"]


def test_audio_labels_never_leak_technical_tokens():
    tracks = [audio(id=1, lang="eng", codec="eac3",
                    **{"demux-channel-count": 6,
                       "demux-samplerate": 48000,
                       "demux-bitrate": 640000}, default=True),
              audio(id=2, lang="und"),
              audio(id=3)]

    for label in track_labels.audio_track_labels(tracks):
        assert_clean(label)


def test_helpers_are_qt_free():
    """Yalnızca KOD ölçülür; docstring'de kuralın kendisi anlatılabilir."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(track_labels))
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list) or not body:
            continue
        first = body[0]
        if (isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            del body[0]
    code = ast.unparse(tree)

    for forbidden in ("PyQt6", "QAction", "QMenu", "import mpv", "urllib"):
        assert forbidden not in code, forbidden


# =====================================================================
# 3. Altyazı parçası etiketleri
# =====================================================================

def sub(**kwargs):
    track = {"type": "sub", "id": kwargs.pop("id", 1)}
    track.update(kwargs)
    return track


def test_internal_turkish_subtitle():
    assert track_labels.subtitle_track_label(sub(lang="tur")) == "Türkçe"


def test_external_turkish_subtitle():
    label = track_labels.subtitle_track_label(sub(lang="tr", external=True))

    assert label == "Türkçe — Harici"


def test_hearing_impaired_subtitle():
    label = track_labels.subtitle_track_label(
        sub(lang="eng", hearing_impaired=True))

    assert label == "İngilizce — SDH"


def test_forced_subtitle():
    label = track_labels.subtitle_track_label(sub(lang="tur", forced=True))

    assert label == "Türkçe — Zorunlu"


def test_subtitle_title_is_shown_with_the_language():
    label = track_labels.subtitle_track_label(sub(lang="eng",
                                                  title="Signs and Songs"))

    assert label.startswith("İngilizce")
    assert "Signs and Songs" in label


def test_subtitle_filename_is_only_a_last_resort():
    label = track_labels.subtitle_track_label(
        sub(**{"external-filename": r"C:\x\Resident.Alien.S01E01.srt",
               "external": True}))

    assert "Resident.Alien.S01E01" in label
    assert_clean(label)


def test_long_subtitle_filename_is_truncated():
    name = "C:/x/" + ("B" * 300) + ".srt"
    label = track_labels.subtitle_track_label(
        sub(**{"external-filename": name, "external": True}))

    assert len(label) <= track_labels.MAX_LABEL_CHARS


def test_empty_subtitle_track_uses_a_safe_default():
    assert track_labels.subtitle_track_label(sub()) == "Altyazı Parçası"


def test_subtitle_labels_never_leak_technical_tokens():
    tracks = [sub(id=1, lang="eng", hearing_impaired=True),
              sub(id=2, lang="und"), sub(id=3)]

    for label in track_labels.subtitle_track_labels(tracks):
        assert_clean(label)


# =====================================================================
# 4. Ana menü
# =====================================================================

class MenuPlayer(QMainWindow):
    """`setup_menu()` için minimum ama gerçek QMainWindow."""

    def __init__(self, tracks=None, aid=1, sid=1, devices=None,
                 raise_on_tracks=False):
        super().__init__()
        self.__dict__["calls"] = []
        self.loop_file = False
        self.loop_playlist = False
        self.shuffle = False
        self.speed_actions = {}
        self.recent_files = []
        self.current_file = "C:/video.mkv"
        self.selected_aid = None
        self.selected_sid = None
        device_list = devices if devices is not None else [
            {"name": "auto", "description": "Otomatik"},
            {"name": "wasapi/x", "description": "Hoparlör (Realtek)"}]

        class Mpv:
            """`track_list` okuması BOZUK olabilen sahte MPV."""

            def __init__(self):
                self.aid = aid
                self.sid = sid
                self.audio_device = "auto"
                self.audio_device_list = device_list
                self._tracks = tracks if tracks is not None else []

            @property
            def track_list(self):
                if raise_on_tracks:
                    raise RuntimeError("track_list okunamadi")
                return self._tracks

            def command(self, *args, **kwargs):
                return None

        self.mpv_player = Mpv()

    def select_audio_track(self, aid):
        self.selected_aid = aid

    def select_subtitle_language(self, sid):
        self.selected_sid = sid

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)

        def recorder(*args, **kwargs):
            self.__dict__["calls"].append(name)
        return recorder


AUDIO_TRACKS = [
    {"type": "audio", "id": 1, "lang": "eng", "codec": "eac3",
     "demux-channel-count": 6, "demux-samplerate": 48000,
     "demux-bitrate": 640000, "default": True},
    {"type": "audio", "id": 2, "lang": "tur", "codec": "ac3",
     "demux-channel-count": 2, "demux-bitrate": 192000},
]
SUB_TRACKS = [
    {"type": "sub", "id": 1, "lang": "tur"},
    {"type": "sub", "id": 2, "lang": "eng", "hearing_impaired": True},
    {"type": "sub", "id": 3, "lang": "tr", "external": True,
     "external-filename": "C:/x/film.srt"},
]


@pytest.fixture
def menu_player():
    app = QApplication.instance() or QApplication([])
    created = []

    def factory(**kwargs):
        from app.menu_actions import setup_menu

        window = MenuPlayer(**kwargs)
        setup_menu(window)
        created.append(window)
        return app, window

    yield factory

    for window in created:
        window.close()
        window.deleteLater()
    app.processEvents()


def submenu_titles(menu_bar):
    titles = []
    for action in menu_bar.actions():
        menu = action.menu()
        if menu is None:
            continue
        for item in menu.actions():
            titles.append(item.text())
            child = item.menu()
            if child is not None:
                titles.extend(a.text() for a in child.actions())
    return titles


def find_menu(menu_bar, title):
    for action in menu_bar.actions():
        menu = action.menu()
        if menu is None:
            continue
        for item in menu.actions():
            if item.text() == title and item.menu() is not None:
                return item.menu()
    return None


def test_main_menu_uses_audio_track_name(menu_player):
    app, window = menu_player(tracks=AUDIO_TRACKS)

    assert find_menu(window.menuBar(), "Ses Parçası") is not None


def test_main_menu_uses_audio_output_name(menu_player):
    app, window = menu_player()

    assert find_menu(window.menuBar(), "Ses Çıkışı") is not None


def test_main_menu_uses_subtitle_track_name(menu_player):
    app, window = menu_player()

    assert find_menu(window.menuBar(), "Altyazı Parçası") is not None


@pytest.mark.parametrize("old", [
    "Ses Kanalı", "Ses Kanalları", "Ses Dili", "Ses Aygıtı",
    "Ses Kanallarını Yenile", "Aygıtları Yenile", "Otomatik Seç",
])
def test_old_audio_names_are_gone(menu_player, old):
    app, window = menu_player()

    assert old not in submenu_titles(window.menuBar()), old


def test_audio_track_rows_are_user_friendly(menu_player):
    from app.menu_actions import refresh_audio_tracks

    app, window = menu_player(tracks=AUDIO_TRACKS)
    refresh_audio_tracks(window)
    menu = find_menu(window.menuBar(), "Ses Parçası")
    texts = [a.text() for a in menu.actions()]

    assert texts == [
        "İngilizce — E-AC-3 · 5.1 · 48 kHz · 640 kb/sn · Varsayılan",
        "Türkçe — AC-3 · Stereo · 192 kb/sn",
    ]
    for text in texts:
        assert_clean(text)


def test_selected_audio_track_is_checked_and_exclusive(menu_player):
    from app.menu_actions import refresh_audio_tracks

    app, window = menu_player(tracks=AUDIO_TRACKS, aid=2)
    refresh_audio_tracks(window)
    menu = find_menu(window.menuBar(), "Ses Parçası")
    actions = [a for a in menu.actions() if a.isCheckable()]

    assert [a.isChecked() for a in actions] == [False, True]
    groups = {a.actionGroup() for a in actions}
    assert len(groups) == 1 and None not in groups
    assert groups.pop().isExclusive() is True


def test_audio_refresh_twice_does_not_duplicate_rows(menu_player):
    from app.menu_actions import refresh_audio_tracks

    app, window = menu_player(tracks=AUDIO_TRACKS)
    refresh_audio_tracks(window)
    first = len(find_menu(window.menuBar(), "Ses Parçası").actions())
    refresh_audio_tracks(window)
    second = len(find_menu(window.menuBar(), "Ses Parçası").actions())

    assert first == second == 2


def test_audio_refresh_does_not_rescan_external_files_on_gui_thread(menu_player):
    """Menu rendering must never start native file I/O from the GUI thread."""
    from app.menu_actions import refresh_audio_tracks

    app, window = menu_player(tracks=AUDIO_TRACKS)
    calls = []
    window.mpv_player.command = lambda *args: calls.append(args)

    refresh_audio_tracks(window)

    assert calls == []


def test_audio_refresh_uses_observed_snapshot_without_mpv_reads(menu_player):
    """The timer path can render a watcher snapshot without taking mpv locks."""
    from app.menu_actions import refresh_audio_tracks

    app, window = menu_player(raise_on_tracks=True)

    class NoSyncReadMpv:
        def __getattr__(self, name):
            raise AssertionError(f"unexpected synchronous mpv read: {name}")

    window.mpv_player = NoSyncReadMpv()
    refreshed = refresh_audio_tracks(
        window, track_list=AUDIO_TRACKS, current_aid=2)
    actions = find_menu(window.menuBar(), "Ses Parçası").actions()

    assert refreshed is True
    assert [action.isChecked() for action in actions] == [False, True]


def test_audio_track_id_reaches_the_callback_but_not_the_text(menu_player):
    from app.menu_actions import refresh_audio_tracks

    app, window = menu_player(tracks=AUDIO_TRACKS)
    refresh_audio_tracks(window)
    menu = find_menu(window.menuBar(), "Ses Parçası")
    second = menu.actions()[1]

    second.trigger()

    assert window.selected_aid == 2
    assert "2" not in second.text().replace("192", "").replace("5.1", "")


def test_broken_track_list_shows_a_safe_disabled_row(menu_player):
    from app.menu_actions import refresh_audio_tracks

    app, window = menu_player(raise_on_tracks=True)
    refresh_audio_tracks(window)
    menu = find_menu(window.menuBar(), "Ses Parçası")

    assert len(menu.actions()) == 1
    assert menu.actions()[0].isEnabled() is False


def test_subtitle_rows_use_the_shared_helper(menu_player):
    from app.menu_actions import refresh_subtitle_tracks

    app, window = menu_player(tracks=SUB_TRACKS)
    refresh_subtitle_tracks(window)
    menu = find_menu(window.menuBar(), "Altyazı Parçası")
    texts = [a.text() for a in menu.actions()]

    assert texts == ["Türkçe", "İngilizce — SDH", "Türkçe — Harici"]
    for text in texts:
        assert_clean(text)


def test_subtitle_selection_is_exclusive_and_stable(menu_player):
    from app.menu_actions import refresh_subtitle_tracks

    app, window = menu_player(tracks=SUB_TRACKS, sid=3)
    refresh_subtitle_tracks(window)
    menu = find_menu(window.menuBar(), "Altyazı Parçası")
    first = len(menu.actions())
    refresh_subtitle_tracks(window)
    actions = [a for a in menu.actions() if a.isCheckable()]

    assert len(menu.actions()) == first == 3
    assert [a.isChecked() for a in actions] == [False, False, True]
    groups = {a.actionGroup() for a in actions}
    assert len(groups) == 1 and None not in groups
    assert groups.pop().isExclusive() is True


def test_audio_output_rows_are_listed(menu_player):
    from app.menu_actions import refresh_audio_devices

    app, window = menu_player()
    refresh_audio_devices(window)
    menu = find_menu(window.menuBar(), "Ses Çıkışı")
    texts = [a.text() for a in menu.actions()]

    assert "Hoparlör (Realtek)" in texts
    assert "Otomatik Seç" not in texts


# =====================================================================
# 5. Video sağ-tık menüsü AYNI etiketleri kullanır
# =====================================================================

@pytest.fixture
def context_frame(monkeypatch, tmp_path):
    from PyQt6.QtCore import QSettings

    app = QApplication.instance() or QApplication([])
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      str(tmp_path))
    created = []

    def factory(tracks):
        from app.video_frame import VideoFrame

        window = QMainWindow()
        window.central_widget = QWidget(window)
        window.setCentralWidget(window.central_widget)
        window.main_layout = QVBoxLayout(window.central_widget)
        window.duration = 600.0
        window.position = 0.0
        window.is_paused = False
        window.is_muted = False
        window.current_file = "C:/video.mkv"
        window._updating_position_slider = False
        window._pending_subs = []
        window.volume_slider = QSlider(Qt.Orientation.Horizontal)
        window.position_slider = QSlider()
        window.current_time_label = QLabel()
        window.total_time_label = QLabel()
        window.play_button = SimpleNamespace(setIcon=lambda icon: None)
        window.play_icon = object()
        window.pause_icon = object()
        window.update_time_label = lambda: None
        window.selected_aid = None
        window.selected_sid = None
        window.mpv_player = SimpleNamespace(
            time_pos=0.0, pause=False, sub_visibility=False, sid=1, aid=1,
            track_list=tracks, stop=lambda: None, speed=1.0,
            audio_device="auto", audio_device_list=[],
            command=lambda *a, **k: None)
        window.select_audio_track = lambda aid: setattr(window, "selected_aid",
                                                        aid)
        window.select_subtitle_language = lambda sid: setattr(
            window, "selected_sid", sid)
        window.is_paused = False
        window.is_muted = False
        window.playlist = []
        window.current_playlist_index = 0
        window.loop_file = False
        window.loop_playlist = False
        window.shuffle = False
        # Gruplanmış sağ-tık menüsünün bağladığı BÜTÜN ürün metotları.
        for name in ("play_previous", "play_next", "play_pause", "stop",
                     "toggle_mute", "toggle_fullscreen",
                     "toggle_picture_in_picture",
                     "setup_video_adjustments", "open_file", "open_folder",
                     "open_url", "open_path",
                     "take_screenshot", "show_playlist", "toggle_subtitles",
                     "open_subtitle", "open_subtitle_center",
                     "show_subtitle_settings", "select_audio_device",
                     "seek_relative", "goto_time", "set_playback_speed",
                     "set_loop_file", "set_loop_playlist", "toggle_shuffle",
                     "close", "seek_position", "show_media_info"):
            setattr(window, name, lambda *a, **k: None)
        frame = VideoFrame(window)
        window.video_frame = frame
        created.append(window)
        app.processEvents()
        return app, frame

    yield factory

    for window in created:
        window.close()
        window.deleteLater()
    app.processEvents()


def collect(menu, depth=0):
    """Menüdeki bütün alt menüleri {baslik: [satirlar]} olarak toplar.

    NOT: sağ-tık menüsü artık gruplanmış bir hiyerarşidir; `Ses Parçası`
    ve `Altyazı Parçası` üst düzeyde değil, `Ses`/`Altyazı` altındadır.
    """
    rows = {}
    if depth > 3:
        return rows
    for action in menu.actions():
        child = action.menu()
        if child is None:
            continue
        rows[action.text()] = [a.text() for a in child.actions()]
        rows.update(collect(child, depth + 1))
    return rows


def test_context_menu_uses_audio_track_name(context_frame):
    app, frame = context_frame(AUDIO_TRACKS)

    rows = collect(frame.build_context_menu())

    assert "Ses Parçası" in rows
    assert "Ses Kanalı" not in rows


def test_context_menu_audio_rows_match_the_main_menu(context_frame):
    app, frame = context_frame(AUDIO_TRACKS)

    rows = collect(frame.build_context_menu())

    assert rows["Ses Parçası"] == track_labels.audio_track_labels(AUDIO_TRACKS)


def test_context_menu_subtitle_rows_use_the_shared_helper(context_frame):
    app, frame = context_frame(SUB_TRACKS)

    rows = collect(frame.build_context_menu())

    assert rows.get("Altyazı Parçası") == track_labels.subtitle_track_labels(
        SUB_TRACKS)


def test_context_menu_never_shows_technical_tokens(context_frame):
    app, frame = context_frame(AUDIO_TRACKS + SUB_TRACKS)

    for title, items in collect(frame.build_context_menu()).items():
        assert_clean(title)
        for text in items:
            assert_clean(text)


def test_context_menu_audio_selection_is_exclusive(context_frame):
    app, frame = context_frame(AUDIO_TRACKS)

    menu = frame.build_context_menu()
    audio = next(a.menu() for a in menu.actions()
                 if a.text() == "Ses" and a.menu() is not None)
    tracks = next(a.menu() for a in audio.actions()
                  if a.text() == "Ses Parçası" and a.menu() is not None)
    rows = [a for a in tracks.actions() if a.isCheckable()]
    assert rows
    groups = {a.actionGroup() for a in rows}
    assert len(groups) == 1 and None not in groups
    assert groups.pop().isExclusive() is True


def test_context_menu_audio_selection_reaches_the_player(context_frame):
    app, frame = context_frame(AUDIO_TRACKS)

    menu = frame.build_context_menu()
    audio = next(a.menu() for a in menu.actions()
                 if a.text() == "Ses" and a.menu() is not None)
    tracks = next(a.menu() for a in audio.actions()
                  if a.text() == "Ses Parçası" and a.menu() is not None)
    tracks.actions()[1].trigger()

    assert frame.main_window.selected_aid == 2


# =====================================================================
# 5b. GERÇEK libmpv kanal alanları
# =====================================================================
#
# Bağımsız gerçek libmpv ölçümünde audio track sözlüğü şu anahtarları
# veriyor: `audio-channels`, `demux-channel-count`, `demux-channels`,
# `demux-samplerate`. Kanal YERLEŞİMİ `demux-channels` alanındadır;
# `demux-channel-layout` gerçek bir track_list alanı DEĞİLDİR.

@pytest.mark.parametrize("track,expected", [
    ({"demux-channels": "5.1(side)"}, "İngilizce — 5.1"),
    ({"demux-channels": "7.1"}, "İngilizce — 7.1"),
    ({"demux-channels": "stereo"}, "İngilizce — Stereo"),
    ({"demux-channels": "mono"}, "İngilizce — Mono"),
    ({"audio-channels": 6}, "İngilizce — 5.1"),
    ({"audio-channels": 2}, "İngilizce — Stereo"),
    ({"demux-channel-count": 8}, "İngilizce — 7.1"),
])
def test_real_mpv_channel_fields(track, expected):
    assert track_labels.audio_track_label(audio(lang="eng", **track)) == expected


def test_layout_wins_over_count_but_they_are_not_mixed():
    label = track_labels.audio_track_label(audio(
        lang="eng", **{"demux-channels": "stereo", "audio-channels": 6}))

    assert label == "İngilizce — Stereo"


def test_unknown_layout_falls_back_to_the_channel_count():
    label = track_labels.audio_track_label(audio(
        lang="eng", **{"demux-channels": "unknown6", "audio-channels": 6}))

    assert label == "İngilizce — 5.1"
    assert "unknown6" not in label


def test_missing_channel_fields_produce_no_channel_part():
    assert track_labels.audio_track_label(audio(lang="eng")) == "İngilizce"


def test_real_mpv_track_never_leaks_layout_internals():
    label = track_labels.audio_track_label(audio(
        lang="eng", codec="eac3",
        **{"demux-channels": "5.1(side)", "audio-channels": 6,
           "demux-channel-count": 6, "demux-samplerate": 48000}))

    assert label == "İngilizce — E-AC-3 · 5.1 · 48 kHz"
    assert_clean(label)
    assert "unknown" not in label


REAL_MPV_AUDIO = [
    {"type": "audio", "id": 1, "lang": "eng", "codec": "eac3",
     "audio-channels": 6, "demux-channel-count": 6,
     "demux-channels": "5.1(side)", "demux-samplerate": 48000},
    {"type": "audio", "id": 2, "lang": "tur", "codec": "aac",
     "audio-channels": 2, "demux-channel-count": 2,
     "demux-channels": "stereo", "demux-samplerate": 48000},
]


def test_real_mpv_tracks_render_the_same_in_both_menus(menu_player,
                                                       context_frame):
    from app.menu_actions import refresh_audio_tracks

    expected = track_labels.audio_track_labels(REAL_MPV_AUDIO)
    assert expected == ["İngilizce — E-AC-3 · 5.1 · 48 kHz",
                        "Türkçe — AAC · Stereo · 48 kHz"]

    app, window = menu_player(tracks=REAL_MPV_AUDIO)
    refresh_audio_tracks(window)
    main_rows = [a.text() for a in
                 find_menu(window.menuBar(), "Ses Parçası").actions()]

    app2, frame = context_frame(REAL_MPV_AUDIO)
    context_rows = collect(frame.build_context_menu())["Ses Parçası"]

    assert main_rows == context_rows == expected


# =====================================================================
# 6. İndirilen altyazının dil metadata'sı
# =====================================================================

class MetadataMpv:
    """`sub-add` metadata imzasını DESTEKLEYEN sahte MPV."""

    def __init__(self):
        self.track_list = []
        self.sid = "no"
        self.sub_visibility = False
        self.add_calls = []
        self._next = 1

    def sub_add(self, path, *args):
        self.add_calls.append((path,) + tuple(args))
        track = {"type": "sub", "id": self._next,
                 "external-filename": path, "external": True}
        if len(args) >= 3:
            track["title"] = args[1]
            track["lang"] = args[2]
        self._next += 1
        self.track_list.append(track)

    def sub_remove(self, sid):
        self.track_list = [t for t in self.track_list if t.get("id") != sid]


class LegacyMpv(MetadataMpv):
    """ESKİ imza: yalnızca tek argüman kabul eder."""

    def sub_add(self, path, *args):
        if args:
            raise TypeError("sub_add() takes 2 positional arguments")
        super().sub_add(path)


class FailingMetadataMpv(MetadataMpv):
    """Metadata çağrısı KONTROLLÜ biçimde başarısız olur (track eklenmez)."""

    def sub_add(self, path, *args):
        if args:
            raise RuntimeError("sub-add metadata reddedildi")
        super().sub_add(path)


@pytest.mark.parametrize("mpv_class", [MetadataMpv, LegacyMpv,
                                       FailingMetadataMpv])
def test_apply_adds_exactly_one_track(tmp_path, mpv_class):
    from app import subtitle_service as service

    mpv = mpv_class()
    player = SimpleNamespace(mpv_player=mpv, video_frame=None)
    target = str(tmp_path / "film.srt")
    (tmp_path / "film.srt").write_bytes(b"x")

    applied = service.SubtitleSession().apply(player, target, language="tr")

    external = [t for t in mpv.track_list if t.get("external-filename")]
    assert applied is True
    assert len(external) == 1, f"fallback duplicate uretti: {mpv.add_calls}"


def test_language_metadata_reaches_sub_add(tmp_path):
    from app import subtitle_service as service

    mpv = MetadataMpv()
    player = SimpleNamespace(mpv_player=mpv, video_frame=None)
    target = str(tmp_path / "film.srt")
    (tmp_path / "film.srt").write_bytes(b"x")

    service.SubtitleSession().apply(player, target, language="tr")

    assert len(mpv.add_calls) == 1
    call = mpv.add_calls[0]
    assert call[1] == "select"
    assert call[2] == "Türkçe"
    assert call[3] == "tr"


def test_applied_track_reads_back_as_turkish_external(tmp_path):
    from app import subtitle_service as service

    mpv = MetadataMpv()
    player = SimpleNamespace(mpv_player=mpv, video_frame=None)
    target = str(tmp_path / "film.srt")
    (tmp_path / "film.srt").write_bytes(b"x")

    service.SubtitleSession().apply(player, target, language="tr")

    label = track_labels.subtitle_track_label(mpv.track_list[0])
    assert label == "Türkçe — Harici"


def test_legacy_fallback_makes_a_single_add_call(tmp_path):
    from app import subtitle_service as service

    mpv = LegacyMpv()
    player = SimpleNamespace(mpv_player=mpv, video_frame=None)
    target = str(tmp_path / "film.srt")
    (tmp_path / "film.srt").write_bytes(b"x")

    service.SubtitleSession().apply(player, target, language="tr")

    # Metadata denemesi TypeError verdi -> hicbir track eklenmedi -> tek
    # guvenli cagri yapildi.
    assert mpv.add_calls == [(target,)]


def test_apply_without_language_keeps_the_old_call(tmp_path):
    from app import subtitle_service as service

    mpv = MetadataMpv()
    player = SimpleNamespace(mpv_player=mpv, video_frame=None)
    target = str(tmp_path / "film.srt")
    (tmp_path / "film.srt").write_bytes(b"x")

    service.SubtitleSession().apply(player, target)

    assert mpv.add_calls == [(target,)]


def test_download_controller_passes_the_result_language(tmp_path):
    """İndirilen sonucun dili apply yoluna ULAŞMALI."""
    import inspect

    from app import subtitle_download_controller as controller

    source = inspect.getsource(controller.SubtitleDownloadController)
    assert "language=" in source, "sonuc dili apply'a gecirilmiyor"


def test_target_file_name_is_unchanged_by_metadata(tmp_path):
    from app import subtitle_service as service

    video = tmp_path / "Resident.Alien.S01E01.Pilot.1080p.AMZN.WEB-DL.mkv"
    video.write_bytes(b"v")

    target = service.subtitle_target_path(str(video))

    assert os.path.basename(target) == (
        "Resident.Alien.S01E01.Pilot.1080p.AMZN.WEB-DL.srt")


# =====================================================================
# 7. Controller: `apply()` YALNIZCA BİR KEZ çağrılır
# =====================================================================
#
# `except TypeError` ile bütün çağrıyı sarmak güvenli değildi: hata
# imza uyuşmazlığından değil `apply()` GÖVDESİNDEN gelirse aynı altyazı
# ikinci kez uygulanmaya çalışılıyor ve ikinci çağrı dil + iptal
# bilgisini düşürüyordu.

class RecordingSession:
    """Güncel imza; çağrıları ve parametreleri kaydeder."""

    def __init__(self, raise_type_error=False):
        self.calls = []
        self.raise_type_error = raise_type_error

    def apply(self, player, target, wait=None, attempts=None,
              is_cancelled=None, language=None, title=None):
        self.calls.append({"target": target, "wait": wait,
                           "attempts": attempts, "is_cancelled": is_cancelled,
                           "language": language, "title": title})
        if self.raise_type_error:
            # GÖVDEDEN gelen hata: imza sorunu DEĞİL.
            raise TypeError("gercek bir hata")
        return True


class LegacySession:
    """ESKİ imza: `language`/`is_cancelled` kabul etmez."""

    def __init__(self):
        self.calls = []

    def apply(self, player, target, wait=None, attempts=None):
        self.calls.append({"target": target, "attempts": attempts})
        return True


@pytest.fixture
def download_bench(tmp_path):
    from PyQt6.QtCore import QEvent

    from app.subtitle_center import SubtitleCenterDialog
    from app.subtitle_download_controller import SubtitleDownloadController

    app = QApplication.instance() or QApplication([])
    created = []
    video = tmp_path / "Resident.Alien.S01E01.1080p.mkv"
    video.write_bytes(b"v")
    result = {"file_id": 7135238, "name": "Uzak.Ad", "language": "tr",
              "format": "srt", "moviehash_match": True, "downloads": 1,
              "ratings": 1.0, "hearing_impaired": False}

    class Client:
        def download_link(self, file_id):
            return "https://dl.opensubtitles.com/download/a.srt"

        def fetch(self, url):
            return b"1\n00:00:01,000 --> 00:00:04,000\nMerhaba\n"

    def factory(session):
        window = QMainWindow()
        window.show()
        dialog = SubtitleCenterDialog(window, media={
            "file_name": str(video), "title": "Resident Alien",
            "season": 1, "episode": 1, "is_series": True,
            "target_name": "Resident.Alien.S01E01.1080p.srt"})
        dialog.show()
        mpv = MetadataMpv()
        player = SimpleNamespace(mpv_player=mpv, video_frame=None)
        controller = SubtitleDownloadController(
            dialog, client=Client(), player=player, session=session,
            owner=window)
        dialog.show_results([result])
        dialog.select_result(dialog.result_cards()[0])
        app.processEvents()
        created.append((window, dialog, controller))

        def run():
            controller.download_and_apply()
            import time as _t
            end = _t.time() + 6
            while _t.time() < end:
                app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                app.processEvents()
                if controller.is_idle() and not controller.is_applying():
                    break
                _t.sleep(0.005)

        return SimpleNamespace(app=app, run=run, mpv=mpv,
                               controller=controller, dialog=dialog)

    yield factory

    for window, dialog, controller in created:
        controller.shutdown(wait_ms=3000)
        for widget in (dialog, window):
            try:
                widget.close()
                widget.deleteLater()
            except RuntimeError:
                pass
    app.processEvents()


def test_current_session_receives_every_parameter_once(download_bench):
    session = RecordingSession()
    env = download_bench(session)

    env.run()

    assert len(session.calls) == 1
    call = session.calls[0]
    assert call["language"] == "tr"
    assert callable(call["is_cancelled"])
    assert callable(call["wait"])
    assert call["attempts"]


def test_type_error_from_the_body_does_not_retry(download_bench):
    session = RecordingSession(raise_type_error=True)
    env = download_bench(session)

    env.run()

    assert len(session.calls) == 1, (
        f"apply {len(session.calls)} kez cagrildi (cift uygulama riski)")
    assert env.dialog.status_text() != "Altyazı indirildi ve uygulandı."


def test_type_error_from_the_body_never_adds_a_second_track(download_bench):
    session = RecordingSession(raise_type_error=True)
    env = download_bench(session)

    env.run()

    assert env.mpv.add_calls == [], "ikinci MPV uygulama girisimi yapildi"


def test_type_error_does_not_drop_language_or_cancellation(download_bench):
    session = RecordingSession(raise_type_error=True)
    env = download_bench(session)

    env.run()

    call = session.calls[0]
    assert call["language"] == "tr"
    assert callable(call["is_cancelled"])


def test_legacy_session_is_called_exactly_once(download_bench):
    session = LegacySession()
    env = download_bench(session)

    env.run()

    assert len(session.calls) == 1


def test_controller_does_not_wrap_apply_in_a_type_error_retry():
    import ast
    import inspect
    import textwrap

    from app.subtitle_download_controller import SubtitleDownloadController

    source = inspect.getsource(SubtitleDownloadController._apply_to_player)
    tree = ast.parse(textwrap.dedent(source))
    calls = sum(1 for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "apply")

    assert calls == 1, f"apply {calls} kez cagriliyor (retry deseni)"


def test_real_session_path_still_applies(download_bench):
    from app import subtitle_service as service

    env = download_bench(service.SubtitleSession())

    env.run()

    external = [t for t in env.mpv.track_list if t.get("external-filename")]
    assert len(external) == 1
    assert external[0].get("lang") == "tr"


def test_repeated_download_overwrites_the_same_file(tmp_path):
    from app import subtitle_service as service

    store = service.SubtitleStore()
    target = str(tmp_path / "film.srt")
    first = b"1\n00:00:01,000 --> 00:00:04,000\nBir\n"
    second = b"1\n00:00:01,000 --> 00:00:04,000\nIki\n"

    store.save(target, first)
    store.save(target, second)

    assert open(target, "rb").read() == second
    assert sorted(p.name for p in tmp_path.iterdir()) == ["film.srt"]
