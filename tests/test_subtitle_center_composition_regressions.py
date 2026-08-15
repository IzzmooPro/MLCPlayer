"""Altyazı Merkezi ÜRÜN ENTEGRASYONU regresyonları.

Bu tur özelliği kullanıcıya açar: "Alt Yazı > Altyazı Bul…" menüsü, tek
pencere sahipliği, controller composition'ı ve üzerine yazma onayı.

GÜVENLİK KURALLARI (testler)
----------------------------
- GERÇEK OpenSubtitles ağına ÇIKILMAZ: istemci enjekte edilir.
- Gerçek HKCU kullanılmaz: QSettings tmp_path altında INI'dir.
- Gerçek Credential Manager kullanılmaz: sahte kimlik deposu enjekte edilir.
- Kullanıcının medya dizinine yazılmaz: video ve hedef SRT tmp_path'tedir.
- Gerçek MPV yoktur: sahte `mpv_player` nesnesi kullanılır.
"""
import os
import threading
import time
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QEvent, QSettings, Qt
from PyQt6.QtWidgets import QApplication, QDialog, QMainWindow

from app import opensubtitles as osub
from app import subtitle_service as service
from app.subtitle_center import SubtitleCenterDialog
from app.subtitle_center_composition import (
    LOCAL_MEDIA_REQUIRED, SubtitleCenterCoordinator, open_subtitle_center,
    shutdown_subtitle_center)
from app.subtitle_settings import SubtitleSettingsStore

VIDEO_NAME = "Resident.Alien.S01E01.Pilot.1080p.AMZN.WEB-DL.DDP5.1.H.264-NTb.mkv"
TARGET_NAME = "Resident.Alien.S01E01.Pilot.1080p.AMZN.WEB-DL.DDP5.1.H.264-NTb.srt"
MOVIE_NAME = "Supergirl.2026.2160p.WEB-DL.H265.mkv"
GOOD_URL = "https://dl.opensubtitles.com/download/abc.srt"
SRT = b"1\n00:00:01,000 --> 00:00:04,000\nMerhaba dunya\n"
RESULT = {"file_id": 7135238, "name": "Uzak.Ad.turkish", "language": "Türkçe",
          "format": "srt", "moviehash_match": True, "downloads": 10,
          "ratings": 9.0, "hearing_impaired": False}
API_KEY = "APIKEYSUPERSECRET123"


# --- Sahteler ---

class FakeClient:
    """Ağ YOK. Hangi ayarlarla kurulduğunu kaydeder."""

    def __init__(self, api_key="", username="", password="", results=None):
        self.api_key = api_key
        self.username = username
        self.password = password
        self.results = results if results is not None else [RESULT]
        self.search_calls = []
        self.download_calls = []
        self.fetch_calls = []

    def search(self, **kwargs):
        # GERÇEK sözleşme: plan hash adımıyla başlayabilir
        # ({"moviehash", "moviebytesize", "languages"}) — `query` ZORUNLU
        # DEĞİLDİR. Zorunlu kılan sahte, hash yolunu hiç sınamıyordu.
        self.search_calls.append((kwargs.get("query"), kwargs.get("languages")))
        return list(self.results)

    def download_link(self, file_id):
        self.download_calls.append(file_id)
        return GOOD_URL

    def fetch(self, url):
        self.fetch_calls.append(url)
        return SRT


class FakeCredentialStore:
    def __init__(self, api_key="", password=""):
        self.secrets = {}
        if api_key:
            self.secrets["api"] = api_key
        if password:
            self.secrets["pw"] = password

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


class FakeMpv:
    def __init__(self):
        self.track_list = [{"type": "sub", "id": 1}]
        self.sid = "no"
        self.sub_visibility = False
        self.stopped = False
        self._next = 2

    def sub_add(self, path, *args):
        self.track_list.append({"type": "sub", "id": self._next,
                                "external-filename": path})
        self._next += 1

    def sub_remove(self, sid):
        self.track_list = [t for t in self.track_list if t.get("id") != sid]

    def stop(self):
        self.stopped = True


class StubVideoFrame:
    def __init__(self):
        self.osd_messages = []

    def show_osd(self, text, duration=1200):
        self.osd_messages.append(text)

    def _update_overlay_subtitle_state(self):
        pass


