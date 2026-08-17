# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""`Klasör Aç` ve `Son Açılanlar` davranış regresyonları.

Ölçülenler:

- `Medya Aç` alt menüsünün ve ana `Ortam` menüsünün satırları;
- klasör taramasının TEK uzantı kaynağı (`app.config.MEDIA_EXTENSIONS`),
  doğal sıralama ve alt klasör dışlaması;
- iptal / boş klasör / okuma hatası durumunda başlangıç state'inin BİREBİR
  korunması (atomiklik);
- `Son Açılanlar` modelinin iki menüde ortak olması, eksik yerel dosyanın
  modelden ve QSettings'ten temizlenmesi, URL girdisinin dosya varlığı
  kontrolüne SOKULMAMASI.

Kullanıcı metninde ham yol/URL taşınmaz; tam değer `QAction.data()` ve
tooltip üzerinden gider.
"""
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtWidgets import (
    QApplication, QLabel, QMainWindow, QMenu, QSlider, QVBoxLayout, QWidget)


ADDITIONAL_MEDIA_SUFFIXES = {
    ".webm", ".ts", ".m2ts", ".mts", ".vob", ".ogv", ".3gp", ".3g2",
    ".asf", ".mxf", ".aac", ".opus", ".wma", ".ape", ".alac", ".aiff",
    ".aif", ".ac3", ".dts", ".mka",
}


# =====================================================================
# Ortak yardımcılar
# =====================================================================

def rows(menu):
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


# =====================================================================
# 1. Klasör taraması: uzantı kaynağı, doğal sıralama, alt klasör
# =====================================================================

def test_media_suffixes_come_from_the_single_config_source():
    from app.config import MEDIA_EXTENSIONS
    from app.media_controls import media_suffixes

    expected = {pattern.lstrip("*").lower()
                for pattern in MEDIA_EXTENSIONS.split()}

    assert media_suffixes() == expected


def test_common_additional_media_suffixes_are_exposed():
    from app.media_controls import media_suffixes

    assert ADDITIONAL_MEDIA_SUFFIXES <= media_suffixes()


@pytest.mark.parametrize("suffix", sorted(ADDITIONAL_MEDIA_SUFFIXES))
def test_folder_scan_accepts_each_additional_media_suffix(tmp_path, suffix):
    from app.media_controls import folder_media_files

    path = tmp_path / f"ornek{suffix.upper()}"
    path.write_bytes(b"x")

    assert folder_media_files(str(tmp_path)) == [str(path)]


def test_natural_order_places_ten_after_two(tmp_path):
    from app.media_controls import folder_media_files

    for name in ("Bölüm 10.mkv", "Bölüm 2.mkv", "Bölüm 1.mkv"):
        (tmp_path / name).write_bytes(b"x")

    names = [os.path.basename(path)
             for path in folder_media_files(str(tmp_path))]

    assert names == ["Bölüm 1.mkv", "Bölüm 2.mkv", "Bölüm 10.mkv"]


def test_case_only_differences_are_deterministic(tmp_path):
    from app.media_controls import folder_media_files

    for name in ("bolum.mkv", "BOLUM.mp4", "Bolum.avi"):
        (tmp_path / name).write_bytes(b"x")

    first = [os.path.basename(p) for p in folder_media_files(str(tmp_path))]
    second = [os.path.basename(p) for p in folder_media_files(str(tmp_path))]

    assert first == second
    assert sorted(first) == sorted(["bolum.mkv", "BOLUM.mp4", "Bolum.avi"])


def test_uppercase_extensions_are_accepted(tmp_path):
    from app.media_controls import folder_media_files

    (tmp_path / "VIDEO.MKV").write_bytes(b"x")
    (tmp_path / "film.Mp4").write_bytes(b"x")

    names = [os.path.basename(p) for p in folder_media_files(str(tmp_path))]

    assert sorted(names) == ["VIDEO.MKV", "film.Mp4"]


@pytest.mark.parametrize("name", [
    "not.txt", "altyazi.srt", "kisayol.lnk", "site.url", "uzantisiz",
    "arsiv.zip",
])
def test_non_media_entries_are_rejected(tmp_path, name):
    from app.media_controls import folder_media_files

    (tmp_path / name).write_bytes(b"x")
    (tmp_path / "gercek.mkv").write_bytes(b"x")

    names = [os.path.basename(p) for p in folder_media_files(str(tmp_path))]

    assert names == ["gercek.mkv"]


def test_subfolders_are_not_scanned(tmp_path):
    from app.media_controls import folder_media_files

    (tmp_path / "ust.mkv").write_bytes(b"x")
    nested = tmp_path / "alt-klasör"
    nested.mkdir()
    (nested / "İçeride.mkv").write_bytes(b"x")

    names = [os.path.basename(p) for p in folder_media_files(str(tmp_path))]

    assert names == ["ust.mkv"]


def test_folder_entries_are_absolute_paths(tmp_path):
    from app.media_controls import folder_media_files

    (tmp_path / "film.mkv").write_bytes(b"x")

    paths = folder_media_files(str(tmp_path))

    assert paths == [os.path.join(str(tmp_path), "film.mkv")]
    assert all(os.path.isabs(path) for path in paths)


def test_unreadable_folder_reports_none(tmp_path):
    from app.media_controls import folder_media_files

    assert folder_media_files(str(tmp_path / "yok")) is None


def test_broken_directory_entry_does_not_abort_the_scan(tmp_path, monkeypatch):
    """Bozuk bir kayıt taramayı çökertmez; sağlam medya yine listelenir."""
    from app import media_controls

    (tmp_path / "saglam.mkv").write_bytes(b"x")
    (tmp_path / "bozuk.mkv").write_bytes(b"x")
    real_isfile = os.path.isfile

    def flaky_isfile(path):
        if os.path.basename(path) == "bozuk.mkv":
            raise OSError("bozuk kayıt")
        return real_isfile(path)

    monkeypatch.setattr(media_controls.os.path, "isfile", flaky_isfile)

    names = [os.path.basename(p)
             for p in media_controls.folder_media_files(str(tmp_path))]

    assert names == ["saglam.mkv"]


# =====================================================================
# 2. `open_folder()` state davranışı
# =====================================================================

class FolderPlayer:
    """`open_folder()` için başlangıç state'i ÖLÇÜLEBİLİR sahte oynatıcı."""

    def __init__(self, playlist=None, current_file="", index=-1):
        self.playlist = list(playlist or [])
        self.current_playlist_index = index
        self.current_file = current_file
        self.last_dir = ""
        self.duration = 0
        self.position = 0
        self.is_paused = True
        self.recent = []
        self.played = []
        self.panel_refreshes = 0
        self._pending_subs = []
        self._core_idle = False
        self._audio_menu_file = ""
        self._chapter_menu_file = ""
        self._load_started_at = 0
        self.play_icon = object()
        self.pause_icon = object()
        self.play_button = SimpleNamespace(setIcon=lambda icon: None)
        self.mpv_player = SimpleNamespace(
            play=lambda path: self.played.append(path),
            sub_delay=0.0, sub_visibility=True)
        self.video_frame = SimpleNamespace(
            control_overlay=None,
            refresh_playlist_panel=self._count_refresh,
            placeholder_label=SimpleNamespace(hide=lambda: None,
                                              show=lambda: None))

    def _count_refresh(self):
        self.panel_refreshes += 1

    def set_title(self):
        pass

    def add_recent_file(self, path):
        self.recent.append(path)

    def snapshot(self):
        return (list(self.playlist), self.current_playlist_index,
                self.current_file, list(self.recent), list(self.played),
                self.is_paused)


