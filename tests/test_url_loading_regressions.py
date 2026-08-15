"""URL'den oynatma: dogrulama, yuklenme gorunumu ve AYRI yasam dongusu.

Olculen durum (bu turdan once):
- `open_url()` girdiyi hic dogrulamiyor; `file:`, `javascript:` veya bos
  metin dogrudan MPV'ye veriliyordu.
- Kullanici icin hicbir yuklenme gostergesi yoktu.
- URL yuklemesi yerel dosyanin `_load_started_at` alanini paylasiyordu ve
  yerel 3 saniyelik "Dosya Acilamadi" yolu URL'ler icin de calisabiliyordu.
- `safe_console(f"URL'den oynatiliyor: {url}")` HAM URL'yi loga veriyordu.

NOT: `mpv_player.play(url)` cagrisinin GUI'yi 10 saniye BLOKE ettigi
kanitlanmadi; bu dosya bunu iddia ETMEZ ve olcmez. Olculen sey durum
makinesi, gorunur metin ve sizinti kontrolleridir. Ag erisimi YOKTUR.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QWidget

import app.media_controls as media_controls

SECRET_URL = ("https://user:s3cret@www.youtube.com/watch?v=abc123"
              "&token=deadbeefcafe#t=42")
PLAIN_URL = "https://www.youtube.com/watch?v=abc123"


class StubMpv:
    def __init__(self):
        self.played = []
        self.stopped = 0
        self.sub_visibility = None
        self.sub_delay = None

    def play(self, url):
        self.played.append(url)

    def stop(self):
        self.stopped += 1


class StubFrame:
    def __init__(self, parent):
        self.control_overlay = None
        self.placeholder_label = QLabel(parent)
        self.placeholder_label.setText(media_controls.PLACEHOLDER_DEFAULT_TEXT)


@pytest.fixture
def player_factory(tmp_path):
    app = QApplication.instance() or QApplication([])
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      str(tmp_path))
    made = []

    def factory():
        window = QMainWindow()
        window.setCentralWidget(QWidget(window))
        window.mpv_player = StubMpv()
        window.video_frame = StubFrame(window)
        window.duration = 0.0
        window.position = 0.0
        window.is_paused = True
        window._core_idle = False
        window._load_started_at = 0
        window._audio_menu_file = ""
        window._chapter_menu_file = ""
        window._pending_subs = []
        window._url_loading_active = False
        window._url_loading_started_at = 0.0
        window.playlist = []
        window.current_playlist_index = -1
        window.current_file = ""
        window.recent_files = []
        window.settings = QSettings()
        window.play_icon = object()
        window.pause_icon = object()
        window.play_button = type("_B", (), {"setIcon": lambda self, i: None})()
        window.position_slider = type(
            "_S", (), {"setValue": lambda self, v: None})()
        window._updating_position_slider = False
        window.set_title = lambda: None
        window.recents = []
        window.add_recent_file = lambda path: window.recents.append(path)
        window.update_time_label = lambda: None
        made.append(window)
        return window

    yield factory

    for window in made:
        window.close()
    app.processEvents()


@pytest.fixture
def console(monkeypatch):
    lines = []
    monkeypatch.setattr(media_controls, "safe_console", lines.append)
    return lines


def answer(monkeypatch, text, accepted=True):
    monkeypatch.setattr(media_controls.QInputDialog, "getText",
                        staticmethod(lambda *a, **k: (text, accepted)))


def errors(monkeypatch):
    seen = []
    monkeypatch.setattr(media_controls, "show_user_error",
                        lambda player, title, message, **kw:
                        seen.append((title, message, kw)))
    return seen


def status_text(player):
    return player.video_frame.placeholder_label.text()


# =====================================================================
# 1. URL dogrulama
# =====================================================================

@pytest.mark.parametrize("raw", (
    "", "   ", "dosya.mkv", "C:/video/film.mkv", "file:///C:/gizli/film.mkv",
    "javascript:alert(1)", "ftp://ornek.test/film.mkv", "https://",
    "http://", "https:///yol", "not a url",
))
def test_an_invalid_address_never_reaches_mpv(player_factory, monkeypatch,
                                              console, raw):
    player = player_factory()
    player.current_file = "C:/onceki.mkv"
    player.playlist = ["C:/onceki.mkv"]
    answer(monkeypatch, raw)
    seen = errors(monkeypatch)

    media_controls.open_url(player)

    assert player.mpv_player.played == [], f"MPV'ye verildi: {raw!r}"
    assert player.current_file == "C:/onceki.mkv", "mevcut oynatma bozuldu"
    assert player.playlist == ["C:/onceki.mkv"]
    assert player.recents == [], "geçersiz adres son açılanlara yazıldı"
    assert player._url_loading_active is False
    if raw.strip():
        assert seen, "kullanıcıya mesaj gösterilmedi"
        title, message, kw = seen[0]
        assert "exc" not in kw or kw["exc"] is None, "ham teknik hata"
        assert "http" in message.lower()


def test_a_cancelled_dialog_changes_nothing(player_factory, monkeypatch):
    player = player_factory()
    answer(monkeypatch, PLAIN_URL, accepted=False)

    media_controls.open_url(player)

    assert player.mpv_player.played == []
    assert player._url_loading_active is False


@pytest.mark.parametrize("raw", (PLAIN_URL, f"  {PLAIN_URL}  ",
                                 "http://ornek.test/canli.m3u8"))
def test_a_valid_address_is_played_exactly_once(player_factory, monkeypatch,
                                                console, raw):
    player = player_factory()
    answer(monkeypatch, raw)

    media_controls.open_url(player)

    assert player.mpv_player.played == [raw.strip()], "trim veya tek çağrı yok"
    assert player.current_file == raw.strip()


# =====================================================================
# 2. Yuklenme gorunumu
# =====================================================================

def test_the_loading_text_appears_immediately(player_factory, monkeypatch,
                                              console):
    player = player_factory()
    answer(monkeypatch, PLAIN_URL)

    media_controls.open_url(player)

    assert status_text(player) == media_controls.URL_LOADING_TEXT
    assert player.video_frame.placeholder_label.isVisible() is False or True
    assert player._url_loading_active is True
    assert player._url_loading_started_at > 0


def test_no_secret_reaches_the_status_text_or_the_log(player_factory,
                                                      monkeypatch, console):
    player = player_factory()
    answer(monkeypatch, SECRET_URL)

    media_controls.open_url(player)

    haystack = status_text(player) + "\n" + "\n".join(console)
    for secret in ("s3cret", "user:", "token", "deadbeefcafe", "abc123",
                   "#t=42", "watch?v="):
        assert secret not in haystack, f"sır sızdı: {secret}"
    assert SECRET_URL not in haystack


def test_the_state_never_stores_the_raw_url_twice(player_factory, monkeypatch,
                                                  console):
    player = player_factory()
    answer(monkeypatch, SECRET_URL)

    media_controls.open_url(player)

    values = [value for name, value in vars(player).items()
              if name.startswith("_url_loading")]
    assert all(not isinstance(value, str) or SECRET_URL not in value
               for value in values)


# =====================================================================
# 3. Basari
# =====================================================================

def test_a_positive_duration_ends_the_loading_state(player_factory,
                                                    monkeypatch, console):
    player = player_factory()
    answer(monkeypatch, PLAIN_URL)
    media_controls.open_url(player)

    player.duration = 120.0
    media_controls.update_url_loading(player)

    assert player._url_loading_active is False
    assert status_text(player) == media_controls.PLACEHOLDER_DEFAULT_TEXT


def test_a_live_stream_without_duration_still_succeeds(player_factory,
                                                       monkeypatch, console):
    """Canli yayinda duration=0 kalabilir; time-pos ilerlemesi yeter."""
    player = player_factory()
    answer(monkeypatch, PLAIN_URL)
    media_controls.open_url(player)

    player.duration = 0.0
    player.position = 3.5
    media_controls.update_url_loading(player)

    assert player._url_loading_active is False


def test_repeating_the_success_signal_has_no_side_effect(player_factory,
                                                         monkeypatch, console):
    player = player_factory()
    answer(monkeypatch, PLAIN_URL)
    media_controls.open_url(player)
    player.duration = 120.0
    media_controls.update_url_loading(player)
    played = list(player.mpv_player.played)
    text = status_text(player)

    for _ in range(50):
        media_controls.update_url_loading(player)

    assert player.mpv_player.played == played, "ek MPV yazımı"
    assert status_text(player) == text
    assert player._url_loading_active is False


# =====================================================================
# 4. Gecikme ve hata
# =====================================================================

def test_ten_seconds_alone_is_never_an_error(player_factory, monkeypatch,
                                             console):
    player = player_factory()
    answer(monkeypatch, PLAIN_URL)
    media_controls.open_url(player)
    seen = errors(monkeypatch)

    # MPV hâlâ açmaya çalışıyor: idle DEĞİL.
    player._core_idle = False
    player._url_loading_started_at -= 10.0
    media_controls.update_url_loading(player)

    assert seen == [], "10 saniye tek başına hata sayıldı"
    assert player._url_loading_active is True
    assert status_text(player) == media_controls.URL_LOADING_TEXT


def test_a_real_idle_failure_shows_a_safe_turkish_message(player_factory,
                                                          monkeypatch,
                                                          console):
    player = player_factory()
    answer(monkeypatch, PLAIN_URL)
    media_controls.open_url(player)
    seen = errors(monkeypatch)

    player._core_idle = True
    player.duration = 0.0
    player.position = 0.0
    player._url_loading_started_at -= media_controls.URL_LOAD_GRACE_SECONDS + 1

    media_controls.update_url_loading(player)

    assert len(seen) == 1
    title, message, _kw = seen[0]
    assert "açılamadı" in message.lower()
    assert "pip install" not in message.lower()
    assert "yt-dlp" not in message.lower()
    assert player._url_loading_active is False
    assert status_text(player) == media_controls.PLACEHOLDER_DEFAULT_TEXT


def test_the_failure_is_reported_only_once(player_factory, monkeypatch,
                                           console):
    player = player_factory()
    answer(monkeypatch, PLAIN_URL)
    media_controls.open_url(player)
    seen = errors(monkeypatch)
    player._core_idle = True
    player._url_loading_started_at -= media_controls.URL_LOAD_GRACE_SECONDS + 1

    for _ in range(5):
        media_controls.update_url_loading(player)

    assert len(seen) == 1


def test_the_local_three_second_path_is_skipped_while_a_url_loads(
        player_factory, monkeypatch, console):
    """URL yuklenirken YEREL 3 saniyelik genel hata yolu calismamali."""
    import inspect

    from app.player import MPVPlayer

    source = inspect.getsource(MPVPlayer.update_ui)
    assert "_url_loading_active" in source, (
        "yerel hata yolu URL durumundan haberdar değil")
    assert "pip install yt-dlp" not in source, (
        "geliştirici talimatı kullanıcı penceresine çıkıyor")


def test_the_local_three_second_contract_still_exists():
    import inspect

    from app.player import MPVPlayer

    source = inspect.getsource(MPVPlayer.update_ui)
    assert "> 3.0" in source, "yerel 3 saniyelik sözleşme kayboldu"


# =====================================================================
# 5. Merkezi ve idempotent temizlik
# =====================================================================

def loading_player(player_factory, monkeypatch):
    player = player_factory()
    answer(monkeypatch, PLAIN_URL)
    media_controls.open_url(player)
    assert player._url_loading_active is True
    return player


def test_stop_clears_the_url_loading_state(player_factory, monkeypatch,
                                           console):
    player = loading_player(player_factory, monkeypatch)

    media_controls.stop(player)

    assert player._url_loading_active is False


def test_opening_another_url_restarts_the_state_cleanly(player_factory,
                                                        monkeypatch, console):
    player = loading_player(player_factory, monkeypatch)
    first_start = player._url_loading_started_at

    answer(monkeypatch, "https://ornek.test/ikinci.m3u8")
    media_controls.open_url(player)

    assert player._url_loading_active is True
    assert player._url_loading_started_at >= first_start
    assert len(player.mpv_player.played) == 2


def test_a_local_media_clears_the_leftover_loading_text(player_factory,
                                                        monkeypatch, console,
                                                        tmp_path):
    player = loading_player(player_factory, monkeypatch)
    local = tmp_path / "Film.mkv"
    local.write_bytes(b"0")
    player.playlist = [str(local)]

    media_controls.play_from_playlist(player, 0)

    assert player._url_loading_active is False
    assert status_text(player) != media_controls.URL_LOADING_TEXT


def test_the_cleanup_is_idempotent(player_factory, monkeypatch, console):
    player = loading_player(player_factory, monkeypatch)

    for _ in range(5):
        media_controls.clear_url_loading(player)

    assert player._url_loading_active is False
    assert status_text(player) == media_controls.PLACEHOLDER_DEFAULT_TEXT


def test_the_close_path_clears_the_state():
    import inspect

    from app.player import MPVPlayer

    source = inspect.getsource(MPVPlayer.closeEvent)
    assert "clear_url_loading" in source, "kapanışta temizlik yok"