class StubPlayer(QMainWindow):
    """Gerçek pencere: dialog parent'lama ve aktivasyon ölçülebilsin."""

    def __init__(self, current_file=""):
        super().__init__()
        self.current_file = current_file
        self.video_frame = StubVideoFrame()
        self.mpv_player = FakeMpv()


class MenuPlayer(QMainWindow):
    """`setup_menu()` için minimum ama gerçek QMainWindow."""

    def __init__(self):
        super().__init__()
        self.__dict__["calls"] = []
        self.loop_file = False
        self.loop_playlist = False
        self.shuffle = False
        self.speed_actions = {}
        self.recent_files = []
        self.current_file = ""

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)

        def recorder(*args, **kwargs):
            self.__dict__["calls"].append(name)
        return recorder


@pytest.fixture
def bench(tmp_path):
    app = QApplication.instance() or QApplication([])
    created = []

    def factory(video=VIDEO_NAME, client=None, api_key=API_KEY,
                existing_target=None, make_file=True):
        if video and make_file:
            path = tmp_path / video
            # Hash 128 KiB ister; gerçekçi boyut.
            path.write_bytes(b"\0" * (140 * 1024))
            current = str(path)
        else:
            current = video or ""
        if existing_target is not None:
            (tmp_path / TARGET_NAME).write_bytes(existing_target)

        player = StubPlayer(current)
        settings = QSettings(str(tmp_path / "settings.ini"),
                             QSettings.Format.IniFormat)
        credentials = FakeCredentialStore(api_key=api_key)
        store = SubtitleSettingsStore(settings=settings,
                                      credentials=credentials)
        built = []

        def client_factory(**kwargs):
            made = client or FakeClient(**kwargs)
            for key, value in kwargs.items():
                setattr(made, key, value)
            built.append(made)
            return made

        coordinator = SubtitleCenterCoordinator(
            player, client_factory=client_factory, settings_store=store)
        created.append((player, coordinator))
        return SimpleNamespace(app=app, player=player, coordinator=coordinator,
                               store=store, credentials=credentials,
                               settings=settings, clients=built, tmp=tmp_path)

    yield factory

    for player, coordinator in created:
        coordinator.shutdown(wait_ms=4000)
        try:
            player.close()
            player.deleteLater()
        except RuntimeError:
            pass
    app.processEvents()


def pump_until(app, predicate, timeout_ms=6000):
    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.005)
    app.processEvents()
    return predicate()


# =====================================================================
# 1. Menü erişim noktası
# =====================================================================

def test_subtitle_menu_has_a_find_action():
    app = QApplication.instance() or QApplication([])
    from app.menu_actions import setup_menu

    window = MenuPlayer()
    setup_menu(window)
    menus = {action.text(): action.menu()
             for action in window.menuBar().actions() if action.menu()}

    assert "Alt Yazı" in menus
    labels = [a.text() for a in menus["Alt Yazı"].actions()]
    assert any("Altyazı Bul" in label for label in labels), labels
    window.close()
    window.deleteLater()
    app.processEvents()


def test_find_action_calls_the_product_entry_point():
    app = QApplication.instance() or QApplication([])
    from app.menu_actions import setup_menu

    window = MenuPlayer()
    setup_menu(window)
    action = next(a for menu in window.menuBar().actions() if menu.menu()
                  for a in menu.menu().actions() if "Altyazı Bul" in a.text())

    action.trigger()

    assert "open_subtitle_center" in window.calls
    window.close()
    window.deleteLater()
    app.processEvents()


def test_find_action_has_no_shortcut_conflict():
    app = QApplication.instance() or QApplication([])
    from app.menu_actions import setup_menu

    window = MenuPlayer()
    setup_menu(window)
    shortcuts = []
    for menu_action in window.menuBar().actions():
        menu = menu_action.menu()
        if menu is None:
            continue
        for action in menu.actions():
            text = action.shortcut().toString()
            if text:
                shortcuts.append(text)

    assert len(shortcuts) == len(set(shortcuts)), (
        f"cakisan kisayol: {sorted(shortcuts)}")
    window.close()
    window.deleteLater()
    app.processEvents()