@pytest.fixture
def episode_folder(tmp_path):
    """Gerçek Windows kabulüyle AYNI içerik."""
    for name in ("Bölüm 10.mkv", "Bölüm 2.mkv", "Bölüm 1.mkv"):
        (tmp_path / name).write_bytes(b"x")
    (tmp_path / "not.txt").write_text("x", encoding="utf-8")
    (tmp_path / "altyazi.srt").write_text("x", encoding="utf-8")
    nested = tmp_path / "alt-klasör"
    nested.mkdir()
    (nested / "İçeride.mkv").write_bytes(b"x")
    return tmp_path


@pytest.fixture
def open_folder_env(monkeypatch):
    """`open_folder()` çağrısını sahte klasör seçimiyle koşturur."""
    from app import media_controls

    def run(selection, player=None, raises=None):
        player = player or FolderPlayer()
        captured = {}
        shown = []

        def fake_dir(parent, caption, directory="", *args, **kwargs):
            captured["caption"] = caption
            captured["directory"] = directory
            if raises is not None:
                raise raises
            return selection

        monkeypatch.setattr(media_controls.QFileDialog,
                            "getExistingDirectory", staticmethod(fake_dir))
        for level in ("information", "warning", "critical"):
            monkeypatch.setattr(
                media_controls.QMessageBox, level,
                staticmethod(lambda *a, **k: shown.append(a[1:3])))
        media_controls.open_folder(player)
        return SimpleNamespace(player=player, captured=captured, shown=shown)

    return run


def test_open_folder_builds_natural_ordered_playlist(open_folder_env,
                                                     episode_folder):
    env = open_folder_env(str(episode_folder))

    names = [os.path.basename(path) for path in env.player.playlist]
    assert names == ["Bölüm 1.mkv", "Bölüm 2.mkv", "Bölüm 10.mkv"]


def test_open_folder_plays_the_first_file_exactly_once(open_folder_env,
                                                       episode_folder):
    env = open_folder_env(str(episode_folder))

    assert len(env.player.played) == 1
    assert os.path.basename(env.player.played[0]) == "Bölüm 1.mkv"
    assert env.player.current_playlist_index == 0
    assert env.player.recent == [env.player.played[0]]


def test_open_folder_refreshes_the_playlist_panel(open_folder_env,
                                                  episode_folder):
    env = open_folder_env(str(episode_folder))

    assert env.player.panel_refreshes >= 1


def test_open_folder_has_no_duplicate_entries(open_folder_env,
                                              episode_folder):
    env = open_folder_env(str(episode_folder))

    assert len(set(env.player.playlist)) == len(env.player.playlist)


def test_open_folder_remembers_the_folder(open_folder_env, episode_folder):
    env = open_folder_env(str(episode_folder))

    assert os.path.normpath(env.player.last_dir) == os.path.normpath(
        str(episode_folder))


def test_open_folder_dialog_starts_at_valid_last_dir(open_folder_env,
                                                     episode_folder):
    player = FolderPlayer()
    player.last_dir = str(episode_folder)

    env = open_folder_env("", player=player)

    assert env.captured["directory"] == str(episode_folder)


def test_open_folder_dialog_falls_back_when_last_dir_is_gone(open_folder_env,
                                                            tmp_path):
    player = FolderPlayer()
    player.last_dir = str(tmp_path / "silinmis")

    env = open_folder_env("", player=player)

    assert env.captured["directory"] != str(tmp_path / "silinmis")
    assert not env.captured["directory"] or os.path.isdir(
        env.captured["directory"])


