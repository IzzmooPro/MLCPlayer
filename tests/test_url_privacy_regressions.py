"""Uzak URL gizliligi: pencere basligi ve KALICI son acilanlar.

Kaynaktan dogrulanan iki acik:

1. `MPVPlayer.set_title()` yerel dosya degilse `base = self.current_file`
   kullaniyordu; tam URL `userinfo`, `query`, `token` ve `fragment` ile
   birlikte PENCERE BASLIGINA cikabiliyordu.
2. `MPVPlayer.add_recent_file()` ham URL'yi `QSettings["recent_files"]`
   icine DUZ METIN yaziyordu. Gorunen ad ile hedefi ayirmak bunu cozmez;
   tam hedef diskte kaldigi surece sizinti surer.

URUN KARARI: uzak URL'ler oturum icinde Son Acilanlar'da bulunabilir ama
kalici ayara ASLA yazilmaz. Program yeniden acildiginda URL gecmisi gelmez;
bu bilincli bir gizlilik kararidir. Yerel dosya gecmisi ve 10 kayit siniri
aynen korunur. Sifreleme/DPAPI/credential store EKLENMEZ.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QApplication, QMainWindow, QMenu, QWidget

import app.menu_actions as menu_actions
from app.player import MPVPlayer

SECRET_URL = ("https://user:s3cret@www.youtube.com/watch?v=abc123"
              "&token=deadbeef#t=42")
SECRETS = ("s3cret", "user:", "abc123", "token", "deadbeef", "#t=42",
           "watch?v=")
PLAIN_URL = "https://ornek.test:8443/canli/yayin.m3u8"


class RecentHost(QMainWindow):
    """Urunun KENDI recent/title metotlarini baglar; govde kopyalanmaz."""

    set_title = MPVPlayer.set_title
    add_recent_file = MPVPlayer.add_recent_file
    remove_recent_file = MPVPlayer.remove_recent_file
    restore_recent_files = MPVPlayer.restore_recent_files
    _persistable_recent_files = MPVPlayer._persistable_recent_files

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.current_file = ""
        self.recent_menu = QMenu(self)
        self.opened = []
        self.open_path = self.opened.append


@pytest.fixture
def host(tmp_path):
    app = QApplication.instance() or QApplication([])
    made = []
    # TAM IZOLASYON: organizasyon/uygulama adi yerine ACIK dosya yolu.
    # `setPath` global oldugu icin baska bir test dosyasi ayni dizini
    # paylasip kayitlari karistirabiliyordu.
    settings_path = str(tmp_path / "ayarlar.ini")

    def factory(stored=None):
        settings = QSettings(settings_path, QSettings.Format.IniFormat)
        if stored is not None:
            settings.setValue("recent_files", list(stored))
        window = RecentHost(settings)
        window.restore_recent_files()
        made.append(window)
        return window

    yield factory

    for window in made:
        window.close()
    app.processEvents()


def local_file(tmp_path, name="Film.mkv"):
    path = tmp_path / name
    path.write_bytes(b"0")
    return str(path)


def stored_recent(window):
    value = window.settings.value("recent_files", []) or []
    return [value] if isinstance(value, str) else list(value)


def menu_actions_of(window):
    menu = QMenu(window)
    menu_actions.populate_recent_menu(window, menu)
    return [action for action in menu.actions() if action.isEnabled()]


def visible_strings(actions):
    found = []
    for action in actions:
        found.extend([action.text(), action.toolTip(), action.statusTip()])
    return found


# =====================================================================
# 1. Guvenli pencere basligi
# =====================================================================

def test_a_remote_url_never_shows_its_full_address_in_the_title(host):
    window = host()
    window.current_file = SECRET_URL

    window.set_title()

    title = window.windowTitle()
    assert title.startswith("www.youtube.com"), title
    for secret in SECRETS:
        assert secret not in title, f"başlıkta sır: {secret}"
    assert SECRET_URL not in title


def test_a_port_is_safe_to_show(host):
    window = host()
    window.current_file = PLAIN_URL

    window.set_title()

    assert window.windowTitle().startswith("ornek.test:8443")
    assert "canli" not in window.windowTitle()
    assert "yayin.m3u8" not in window.windowTitle()


def test_a_local_file_still_shows_only_its_basename(host, tmp_path):
    window = host()
    window.current_file = local_file(tmp_path, "Bolum 1.mkv")

    window.set_title()

    assert window.windowTitle().startswith("Bolum 1.mkv")
    assert str(tmp_path) not in window.windowTitle()


# NOT: `://kirik` bir http/https ADRESI DEGILDIR; mevcut yerel-yol
# davranisina duser ve bu turda degistirilmez.
@pytest.mark.parametrize("broken", ("http://", "https:///yol"))
def test_a_broken_url_falls_back_to_the_plain_app_title(host, broken):
    window = host()
    window.current_file = broken

    window.set_title()

    assert window.windowTitle() == "MLC Player"


def test_no_media_keeps_the_plain_app_title(host):
    window = host()
    window.current_file = ""

    window.set_title()

    assert window.windowTitle() == "MLC Player"


# =====================================================================
# 2. Oturumluk URL gecmisi
# =====================================================================

def test_a_url_lives_in_memory_but_never_on_disk(host):
    window = host()

    window.add_recent_file(SECRET_URL)

    assert window.recent_files == [SECRET_URL], "oturum belleğinde yok"
    assert stored_recent(window) == [], "URL kalıcı ayara yazıldı"


def test_a_local_file_is_still_persisted(host, tmp_path):
    window = host()
    path = local_file(tmp_path)

    window.add_recent_file(path)

    assert window.recent_files == [path]
    assert stored_recent(window) == [path]


def test_a_mixed_list_persists_only_the_local_entries(host, tmp_path):
    window = host()
    first = local_file(tmp_path, "A.mkv")
    second = local_file(tmp_path, "B.mkv")

    window.add_recent_file(first)
    window.add_recent_file(SECRET_URL)
    window.add_recent_file(second)

    assert window.recent_files == [second, SECRET_URL, first]
    assert stored_recent(window) == [second, first]


def test_the_ten_entry_limit_holds_in_memory_and_on_disk(host, tmp_path):
    window = host()
    for index in range(14):
        window.add_recent_file(local_file(tmp_path, f"F{index}.mkv"))

    assert len(window.recent_files) == 10
    assert len(stored_recent(window)) == 10


def test_the_url_disappears_after_a_restart(host):
    window = host()
    window.add_recent_file(SECRET_URL)

    fresh = host(stored=stored_recent(window))

    assert fresh.recent_files == [], "URL geçmişi yeniden başlatmada geldi"


def test_local_history_survives_a_restart(host, tmp_path):
    window = host()
    path = local_file(tmp_path)
    window.add_recent_file(path)

    fresh = host(stored=stored_recent(window))

    assert fresh.recent_files == [path]


# =====================================================================
# 3. Menude yalniz MASKELI deger
# =====================================================================

def test_the_menu_shows_only_a_safe_host_for_a_url(host):
    window = host()
    window.add_recent_file(SECRET_URL)

    actions = menu_actions_of(window)

    assert len(actions) == 1
    for value in visible_strings(actions):
        for secret in SECRETS:
            assert secret not in value, f"menüde sır: {secret} ({value!r})"
    assert "www.youtube.com" in actions[0].text()


def test_the_action_data_still_carries_the_real_target(host):
    window = host()
    window.add_recent_file(SECRET_URL)

    actions = menu_actions_of(window)

    assert actions[0].data() == SECRET_URL, "oturumda yeniden açılamaz"


def test_a_url_can_be_reopened_within_the_same_session(host):
    window = host()
    window.add_recent_file(SECRET_URL)

    menu_actions_of(window)[0].trigger()

    assert window.opened == [SECRET_URL]


def test_a_local_entry_keeps_its_current_menu_behaviour(host, tmp_path):
    window = host()
    path = local_file(tmp_path, "Bolum 2.mkv")
    window.add_recent_file(path)

    action = menu_actions_of(window)[0]

    assert action.text() == "Bolum 2.mkv"
    assert action.toolTip() == path
    assert action.data() == path
    action.trigger()
    assert window.opened == [path]


# =====================================================================
# 4. Eski kayitlarin temizlenmesi
# =====================================================================

def test_old_stored_urls_are_dropped_and_normalised_once(host, tmp_path):
    path = local_file(tmp_path)
    window = host(stored=[SECRET_URL, path, "http://eski.test/video.mp4"])

    assert window.recent_files == [path], "eski URL geri yüklendi"
    assert stored_recent(window) == [path], "ayar normalize edilmedi"


def test_unknown_local_style_entries_are_never_dropped(host, tmp_path):
    """Var olmayan ya da ileride desteklenecek YEREL yollar silinmez."""
    missing = str(tmp_path / "tasinmis" / "Film.mkv")
    unc = r"\\sunucu\pay\Film.mkv"
    window = host(stored=[missing, unc])

    assert window.recent_files == [missing, unc]
    assert stored_recent(window) == [missing, unc]


def test_a_clean_local_list_is_left_alone(host, tmp_path):
    path = local_file(tmp_path)
    window = host(stored=[path])

    assert window.recent_files == [path]
    assert stored_recent(window) == [path]


# =====================================================================
# 5. Basarisiz komut oturum listesine de girmez
# =====================================================================

def test_a_failed_play_never_reaches_the_recent_list(tmp_path, monkeypatch):
    import app.media_controls as media_controls

    app = QApplication.instance() or QApplication([])
    window = QMainWindow()
    window.setCentralWidget(QWidget(window))

    class AngryMpv:
        def play(self, url):
            raise RuntimeError("mpv reddetti")

    class Frame:
        control_overlay = None
        placeholder_label = None

    window.mpv_player = AngryMpv()
    window.video_frame = Frame()
    window.recents = []
    window.add_recent_file = window.recents.append
    for name in ("duration", "position"):
        setattr(window, name, 0)
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
    window.set_title = lambda: None
    window.play_button = type("_B", (), {"setIcon": lambda self, i: None})()
    window.pause_icon = object()
    window.is_paused = True

    monkeypatch.setattr(media_controls.QInputDialog, "getText",
                        staticmethod(lambda *a, **k: (SECRET_URL, True)))
    shown = []
    monkeypatch.setattr(media_controls, "show_user_error",
                        lambda *a, **k: shown.append(a))
    console = []
    monkeypatch.setattr(media_controls, "safe_console", console.append)

    media_controls.open_url(window)

    assert window.recents == [], "başarısız komut listeye girdi"
    assert window._url_loading_active is False
    joined = "\n".join(console) + "\n".join(str(item) for item in shown)
    for secret in SECRETS:
        assert secret not in joined, f"hata yolunda sır: {secret}"
    window.close()
    app.processEvents()