def test_existing_subtitle_menu_order_is_preserved():
    app = QApplication.instance() or QApplication([])
    from app.menu_actions import setup_menu

    window = MenuPlayer()
    setup_menu(window)
    menu = next(a.menu() for a in window.menuBar().actions()
                if a.text() == "Alt Yazı")
    labels = [a.text() for a in menu.actions() if a.text()]

    for earlier, later in (("Altyazı Ekle", "Altyazıları Göster/Gizle"),
                           ("Altyazıları Göster/Gizle", "Altyazı Parçası"),
                           ("Altyazı Parçası", "Altyazı Ayarları")):
        assert labels.index(earlier) < labels.index(later), labels
    window.close()
    window.deleteLater()
    app.processEvents()


def test_player_exposes_the_entry_point():
    from app.player import MPVPlayer

    assert callable(getattr(MPVPlayer, "open_subtitle_center", None))


# =====================================================================
# 2. Ön koşullar: yerel video gerekir
# =====================================================================

@pytest.mark.parametrize("video", [
    "",
    "https://example.com/stream.mp4",
    "http://example.com/stream.mp4",
])
def test_non_local_media_never_opens_the_dialog(bench, video):
    env = bench(video=video, make_file=False)

    assert env.coordinator.open() is False
    assert env.coordinator.dialog is None
    assert env.player.video_frame.osd_messages == [LOCAL_MEDIA_REQUIRED]


def test_missing_file_is_not_local_media(bench, tmp_path):
    env = bench(video=str(tmp_path / "yok-boyle-bir-dosya.mkv"),
                make_file=False)

    assert env.coordinator.open() is False
    assert env.coordinator.dialog is None


def test_directory_is_not_local_media(bench, tmp_path):
    folder = tmp_path / "klasor"
    folder.mkdir()
    env = bench(video=str(folder), make_file=False)

    assert env.coordinator.open() is False


def test_rejected_media_makes_no_network_or_credential_access(bench,
                                                              monkeypatch):
    touched = {"hash": 0}
    monkeypatch.setattr(service, "opensubtitles_hash",
                        lambda path: touched.__setitem__("hash",
                                                         touched["hash"] + 1))
    env = bench(video="", make_file=False)

    env.coordinator.open()
    pump_until(env.app, lambda: True, 200)

    assert touched["hash"] == 0
    assert env.clients == [], "istemci kuruldu"


# =====================================================================
# 3. Yerel video ile açılış ve metadata
# =====================================================================

def test_local_video_opens_the_dialog(bench):
    env = bench()

    assert env.coordinator.open() is True
    dialog = env.coordinator.dialog
    assert isinstance(dialog, SubtitleCenterDialog)
    assert dialog.isVisible()
    assert env.player.video_frame.osd_messages == []


def test_dialog_media_comes_from_the_service_parser(bench):
    env = bench()
    env.coordinator.open()
    media = env.coordinator.dialog.media

    parsed = service.parse_release(env.player.current_file)
    assert media["file_name"] == env.player.current_file
    assert media["title"] == parsed["title"]
    assert media["season"] == parsed["season"] == 1
    assert media["episode"] == parsed["episode"] == 1
    assert media["is_series"] is True
    assert media["target_name"] == TARGET_NAME


def test_series_fields_are_visible_for_a_series(bench):
    env = bench()
    env.coordinator.open()
    dialog = env.coordinator.dialog

    assert dialog.season_field.isVisible()
    assert dialog.season_field.text() == "1"
    assert dialog.episode_field.text() == "1"


def test_series_fields_are_hidden_for_a_movie(bench):
    env = bench(video=MOVIE_NAME)
    env.coordinator.open()
    dialog = env.coordinator.dialog

    assert dialog.season_field.isVisible() is False
    assert dialog.episode_field.isVisible() is False
    assert dialog.media["is_series"] is False


def test_hash_is_not_computed_on_the_ui_thread(bench, monkeypatch):
    seen = {}
    original = service.opensubtitles_hash

    def spy(path):
        seen["thread"] = threading.get_ident()
        return original(path)

    monkeypatch.setattr(service, "opensubtitles_hash", spy)
    env = bench()
    main_thread = threading.get_ident()

    env.coordinator.open()
    pump_until(env.app, lambda: "thread" in seen, 4000)

    assert seen.get("thread") is not None, "hash hic hesaplanmadi"
    assert seen["thread"] != main_thread, "hash UI thread'inde hesaplandi"