def test_cancelled_dialog_keeps_every_state_field(open_folder_env,
                                                  episode_folder):
    player = FolderPlayer(playlist=["C:/onceki.mkv"],
                          current_file="C:/onceki.mkv", index=0)
    before = player.snapshot()

    env = open_folder_env("", player=player)

    assert env.player.snapshot() == before
    assert env.player.panel_refreshes == 0
    assert env.shown == []


def test_empty_folder_keeps_state_and_warns_safely(open_folder_env, tmp_path):
    empty = tmp_path / "bos"
    empty.mkdir()
    player = FolderPlayer(playlist=["C:/onceki.mkv"],
                          current_file="C:/onceki.mkv", index=0)
    before = player.snapshot()

    env = open_folder_env(str(empty), player=player)

    assert env.player.snapshot() == before
    assert env.player.panel_refreshes == 0
    assert len(env.shown) == 1
    assert env.shown[0][1] == "Bu klasörde desteklenen medya dosyası bulunamadı."


def test_unsupported_only_folder_keeps_state(open_folder_env, tmp_path):
    folder = tmp_path / "belgeler"
    folder.mkdir()
    (folder / "not.txt").write_text("x", encoding="utf-8")
    (folder / "altyazi.srt").write_text("x", encoding="utf-8")
    player = FolderPlayer(playlist=["C:/onceki.mkv"],
                          current_file="C:/onceki.mkv", index=0)
    before = player.snapshot()

    env = open_folder_env(str(folder), player=player)

    assert env.player.snapshot() == before
    assert len(env.shown) == 1


def test_unreadable_folder_keeps_state_and_hides_raw_error(open_folder_env,
                                                           tmp_path):
    player = FolderPlayer(playlist=["C:/onceki.mkv"],
                          current_file="C:/onceki.mkv", index=0)
    before = player.snapshot()

    env = open_folder_env(str(tmp_path / "yok"), player=player)

    assert env.player.snapshot() == before
    assert len(env.shown) == 1
    message = env.shown[0][1]
    assert "Traceback" not in message
    assert str(tmp_path) not in message


def test_dialog_exception_keeps_state(open_folder_env, episode_folder):
    player = FolderPlayer(playlist=["C:/onceki.mkv"],
                          current_file="C:/onceki.mkv", index=0)
    before = player.snapshot()

    env = open_folder_env(str(episode_folder), player=player,
                          raises=RuntimeError("dialog patladı"))

    assert env.player.snapshot() == before
    assert env.player.panel_refreshes == 0


def test_playlist_is_untouched_until_the_scan_succeeds(monkeypatch,
                                                       episode_folder):
    """Hazırlık aşaması patlarsa mevcut liste TEMİZLENMEZ."""
    from app import media_controls

    player = FolderPlayer(playlist=["C:/onceki.mkv"],
                          current_file="C:/onceki.mkv", index=0)
    before = player.snapshot()
    monkeypatch.setattr(media_controls.QFileDialog, "getExistingDirectory",
                        staticmethod(lambda *a, **k: str(episode_folder)))
    monkeypatch.setattr(media_controls, "folder_media_files",
                        lambda folder: (_ for _ in ()).throw(
                            OSError("tarama patladı")))
    shown = []
    monkeypatch.setattr(media_controls.QMessageBox, "warning",
                        staticmethod(lambda *a, **k: shown.append(a[1:3])))

    media_controls.open_folder(player)

    assert player.snapshot() == before
    assert len(shown) == 1


def test_player_routes_open_folder():
    from app.player import MPVPlayer

    assert callable(getattr(MPVPlayer, "open_folder", None))


# =====================================================================
# 2b. Senkron `play()` hatasında ATOMİKLİK
# =====================================================================

class PlayFailurePlayer:
    """`mpv_player.play()` GERÇEKTEN exception üreten sahte oynatıcı.

    Klasör taraması başarılı olduğu hâlde ilk dosya açılamazsa hiçbir
    alan yeni medyaya kaymamalıdır.
    """

    def __init__(self):
        self.playlist = ["C:/old.mkv"]
        self.current_playlist_index = 0
        self.current_file = "C:/old.mkv"
        self.last_dir = "C:/old"
        self.duration = 123
        self.position = 45
        self.is_paused = False
        self.recent_files = ["C:/old.mkv"]
        self.recent_added = []
        self.panel_refreshes = 0
        self.play_calls = []
        self._pending_subs = ["C:/old.srt"]
        self._core_idle = True
        self._audio_menu_file = "C:/old.mkv"
        self._chapter_menu_file = "C:/old.mkv"
        self._load_started_at = 1000.0
        self._title_bar_raise_pending = True
        self.stored = {"subtitle/sub_delay": 2.5,
                       "recent_files": ["C:/old.mkv"]}
        self.play_icon = object()
        self.pause_icon = object()
        self.play_button = SimpleNamespace(setIcon=lambda icon: None)
        self.settings = SimpleNamespace(
            value=lambda key, default=None: self.stored.get(key, default),
            setValue=lambda key, value: self.stored.__setitem__(key, value))
        self.mpv_player = SimpleNamespace(
            play=self._failing_play, sub_delay=2.5, sub_visibility=True)
        self.video_frame = SimpleNamespace(
            control_overlay=None,
            refresh_playlist_panel=self._count_refresh,
            placeholder_label=SimpleNamespace(hide=lambda: None,
                                              show=lambda: None))

    def _failing_play(self, path):
        self.play_calls.append(path)
        raise RuntimeError(f"mpv açamadı: {path}")

    def _count_refresh(self):
        self.panel_refreshes += 1

    def set_title(self):
        pass

    def add_recent_file(self, path):
        self.recent_added.append(path)
        self.recent_files.insert(0, path)
        self.settings.setValue("recent_files", self.recent_files)

    def clear_title_bar_raise_pending(self):
        self._title_bar_raise_pending = False

    def mark_title_bar_raise_pending(self):
        self._title_bar_raise_pending = True

    def state(self):
        """Denetimin karşılaştırdığı BÜTÜN alanlar."""
        return {
            "playlist": list(self.playlist),
            "current_playlist_index": self.current_playlist_index,
            "current_file": self.current_file,
            "last_dir": self.last_dir,
            "duration": self.duration,
            "position": self.position,
            "is_paused": self.is_paused,
            "recent_files": list(self.recent_files),
            "_pending_subs": list(self._pending_subs),
            "_core_idle": self._core_idle,
            "_audio_menu_file": self._audio_menu_file,
            "_chapter_menu_file": self._chapter_menu_file,
            "_load_started_at": self._load_started_at,
            "_title_bar_raise_pending": self._title_bar_raise_pending,
            "mpv.sub_delay": self.mpv_player.sub_delay,
            "mpv.sub_visibility": self.mpv_player.sub_visibility,
            "settings": dict(self.stored),
        }


@pytest.fixture
def play_failure_env(monkeypatch, episode_folder):
    """Klasör TARAMASI başarılı, `play()` senkron patlıyor."""
    from app import media_controls

    def run():
        player = PlayFailurePlayer()
        before = player.state()
        errors = []
        monkeypatch.setattr(media_controls.QFileDialog, "getExistingDirectory",
                            staticmethod(lambda *a, **k: str(episode_folder)))
        monkeypatch.setattr(
            media_controls, "show_user_error",
            lambda parent, title, message, **kwargs: errors.append(
                (title, message)))
        for level in ("information", "warning", "critical"):
            monkeypatch.setattr(
                media_controls.QMessageBox, level,
                staticmethod(lambda *a, **k: errors.append(a[1:3])))
        media_controls.open_folder(player)
        return SimpleNamespace(player=player, before=before, errors=errors)

    return run


def test_sync_play_failure_is_actually_triggered(play_failure_env):
    """Test double GERÇEKTEN patlamalı; AST/kaynak kontrolü değil."""
    env = play_failure_env()

    assert len(env.player.play_calls) == 1
    assert os.path.basename(env.player.play_calls[0]) == "Bölüm 1.mkv"


def test_sync_play_failure_preserves_the_whole_state(play_failure_env):
    env = play_failure_env()

    assert env.player.state() == env.before


@pytest.mark.parametrize("field", [
    "playlist", "current_playlist_index", "current_file", "last_dir",
    "duration", "position", "is_paused", "recent_files", "_pending_subs",
    "_core_idle", "_audio_menu_file", "_chapter_menu_file",
    "_load_started_at", "_title_bar_raise_pending", "mpv.sub_delay",
    "mpv.sub_visibility", "settings",
])
def test_sync_play_failure_restores_each_field(play_failure_env, field):
    env = play_failure_env()

    assert env.player.state()[field] == env.before[field]


def test_sync_play_failure_does_not_touch_recent_files(play_failure_env):
    env = play_failure_env()

    assert env.player.recent_added == []
    assert env.player.settings.value("recent_files") == ["C:/old.mkv"]


def test_sync_play_failure_does_not_refresh_the_panel(play_failure_env):
    env = play_failure_env()

    assert env.player.panel_refreshes == 0


def test_sync_play_failure_shows_exactly_one_safe_message(play_failure_env,
                                                          episode_folder):
    env = play_failure_env()

    assert len(env.errors) == 1
    title, message = env.errors[0]
    assert title == "Dosya Açılamadı"
    assert "Traceback" not in message
    assert "RuntimeError" not in message
    assert "mpv açamadı" not in message
    assert str(episode_folder) not in message
    assert "Bölüm 1.mkv" not in message


def test_play_from_playlist_reports_success_and_failure(episode_folder):
    """`open_folder()` geri almayı bu SONUÇ üzerinden karara bağlar."""
    from app.media_controls import play_from_playlist

    player = FolderPlayer(playlist=[str(episode_folder / "Bölüm 1.mkv")])

    assert play_from_playlist(player, 0) is True
    assert play_from_playlist(player, 5) is False


def test_play_from_playlist_reports_false_on_sync_play_error(monkeypatch):
    from app import media_controls

    player = PlayFailurePlayer()
    monkeypatch.setattr(media_controls, "show_user_error",
                        lambda *a, **k: None)

    assert media_controls.play_from_playlist(player, 0) is False


# ---------------------------------------------------------------------
# 2c. QSettings anahtarının ÜÇ ayrı durumu
#     yok / okunabilir / okunamıyor — aynı sentinel ile temsil edilemez.
# ---------------------------------------------------------------------