def test_opening_the_dialog_does_not_stop_playback(bench):
    env = bench()

    env.coordinator.open()

    assert env.player.mpv_player.stopped is False


# =====================================================================
# 4. Tek pencere ve yaşam döngüsü
# =====================================================================

def test_second_open_reuses_the_same_dialog(bench):
    env = bench()
    env.coordinator.open()
    first = env.coordinator.dialog

    assert env.coordinator.open() is True

    assert env.coordinator.dialog is first
    dialogs = [w for w in env.app.topLevelWidgets()
               if isinstance(w, SubtitleCenterDialog)]
    assert len(dialogs) == 1, f"ikinci pencere uretildi: {len(dialogs)}"


def test_dialog_is_owned_by_the_player(bench):
    env = bench()
    env.coordinator.open()

    assert env.coordinator.dialog.parent() is env.player


def test_dialog_is_not_always_on_top(bench):
    env = bench()
    env.coordinator.open()

    flags = env.coordinator.dialog.windowFlags()
    assert not (flags & Qt.WindowType.WindowStaysOnTopHint)


def test_dialog_can_be_closed_and_reopened(bench):
    env = bench()
    env.coordinator.open()
    first = env.coordinator.dialog
    first.close()
    env.app.processEvents()
    pump_until(env.app, lambda: env.coordinator.dialog is None, 3000)

    assert env.coordinator.open() is True
    assert env.coordinator.dialog is not None
    dialogs = [w for w in env.app.topLevelWidgets()
               if isinstance(w, SubtitleCenterDialog) and w.isVisible()]
    assert len(dialogs) == 1


def test_reopen_does_not_double_connect_signals(bench):
    env = bench()
    client = FakeClient(api_key=API_KEY)
    env.coordinator.client_factory = lambda **kwargs: client

    env.coordinator.open()
    env.coordinator.dialog.close()
    pump_until(env.app, lambda: env.coordinator.dialog is None, 3000)
    env.coordinator.open()
    dialog = env.coordinator.dialog
    dialog.search_button.click()
    pump_until(env.app, lambda: env.coordinator.is_idle(), 5000)

    assert len(client.search_calls) <= 1, (
        f"arama {len(client.search_calls)} kez tetiklendi (cift baglanti)")


def test_player_shutdown_cancels_running_work(bench):
    env = bench()
    env.coordinator.open()
    env.coordinator.shutdown(wait_ms=4000)

    assert env.coordinator.dialog is None
    assert env.coordinator.is_idle() is True


def test_shutdown_helper_is_safe_without_a_coordinator():
    player = SimpleNamespace()

    shutdown_subtitle_center(player)  # hata vermemeli


# =====================================================================
# 5. Kimlik bilgisi eksikken ağ yok
# =====================================================================

def test_missing_api_key_opens_the_settings_window_without_network(bench):
    client = FakeClient()
    env = bench(api_key="", client=client)

    assert env.coordinator.open() is True
    dialog = env.coordinator.dialog

    # Ayarlar ARTIK ayrı pencerede açılır (eski çekmece kaldırıldı).
    assert env.coordinator.settings_dialog is not None
    assert env.coordinator.settings_dialog.isVisible() is True
    assert dialog.status_text().strip() != ""
    assert client.search_calls == []
    assert client.download_calls == []


def test_missing_api_key_message_is_safe(bench):
    env = bench(api_key="")
    env.coordinator.open()

    status = env.coordinator.dialog.status_text()
    assert "Traceback" not in status
    assert API_KEY not in status


def test_present_api_key_does_not_force_the_settings_window_open(bench):
    env = bench()

    env.coordinator.open()

    assert env.coordinator.settings_dialog is None


# =====================================================================
# 6. Ayar kaydı sonrası yeni istemci
# =====================================================================