class RecordingSettings:
    """`contains`/`value`/`setValue`/`remove` çağrılarını kaydeden ayar."""

    def __init__(self, stored=None, fail_read=False, fail_contains=False):
        self.stored = dict(stored or {})
        self.fail_read = fail_read
        self.fail_contains = fail_contains
        self.value_calls = []
        self.set_calls = []
        self.remove_calls = []

    def contains(self, key):
        if self.fail_contains:
            raise RuntimeError("registry okunamadı: HKCU erişimi yok")
        return key in self.stored

    def value(self, key, default=None):
        self.value_calls.append(key)
        if self.fail_read and key == "subtitle/sub_delay":
            raise RuntimeError("registry okunamadı: HKCU erişimi yok")
        return self.stored.get(key, default)

    def setValue(self, key, value):
        self.set_calls.append((key, value))
        self.stored[key] = value

    def remove(self, key):
        self.remove_calls.append(key)
        self.stored.pop(key, None)


@pytest.fixture
def settings_failure_env(monkeypatch, episode_folder):
    """Farklı ayar durumlarıyla senkron `play()` hatası akışı."""
    from app import media_controls

    def run(settings, failing_play=True):
        player = PlayFailurePlayer()
        player.settings = settings
        player.stored = settings.stored
        if not failing_play:
            player.mpv_player.play = lambda path: player.play_calls.append(path)
        before = player.state()
        errors = []
        monkeypatch.setattr(media_controls.QFileDialog, "getExistingDirectory",
                            staticmethod(lambda *a, **k: str(episode_folder)))
        monkeypatch.setattr(
            media_controls, "show_user_error",
            lambda parent, title, message, **kwargs: errors.append(
                (title, message)))
        for level in ("information", "warning", "critical"):
            monkeypatch.setattr(
                media_controls.QMessageBox, level,
                staticmethod(lambda *a, **k: errors.append(a[1:3])))
        media_controls.open_folder(player)
        return SimpleNamespace(player=player, before=before, errors=errors,
                               settings=settings)

    return run


# A) Anahtar gerçekten yok
def test_absent_setting_is_removed_after_failed_attempt(settings_failure_env):
    settings = RecordingSettings({"recent_files": ["C:/old.mkv"]})

    env = settings_failure_env(settings)

    assert "subtitle/sub_delay" not in settings.stored
    assert settings.remove_calls == ["subtitle/sub_delay"]


def test_absent_setting_state_is_fully_preserved(settings_failure_env):
    settings = RecordingSettings({"recent_files": ["C:/old.mkv"]})

    env = settings_failure_env(settings)

    state = env.player.state()
    for field in ("playlist", "current_file", "last_dir", "duration",
                  "position", "_pending_subs", "_core_idle",
                  "_title_bar_raise_pending", "mpv.sub_delay",
                  "mpv.sub_visibility"):
        assert state[field] == env.before[field], field


# B) Anahtar var ve okunabiliyor
def test_readable_setting_is_restored_without_remove(settings_failure_env):
    settings = RecordingSettings({"subtitle/sub_delay": 2.5,
                                  "recent_files": ["C:/old.mkv"]})

    env = settings_failure_env(settings)

    assert settings.stored["subtitle/sub_delay"] == 2.5
    assert settings.remove_calls == []
    assert ("subtitle/sub_delay", 2.5) in settings.set_calls


# C) Ayar okunamıyor: işlem BAŞLAMADAN iptal edilir
@pytest.mark.parametrize("broken", [
    {"fail_read": True}, {"fail_contains": True},
])
def test_unreadable_setting_never_removes_the_existing_key(
        settings_failure_env, broken):
    settings = RecordingSettings({"subtitle/sub_delay": 2.5,
                                  "recent_files": ["C:/old.mkv"]}, **broken)

    env = settings_failure_env(settings)

    assert settings.remove_calls == []
    assert settings.stored["subtitle/sub_delay"] == 2.5


@pytest.mark.parametrize("broken", [
    {"fail_read": True}, {"fail_contains": True},
])
def test_unreadable_setting_is_not_overwritten(settings_failure_env, broken):
    settings = RecordingSettings({"subtitle/sub_delay": 2.5,
                                  "recent_files": ["C:/old.mkv"]}, **broken)

    env = settings_failure_env(settings)

    assert [key for key, _value in settings.set_calls
            if key == "subtitle/sub_delay"] == []


@pytest.mark.parametrize("broken", [
    {"fail_read": True}, {"fail_contains": True},
])
def test_unreadable_setting_aborts_before_touching_mpv(settings_failure_env,
                                                       broken):
    """Eski değer yakalanamıyorsa oynatma DENENMEZ."""
    settings = RecordingSettings({"subtitle/sub_delay": 2.5,
                                  "recent_files": ["C:/old.mkv"]}, **broken)

    env = settings_failure_env(settings, failing_play=False)

    assert env.player.play_calls == []
    assert env.player.state() == env.before
    assert env.player.panel_refreshes == 0


@pytest.mark.parametrize("broken", [
    {"fail_read": True}, {"fail_contains": True},
])
def test_unreadable_setting_shows_one_safe_message(settings_failure_env,
                                                   broken, episode_folder):
    settings = RecordingSettings({"subtitle/sub_delay": 2.5,
                                  "recent_files": ["C:/old.mkv"]}, **broken)

    env = settings_failure_env(settings, failing_play=False)

    assert len(env.errors) == 1
    title, message = env.errors[0]
    assert "registry okunamadı" not in message
    assert "RuntimeError" not in message
    assert "Traceback" not in message
    assert str(episode_folder) not in message


def test_settings_states_are_distinguishable(settings_failure_env):
    """Yok / okunabilir / okunamıyor AYNI sonucu üretmemeli."""
    absent = RecordingSettings({})
    readable = RecordingSettings({"subtitle/sub_delay": 2.5})
    unreadable = RecordingSettings({"subtitle/sub_delay": 2.5},
                                   fail_read=True)

    settings_failure_env(absent)
    settings_failure_env(readable)
    unreadable_env = settings_failure_env(unreadable, failing_play=False)

    assert absent.remove_calls == ["subtitle/sub_delay"]
    assert readable.remove_calls == []
    assert unreadable.remove_calls == []
    assert unreadable_env.player.play_calls == []


def test_successful_folder_open_is_unchanged_after_the_fix(open_folder_env,
                                                           episode_folder):
    """Geri alma yolu BAŞARILI akışı bozmamalı."""
    env = open_folder_env(str(episode_folder))

    names = [os.path.basename(path) for path in env.player.playlist]
    assert names == ["Bölüm 1.mkv", "Bölüm 2.mkv", "Bölüm 10.mkv"]
    assert env.player.current_playlist_index == 0
    assert len(env.player.played) == 1
    assert env.player.recent == [env.player.playlist[0]]
    assert env.player.panel_refreshes >= 1
    assert os.path.normpath(env.player.last_dir) == os.path.normpath(
        str(episode_folder))
    assert env.shown == []


# =====================================================================
# 3. `Son Açılanlar` ortak modeli
# =====================================================================

class RecentPlayer(QMainWindow):
    """Ana menü + sağ-tık menüsü için ortak sahte oynatıcı."""

    def __init__(self, recent_files=None):
        super().__init__()
        self.recent_files = list(recent_files or [])
        self.opened = []
        self.recent_opened = []

    def open_path(self, path):
        self.opened.append(path)

    def open_recent(self, path):
        self.recent_opened.append(path)


RECENT = ["C:/videolar/film.mkv", "C:/muzik/sarki.mp3",
          "https://ornek.test/yayin.m3u8"]


@pytest.fixture
def recent_menu_env():
    app = QApplication.instance() or QApplication([])
    created = []

    def factory(recent_files=None):
        from app.menu_actions import populate_recent_menu

        window = RecentPlayer(recent_files)
        menu = QMenu(window)
        populate_recent_menu(window, menu)
        created.append(window)
        return SimpleNamespace(window=window, menu=menu, app=app)

    yield factory

    for window in created:
        window.close()
        window.deleteLater()
    app.processEvents()


def test_recent_rows_use_display_names_only(recent_menu_env):
    env = recent_menu_env(RECENT)

    # YENI SOZLESME: uzak adreste YALNIZ guvenli host gorunur; yol ve
    # dosya adi menuye cikmaz.
    assert rows(env.menu) == ["film.mkv", "sarki.mp3", "ornek.test"]


def test_recent_rows_keep_the_full_value_in_data_and_tooltip(recent_menu_env):
    """`data()` her zaman GERCEK hedef; tooltip uzak adreste MASKELI."""
    env = recent_menu_env(RECENT)

    for action, path in zip(env.menu.actions(), RECENT):
        assert action.data() == path
        assert path not in action.text()
        if path.startswith(("http://", "https://")):
            assert action.toolTip() == "ornek.test"
            assert action.statusTip() == "ornek.test"
            assert "yayin.m3u8" not in action.toolTip()
        else:
            assert action.toolTip() == path


def test_every_recent_row_opens_its_own_entry(recent_menu_env):
    """Lambda late-binding olsaydı hepsi SON girdiyi açardı."""
    env = recent_menu_env(RECENT)

    for action in env.menu.actions():
        action.trigger()

    assert env.window.recent_opened == RECENT


def test_recent_menu_is_capped_at_ten_rows(recent_menu_env):
    many = [f"C:/videolar/film{index}.mkv" for index in range(25)]

    env = recent_menu_env(many)

    assert len(env.menu.actions()) == 10
    assert rows(env.menu) == [f"film{index}.mkv" for index in range(10)]


def test_empty_recent_menu_shows_disabled_placeholder(recent_menu_env):
    env = recent_menu_env([])

    assert rows(env.menu) == ["Son açılan dosya yok"]
    assert not env.menu.actions()[0].isEnabled()


def test_repopulate_does_not_stack_stale_rows(recent_menu_env):
    from app.menu_actions import populate_recent_menu

    env = recent_menu_env(RECENT)
    env.window.recent_files = ["C:/yeni.mkv"]

    populate_recent_menu(env.window, env.menu)
    populate_recent_menu(env.window, env.menu)

    assert rows(env.menu) == ["yeni.mkv"]


def test_main_menu_recent_uses_the_shared_builder(recent_menu_env):
    from app.menu_actions import update_recent_menu

    env = recent_menu_env(RECENT)
    env.window.recent_menu = QMenu(env.window)

    update_recent_menu(env.window)

    assert rows(env.window.recent_menu) == rows(env.menu)


# =====================================================================
# 4. Eksik yerel dosya ve URL ayrımı
# =====================================================================

class RecentOpenPlayer:
    """`open_recent()` için gerçek model + QSettings davranışı."""

    def __init__(self, recent_files, tmp_path):
        self.recent_files = list(recent_files)
        self.playlist = ["C:/oynayan.mkv"]
        self.current_playlist_index = 0
        self.current_file = "C:/oynayan.mkv"
        self.opened = []
        self.stored = {}
        self.menu_updates = 0
        self.settings = SimpleNamespace(
            setValue=lambda key, value: self.stored.__setitem__(key, value))

    def open_path(self, path):
        self.opened.append(path)

    def remove_recent_file(self, path):
        if path in self.recent_files:
            self.recent_files.remove(path)
            self.settings.setValue("recent_files", self.recent_files)
            self.menu_updates += 1