def test_saved_settings_are_used_by_the_next_search(bench):
    env = bench(api_key="")
    env.coordinator.open()
    center = env.coordinator.dialog
    env.coordinator.open_settings()
    dialog = env.coordinator.settings_dialog

    dialog.api_key_field.setText("YENIANAHTAR")
    dialog.username_field.setText("kullanici")
    dialog.password_field.setText("P4rola!")
    dialog.settings_save_button.click()
    env.app.processEvents()
    center.search_button.click()
    pump_until(env.app, lambda: env.coordinator.is_idle(), 5000)

    assert env.clients, "hic istemci kurulmadi"
    assert env.clients[-1].api_key == "YENIANAHTAR", (
        "arama eski istemci ayarlariyla yapildi")


def test_stale_client_is_not_cached_after_a_settings_change(bench):
    env = bench(api_key="ESKIANAHTAR")
    env.coordinator.open()
    env.coordinator.open_settings()
    dialog = env.coordinator.settings_dialog
    before = env.coordinator.client()

    dialog.api_key_field.setText("YENIANAHTAR")
    dialog.settings_save_button.click()
    env.app.processEvents()

    after = env.coordinator.client()
    assert after is not before
    assert after.api_key == "YENIANAHTAR"


# =====================================================================
# 7. Controller bağlantıları
# =====================================================================

def test_search_button_reaches_the_client(bench):
    client = FakeClient(api_key=API_KEY)
    env = bench(client=client)
    env.coordinator.open()

    env.coordinator.dialog.search_button.click()
    pump_until(env.app, lambda: env.coordinator.is_idle(), 5000)

    assert client.search_calls, "arama istemciye ulasmadi"


def test_search_results_reach_the_dialog(bench):
    """Uçtan uca: istemci yanıtı çekirdek filtresinden geçip karta dönüşür.

    NOT: çekirdek `filter_results` DİL KODUNA göre eler; sahte istemci de
    gerçek API gibi kod döndürmelidir.
    """
    client = FakeClient(api_key=API_KEY, results=[dict(RESULT, language="tr")])
    env = bench(client=client)
    env.coordinator.open()

    env.coordinator.dialog.search_button.click()
    pump_until(env.app,
               lambda: bool(env.coordinator.dialog.result_cards()), 6000)

    assert env.coordinator.dialog.result_cards(), (
        f"sonuc karta donusmedi: {env.coordinator.dialog.status_text()!r}")


def test_closed_dialog_is_destroyed_and_does_not_accumulate(bench):
    """Kapatılan pencere YOK EDİLMELİ; her açılışta bir kabuk birikmemeli."""
    env = bench()

    for _ in range(3):
        env.coordinator.open()
        env.coordinator.dialog.close()
        pump_until(env.app, lambda: env.coordinator.dialog is None, 4000)
        pump_until(env.app, lambda: True, 150)

    alive = [w for w in env.app.topLevelWidgets()
             if isinstance(w, SubtitleCenterDialog)]
    assert alive == [], f"kapatilan dialog(lar) yok edilmedi: {len(alive)}"


def test_selection_enables_the_single_download_action(bench):
    """Tek eylem düğmesi yalnız seçim varken etkinleşir.

    ESKİ AD: `test_selection_enables_the_download_buttons`. "Yalnızca
    İndir" düğmesi kaldırıldığı için çoğul sözleşme geçersiz.
    """
    env = bench()
    env.coordinator.open()
    dialog = env.coordinator.dialog
    dialog.show_results([RESULT])

    assert dialog.apply_button.isEnabled() is False
    dialog.select_result(dialog.result_cards()[0])

    assert dialog.apply_button.isEnabled() is True
    assert not hasattr(dialog, "download_button")


def test_download_and_apply_reaches_mpv(bench):
    client = FakeClient(api_key=API_KEY)
    env = bench(client=client)
    env.coordinator.open()
    dialog = env.coordinator.dialog
    dialog.show_results([RESULT])
    dialog.select_result(dialog.result_cards()[0])

    dialog.apply_button.click()
    pump_until(env.app, lambda: env.coordinator.is_idle(), 6000)

    assert (env.tmp / TARGET_NAME).exists()
    assert env.player.mpv_player.sid != "no"
    assert env.player.mpv_player.sub_visibility is True