@pytest.fixture
def open_recent_env(monkeypatch, tmp_path):
    from app import media_controls

    def run(path, recent_files):
        player = RecentOpenPlayer(recent_files, tmp_path)
        shown = []
        for level in ("information", "warning", "critical"):
            monkeypatch.setattr(
                media_controls.QMessageBox, level,
                staticmethod(lambda *a, **k: shown.append(a[1:3])))
        media_controls.open_recent(player, path)
        return SimpleNamespace(player=player, shown=shown)

    return run


def test_existing_local_recent_opens_through_open_path(open_recent_env,
                                                       tmp_path):
    real = tmp_path / "film.mkv"
    real.write_bytes(b"x")

    env = open_recent_env(str(real), [str(real)])

    assert env.player.opened == [str(real)]
    assert env.player.recent_files == [str(real)]
    assert env.shown == []


def test_missing_local_recent_is_not_played(open_recent_env, tmp_path):
    missing = str(tmp_path / "silinmis.mkv")

    env = open_recent_env(missing, [missing, "C:/baska.mkv"])

    assert env.player.opened == []


def test_missing_local_recent_is_removed_from_model_and_settings(
        open_recent_env, tmp_path):
    missing = str(tmp_path / "silinmis.mkv")

    env = open_recent_env(missing, [missing, "C:/baska.mkv"])

    assert env.player.recent_files == ["C:/baska.mkv"]
    assert env.player.stored["recent_files"] == ["C:/baska.mkv"]
    assert env.player.menu_updates == 1


def test_missing_local_recent_message_is_safe(open_recent_env, tmp_path):
    missing = str(tmp_path / "silinmis.mkv")

    env = open_recent_env(missing, [missing])

    assert len(env.shown) == 1
    message = env.shown[0][1]
    assert message == ("Dosya artık mevcut değil. "
                       "Son Açılanlar listesinden kaldırıldı.")
    assert str(tmp_path) not in message
    assert "Traceback" not in message


def test_missing_local_recent_keeps_playback_state(open_recent_env, tmp_path):
    missing = str(tmp_path / "silinmis.mkv")

    env = open_recent_env(missing, [missing])

    assert env.player.playlist == ["C:/oynayan.mkv"]
    assert env.player.current_file == "C:/oynayan.mkv"
    assert env.player.current_playlist_index == 0


@pytest.mark.parametrize("url", [
    "https://ornek.test/yayin.m3u8",
    "http://ornek.test/video.mp4",
    "rtsp://ornek.test/canli",
])
def test_url_recent_entries_skip_the_file_check(open_recent_env, url):
    env = open_recent_env(url, [url])

    assert env.player.opened == [url]
    assert env.player.recent_files == [url]
    assert env.shown == []


def test_player_routes_open_recent_and_remove_recent():
    from app.player import MPVPlayer

    assert callable(getattr(MPVPlayer, "open_recent", None))
    assert callable(getattr(MPVPlayer, "remove_recent_file", None))


# =====================================================================
# 5. Menü entegrasyonu (sağ-tık + ana menü)
# =====================================================================

MEDIA_ROWS = ["Dosya Aç", "Klasör Aç", "Bağlantıdan Oynat", "---",
              "Son Açılanlar"]


@pytest.fixture
def frame_env(tmp_path):
    app = QApplication.instance() or QApplication([])
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      str(tmp_path))
    created = []

    def factory(recent_files=None):
        from app.video_frame import VideoFrame

        calls = []
        window = QMainWindow()
        window.central_widget = QWidget(window)
        window.setCentralWidget(window.central_widget)
        window.main_layout = QVBoxLayout(window.central_widget)
        window.duration = 600.0
        window.position = 0.0
        window.current_file = "C:/video.mkv"
        window.is_paused = False
        window.is_muted = False
        window.playlist = []
        window.current_playlist_index = 0
        window.loop_file = False
        window.loop_playlist = False
        window.shuffle = False
        window._updating_position_slider = False
        window._pending_subs = []
        window.recent_files = list(recent_files or [])
        window.recent_opened = []
        window.open_recent = lambda path: window.recent_opened.append(path)
        window.volume_slider = QSlider(Qt.Orientation.Horizontal)
        window.position_slider = QSlider()
        window.current_time_label = QLabel()
        window.total_time_label = QLabel()
        window.play_button = SimpleNamespace(setIcon=lambda icon: None)
        window.play_icon = object()
        window.pause_icon = object()
        window.update_time_label = lambda: None
        window.mpv_player = SimpleNamespace(
            aid=1, sid=1, audio_device="auto", sub_visibility=False,
            speed=1.0, track_list=[], audio_device_list=[],
            command=lambda *a, **k: None)

        def recorder(name):
            def call(*args, **kwargs):
                calls.append(name)
            return call

        for name in ("open_file", "open_folder", "open_url", "open_path",
                     "play_pause", "stop", "play_previous", "play_next",
                     "show_playlist", "toggle_mute", "select_audio_track",
                     "select_audio_device", "toggle_subtitles",
                     "select_subtitle_language", "open_subtitle",
                     "open_subtitle_center", "show_subtitle_settings",
                     "toggle_fullscreen", "take_screenshot",
                     "setup_video_adjustments", "seek_relative", "goto_time",
                     "set_playback_speed", "set_loop_file",
                     "set_loop_playlist", "toggle_shuffle", "close",
                     "seek_position", "show_media_info"):
            setattr(window, name, recorder(name))
        frame = VideoFrame(window)
        window.video_frame = frame
        created.append(window)
        app.processEvents()
        return SimpleNamespace(frame=frame, window=window, calls=calls)

    yield factory

    for window in created:
        window.close()
        window.deleteLater()
    app.processEvents()


def test_context_media_submenu_order(frame_env):
    env = frame_env(RECENT)

    media = submenu(env.frame.build_context_menu(), "Medya Aç")

    assert rows(media) == MEDIA_ROWS


def test_context_folder_row_calls_open_folder_once(frame_env):
    env = frame_env()

    media = submenu(env.frame.build_context_menu(), "Medya Aç")
    find_action(media, "Klasör Aç").trigger()

    assert env.calls.count("open_folder") == 1


def test_context_recent_rows_match_the_shared_model(frame_env):
    env = frame_env(RECENT)

    media = submenu(env.frame.build_context_menu(), "Medya Aç")
    recent = submenu(media, "Son Açılanlar")

    assert rows(recent) == ["film.mkv", "sarki.mp3", "ornek.test"]
    assert [action.data() for action in recent.actions()] == RECENT


def test_context_recent_row_opens_its_entry_once(frame_env):
    env = frame_env(RECENT)

    media = submenu(env.frame.build_context_menu(), "Medya Aç")
    recent = submenu(media, "Son Açılanlar")
    recent.actions()[1].trigger()

    assert env.window.recent_opened == ["C:/muzik/sarki.mp3"]


def test_context_recent_submenu_is_rebuilt_per_open(frame_env):
    env = frame_env(RECENT)

    env.frame.build_context_menu()
    env.window.recent_files = ["C:/yeni.mkv"]
    media = submenu(env.frame.build_context_menu(), "Medya Aç")

    assert rows(submenu(media, "Son Açılanlar")) == ["yeni.mkv"]


def test_rebuilding_menus_does_not_multiply_actions(frame_env):
    env = frame_env(RECENT)

    for _ in range(3):
        media = submenu(env.frame.build_context_menu(), "Medya Aç")
        recent = submenu(media, "Son Açılanlar")

    assert len(recent.actions()) == len(RECENT)
    assert rows(media) == MEDIA_ROWS


def test_context_and_main_menu_do_not_share_action_objects(frame_env):
    from app.menu_actions import populate_recent_menu

    env = frame_env(RECENT)
    main_recent = QMenu(env.window)
    populate_recent_menu(env.window, main_recent)
    media = submenu(env.frame.build_context_menu(), "Medya Aç")
    context_recent = submenu(media, "Son Açılanlar")

    assert rows(main_recent) == rows(context_recent)
    assert not set(main_recent.actions()) & set(context_recent.actions())


class MainMenuPlayer(QMainWindow):
    """`setup_menu()` için minimum ama gerçek QMainWindow."""

    def __init__(self, recent_files=None):
        super().__init__()
        self.__dict__["calls"] = []
        self.recent_files = list(recent_files or [])
        self.speed_actions = {}
        self.loop_file = False
        self.loop_playlist = False
        self.shuffle = False
        self.current_file = ""
        self.mpv_player = SimpleNamespace(
            aid=1, sid=1, audio_device="auto", audio_device_list=[],
            track_list=[], command=lambda *a, **k: None)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)

        def recorder(*args, **kwargs):
            self.__dict__["calls"].append(name)
        return recorder


@pytest.fixture
def main_menu_env():
    app = QApplication.instance() or QApplication([])
    created = []

    def factory(recent_files=None):
        from app.menu_actions import setup_menu

        window = MainMenuPlayer(recent_files)
        setup_menu(window)
        created.append(window)
        return SimpleNamespace(window=window, app=app,
                               file_menu=window.menuBar().actions()[0].menu())

    yield factory

    for window in created:
        window.close()
        window.deleteLater()
    app.processEvents()


def test_main_menu_has_open_folder_after_open_file(main_menu_env):
    env = main_menu_env()

    file_rows = rows(env.file_menu)

    assert file_rows.index("Klasör Aç") == file_rows.index("Dosya Aç") + 1


def test_main_menu_open_folder_calls_the_product_method_once(main_menu_env):
    env = main_menu_env()

    find_action(env.file_menu, "Klasör Aç").trigger()

    assert env.window.calls.count("open_folder") == 1


def test_both_menus_bind_the_same_product_method(main_menu_env, frame_env):
    """Ana menü ve sağ-tık aynı `open_folder` metodunu çağırır."""
    env = main_menu_env()
    frame = frame_env()

    find_action(env.file_menu, "Klasör Aç").trigger()
    find_action(submenu(frame.frame.build_context_menu(), "Medya Aç"),
                "Klasör Aç").trigger()

    assert env.window.calls.count("open_folder") == 1
    assert frame.calls.count("open_folder") == 1


def test_new_media_updates_both_menus(main_menu_env, frame_env):
    """Yeni medya açıldıktan sonra iki menü de güncel listeyi gösterir."""
    from app.menu_actions import update_recent_menu

    env = main_menu_env(["C:/eski.mkv"])
    frame = frame_env(["C:/eski.mkv"])

    env.window.recent_files.insert(0, "C:/yeni.mkv")
    frame.window.recent_files.insert(0, "C:/yeni.mkv")
    update_recent_menu(env.window)
    context_recent = submenu(
        submenu(frame.frame.build_context_menu(), "Medya Aç"), "Son Açılanlar")

    assert rows(env.window.recent_menu) == ["yeni.mkv", "eski.mkv"]
    assert rows(context_recent) == ["yeni.mkv", "eski.mkv"]