@pytest.mark.parametrize("preference", ["apply", "download_only"])
def test_legacy_after_download_setting_cannot_change_the_flow(bench,
                                                              preference):
    """Eski `after_download` değeri kayıtlı olsa da akış DEĞİŞMEZ.

    ESKİ ADLAR: `test_explicit_buttons_ignore_the_after_download_preference`
    ve `test_explicit_apply_button_ignores_the_preference`. İki düğme
    yerine tek akış olduğu için sözleşme "tercih indirmeyi de uygulamayı
    da etkilemez" biçimine indi.
    """
    client = FakeClient(api_key=API_KEY)
    env = bench(client=client)
    env.store.save({"after_download": preference})
    env.coordinator.open()
    dialog = env.coordinator.dialog
    dialog.show_results([RESULT])
    dialog.select_result(dialog.result_cards()[0])

    dialog.apply_button.click()
    pump_until(env.app, lambda: env.coordinator.is_idle(), 6000)

    assert env.player.mpv_player.sid != "no", (
        f"tercih ({preference}) explicit uygula dugmesini ezdi")


# =====================================================================
# 8. Üzerine yazma (ONAY SORULMAZ)
# =====================================================================
#
# ESKİ SÖZLEŞME KALDIRILDI: `test_overwrite_is_asked_only_when_the_target_exists`
# ve `test_declined_overwrite_has_no_side_effects` kullanıcıya sorulan bir
# onayı ölçüyordu. Hedef videodan tek anlamlı türediği için soru artık
# yoktur; korunan garanti "mevcut dosya YALNIZ doğrulanmış içerikle,
# atomik olarak değişir"dir ve aşağıda ölçülür.

def test_overwrite_happens_without_any_confirmation(bench):
    client = FakeClient(api_key=API_KEY)
    env = bench(client=client, existing_target=b"ESKI")
    env.coordinator.open()
    dialog = env.coordinator.dialog
    dialog.show_results([RESULT])
    dialog.select_result(dialog.result_cards()[0])

    dialog.apply_button.click()
    pump_until(env.app, lambda: env.coordinator.is_idle(), 6000)

    assert (env.tmp / TARGET_NAME).read_bytes() == SRT
    assert env.player.mpv_player.sid != "no"
    leftovers = [p.name for p in env.tmp.iterdir()
                 if p.name.startswith(".mlc-sub-")]
    assert leftovers == []


def module_code_without_docs(module):
    """Modülün YALNIZCA çalıştırılabilir kodu (yorum ve docstring hariç).

    Ham kaynakta arama yapmak, kuralın kendisini anlatan yorumlara takılıyor.
    Ölçülmesi gereken şey koddur.
    """
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(module))
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list) or not body:
            continue
        first = body[0]
        if (isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            del body[0]
    return ast.unparse(tree)


def test_no_confirmation_dialog_remains_in_the_composition():
    """Onay penceresi tamamen kaldırıldı.

    ESKİ AD: `test_default_confirmation_is_a_themed_dialog`. Kural
    "onay kutusu ürünün temasında olsun"dan "onay kutusu HİÇ olmasın"a
    döndü; sistem `QMessageBox` yasağı aynen sürüyor.
    """
    from app import subtitle_center_composition as composition

    code = module_code_without_docs(composition)
    assert "QMessageBox" not in code, "sistem kutusu tasarimla sirisiyor"
    assert "OverwriteConfirmDialog" not in code
    assert "confirm_overwrite" not in code


# =====================================================================
# 9. Katman/güvenlik disiplini
# =====================================================================

def test_composition_does_not_reintroduce_the_classic_shell():
    from app import subtitle_center_composition as composition

    code = module_code_without_docs(composition)
    for forbidden in ("MLCPLAYER_CLASSIC_UI", "MLCPLAYER_OVERLAY_PREVIEW",
                      "WindowStaysOnTopHint"):
        assert forbidden not in code, forbidden


def test_composition_has_no_global_singleton():
    from app import subtitle_center_composition as composition

    assert not hasattr(composition, "COORDINATOR")
    assert not hasattr(composition, "_INSTANCE")


def test_entry_point_creates_one_coordinator_per_player(bench):
    env = bench()
    player = env.player

    first = open_subtitle_center(player)
    second = open_subtitle_center(player)

    assert first is True and second is True
    coordinator = player._subtitle_center
    assert isinstance(coordinator, SubtitleCenterCoordinator)
    coordinator.shutdown(wait_ms=2000)
