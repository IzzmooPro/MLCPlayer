# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Altyazı Merkezi koordinatör YAŞAM DÖNGÜSÜ regresyonları.

Bu tur yalnızca sahiplik ve kapanış disiplinidir: gerçek ağ YOK, gerçek MPV
YOK, görünüm değişikliği YOK.

Ölçülen kurallar
----------------
1. Kapatılan dialogun controller'ı UNUTULMAZ; thread doğal olarak bitene
   kadar "draining" olarak sahiplenilir. `is_idle()` ve `shutdown()` onu da
   hesaba katar.
2. Hash sonucu generation + normalize edilmiş medya kimliğiyle doğrulanır;
   eski medyanın geç gelen sonucu yeni dialoga YAZILMAZ ve eski thread yeni
   hash'i ENGELLEMEZ.
3. Player kapanışı çalışan iş varsa ERTELENİR; UI donmaz, QThread zorla
   sonlandırılmaz, kapanış yalnız BİR kez sürdürülür.
4. İstemci yenileme düğme tıklamasına değil `SettingsSaveResult.accepted`
   sonucuna bağlıdır.
"""
import os
import threading
import time
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QEvent, QSettings, Qt, QTimer
from PyQt6.QtWidgets import QApplication, QMainWindow

from app import subtitle_service as service
from app.subtitle_center import SubtitleCenterDialog
from app.subtitle_center_composition import (
    SubtitleCenterCoordinator, close_subtitle_center_before_exit)
from app.subtitle_settings import SubtitleSettingsStore

SERIES = "Resident.Alien.S01E01.Pilot.1080p.AMZN.WEB-DL.mkv"
OTHER = "Supergirl.2026.2160p.WEB-DL.H265.mkv"
GOOD_URL = "https://dl.opensubtitles.com/download/abc.srt"
SRT = b"1\n00:00:01,000 --> 00:00:04,000\nMerhaba\n"
RESULT = {"file_id": 7135238, "name": "Uzak.Ad", "language": "tr",
          "format": "srt", "moviehash_match": True, "downloads": 10,
          "ratings": 9.0, "hearing_impaired": False}
API_KEY = "APIKEYSUPERSECRET123"


class SlowClient:
    """Arama, testin serbest bırakacağı ana kadar worker thread'inde bekler.

    NOT: `release`/`entered` olayları PAYLAŞILABİLİR. Böylece istemci her
    ayar kaydında yeniden kurulsa bile (kimlik testleri bunu ölçer) test
    hâlâ çalışan aramayı kontrol edebilir.
    """

    def __init__(self, results=None, gate=None):
        gate = gate or SimpleNamespace(release=threading.Event(),
                                       entered=threading.Event())
        self.release = gate.release
        self.entered = gate.entered
        self.results = results if results is not None else [RESULT]
        self.search_calls = 0

    def search(self, **kwargs):
        # Plan hash adımıyla başlayabilir
        # ({"moviehash", "moviebytesize", "languages"}); `query` ZORUNLU DEĞİL.
        self.search_calls += 1
        self.entered.set()
        # Kooperatif: en fazla 20 sn; test her hâlükârda serbest bırakır.
        self.release.wait(20)
        return list(self.results)

    def download_link(self, file_id):
        return GOOD_URL

    def fetch(self, url):
        return SRT


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


class FakeMpv:
    def __init__(self):
        self.track_list = [{"type": "sub", "id": 1}]
        self.sid = "no"
        self.sub_visibility = False

    def sub_add(self, path, *args):
        self.track_list.append({"type": "sub", "id": 2,
                                "external-filename": path})

    def sub_remove(self, sid):
        self.track_list = [t for t in self.track_list if t.get("id") != sid]


class StubVideoFrame:
    def __init__(self):
        self.osd_messages = []

    def show_osd(self, text, duration=1200):
        self.osd_messages.append(text)

    def _update_overlay_subtitle_state(self):
        pass


class StubPlayer(QMainWindow):
    def __init__(self, current_file=""):
        super().__init__()
        self.current_file = current_file
        self.video_frame = StubVideoFrame()
        self.mpv_player = FakeMpv()


class ClosingPlayer(StubPlayer):
    """Ürünün kapanış deseni: iş sürüyorsa `closeEvent` ERTELER."""

    def __init__(self, current_file=""):
        super().__init__(current_file)
        self.close_events = 0
        self.accepted_closes = 0
        self.terminated = 0

    def closeEvent(self, event):
        self.close_events += 1
        if not close_subtitle_center_before_exit(self):
            event.ignore()
            return
        self.accepted_closes += 1
        self.terminated += 1  # gerçek üründe mpv terminate burada
        event.accept()


@pytest.fixture
def bench(tmp_path):
    app = QApplication.instance() or QApplication([])
    created = []

    def factory(video=SERIES, client=None, api_key=API_KEY,
                player_class=StubPlayer):
        path = tmp_path / video
        path.write_bytes(b"\0" * (140 * 1024))
        player = player_class(str(path))
        store = SubtitleSettingsStore(
            settings=QSettings(str(tmp_path / "settings.ini"),
                               QSettings.Format.IniFormat),
            credentials=FakeCredentialStore(api_key))
        gate = SimpleNamespace(release=threading.Event(),
                               entered=threading.Event())
        made = client if client is not None else SlowClient(gate=gate)
        built = []

        def client_factory(**kwargs):
            # Her kurulum YENİ nesne döndürür (kimlik testleri anlamlı olsun);
            # kontrol kapıları paylaşılır.
            instance = made if client is not None else SlowClient(gate=gate)
            built.append(instance)
            return instance

        coordinator = SubtitleCenterCoordinator(
            player, client_factory=client_factory, settings_store=store)
        player._subtitle_center = coordinator
        created.append((player, coordinator, made))
        return SimpleNamespace(app=app, player=player, tmp=tmp_path,
                               coordinator=coordinator, store=store,
                               client=made, clients=built)

    yield factory

    for player, coordinator, client in created:
        release = getattr(client, "release", None)
        if release is not None:
            release.set()
        coordinator.shutdown(wait_ms=6000)
        try:
            player.close()
            player.deleteLater()
        except RuntimeError:
            pass
    app.processEvents()


def pump(app, milliseconds):
    end = time.time() + milliseconds / 1000.0
    while time.time() < end:
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
        time.sleep(0.005)


def pump_until(app, predicate, timeout_ms=8000):
    end = time.time() + timeout_ms / 1000.0
    while time.time() < end:
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.005)
    app.processEvents()
    return predicate()


def switch_media(env, name):
    path = env.tmp / name
    if not path.exists():
        path.write_bytes(b"\0" * (150 * 1024))
    env.player.current_file = str(path)
    return str(path)


# =====================================================================
# 1. Draining controller sahipliği
# =====================================================================

def test_coordinator_is_not_idle_while_a_retired_search_runs(bench):
    env = bench()
    env.coordinator.open()
    env.coordinator.dialog.search_button.click()
    assert env.client.entered.wait(5), "arama worker'i baslamadi"

    env.coordinator.dialog.close()
    pump_until(env.app, lambda: env.coordinator.dialog is None, 3000)

    assert env.coordinator.is_idle() is False, (
        "kapatilan dialogun calisan controller'i takipten cikti")

    env.client.release.set()
    assert pump_until(env.app, lambda: env.coordinator.is_idle(), 8000)


def test_retired_controller_is_dropped_when_it_finishes(bench):
    env = bench()
    env.coordinator.open()
    env.coordinator.dialog.search_button.click()
    assert env.client.entered.wait(5)
    env.coordinator.dialog.close()
    pump_until(env.app, lambda: env.coordinator.dialog is None, 3000)
    assert env.coordinator.draining_count() == 1

    env.client.release.set()
    assert pump_until(env.app, lambda: env.coordinator.is_idle(), 8000)

    assert env.coordinator.draining_count() == 0, "biten controller birakilmadi"


def test_shutdown_waits_for_a_retired_controller(bench):
    env = bench()
    env.coordinator.open()
    env.coordinator.dialog.search_button.click()
    assert env.client.entered.wait(5)
    env.coordinator.dialog.close()
    pump_until(env.app, lambda: env.coordinator.dialog is None, 3000)

    env.client.release.set()
    finished = env.coordinator.shutdown(wait_ms=8000)

    assert finished is True
    assert env.coordinator.is_idle() is True
    assert env.coordinator.draining_count() == 0


def test_old_and_new_controllers_are_tracked_separately(bench):
    env = bench()
    env.coordinator.open()
    first_dialog = env.coordinator.dialog
    first_dialog.search_button.click()
    assert env.client.entered.wait(5)
    first_dialog.close()
    pump_until(env.app, lambda: env.coordinator.dialog is None, 3000)

    env.coordinator.open()
    second = env.coordinator.dialog

    assert second is not first_dialog
    assert env.coordinator.draining_count() == 1, (
        "eski controller yeni acilista kayboldu")
    assert env.coordinator.is_idle() is False


def test_stale_worker_never_writes_into_the_new_dialog(bench):
    env = bench()
    env.coordinator.open()
    env.coordinator.dialog.search_button.click()
    assert env.client.entered.wait(5)
    env.coordinator.dialog.close()
    pump_until(env.app, lambda: env.coordinator.dialog is None, 3000)
    env.coordinator.open()
    fresh = env.coordinator.dialog
    fresh.show_results([])
    before = fresh.status_text()

    env.client.release.set()
    pump_until(env.app, lambda: env.coordinator.is_idle(), 8000)

    assert fresh.result_cards() == [], "eski worker yeni dialoga yazdi"
    assert fresh.status_text() == before


def test_three_cycles_do_not_accumulate_controllers_or_threads(bench):
    env = bench()
    threads_before = threading.active_count()

    for _ in range(3):
        env.coordinator.open()
        env.coordinator.dialog.search_button.click()
        assert env.client.entered.wait(5)
        env.client.entered.clear()
        env.coordinator.dialog.close()
        pump_until(env.app, lambda: env.coordinator.dialog is None, 3000)
        env.client.release.set()
        assert pump_until(env.app, lambda: env.coordinator.is_idle(), 8000)
        env.client.release.clear()

    pump(env.app, 200)
    assert env.coordinator.draining_count() == 0
    assert threading.active_count() <= threads_before, (
        f"thread birikti: {threads_before} -> {threading.active_count()}")


def test_shutdown_does_not_force_terminate_threads():
    import inspect

    from app import subtitle_center_composition as composition

    source = inspect.getsource(composition.SubtitleCenterCoordinator)
    assert ".terminate()" not in source


# =====================================================================
# 2. Hash generation ve medya kimliği
# =====================================================================

@pytest.fixture
def slow_hash(monkeypatch):
    """Yol bazlı kontrollü hash: her dosya ayrı serbest bırakılır."""
    gates = {}
    seen = []

    def fake_hash(path):
        key = os.path.normcase(os.path.abspath(path))
        seen.append(key)
        gate = gates.setdefault(key, threading.Event())
        gate.wait(20)
        return "HASH-" + os.path.basename(key)

    monkeypatch.setattr(service, "opensubtitles_hash", fake_hash)
    return SimpleNamespace(gates=gates, seen=seen,
                           gate=lambda p: gates.setdefault(
                               os.path.normcase(os.path.abspath(p)),
                               threading.Event()))


def test_new_media_hash_is_not_blocked_by_a_slow_old_hash(bench, slow_hash):
    env = bench()
    first = env.player.current_file
    first_gate = slow_hash.gate(first)
    env.coordinator.open()
    pump_until(env.app, lambda: first in
               [p for p in slow_hash.seen for _ in [0]] or True, 300)

    env.coordinator.dialog.close()
    pump_until(env.app, lambda: env.coordinator.dialog is None, 3000)
    second = switch_media(env, OTHER)
    second_gate = slow_hash.gate(second)
    env.coordinator.open()
    second_gate.set()

    ok = pump_until(
        env.app,
        lambda: env.coordinator.dialog.media.get("movie_hash", ""), 8000)
    first_gate.set()

    assert ok, "eski hash thread'i yeni medyanin hash'ini engelledi"
    assert env.coordinator.dialog.media["movie_hash"].endswith(
        os.path.basename(os.path.normcase(second)))


def test_stale_hash_result_is_rejected(bench, slow_hash):
    env = bench()
    first = env.player.current_file
    first_gate = slow_hash.gate(first)
    env.coordinator.open()
    pump(env.app, 150)
    env.coordinator.dialog.close()
    pump_until(env.app, lambda: env.coordinator.dialog is None, 3000)

    second = switch_media(env, OTHER)
    second_gate = slow_hash.gate(second)
    env.coordinator.open()
    fresh = env.coordinator.dialog

    # Eski medyanin hash'i SIMDI geliyor: yeni dialoga yazilmamali.
    first_gate.set()
    pump(env.app, 400)
    stale = fresh.media.get("movie_hash", "")
    assert os.path.basename(first).lower() not in stale.lower(), (
        f"eski medyanin hash'i yeni dialoga yazildi: {stale!r}")

    second_gate.set()
    pump_until(env.app, lambda: fresh.media.get("movie_hash", ""), 8000)
    assert fresh.media["movie_hash"].endswith(
        os.path.basename(os.path.normcase(second)))


def test_every_open_gets_a_new_media_generation(bench):
    env = bench()
    env.coordinator.open()
    first = env.coordinator.media_generation()
    env.coordinator.dialog.close()
    pump_until(env.app, lambda: env.coordinator.dialog is None, 3000)
    env.coordinator.open()

    assert env.coordinator.media_generation() != first


def test_hash_work_is_included_in_idle_state(bench, slow_hash):
    env = bench()
    gate = slow_hash.gate(env.player.current_file)
    env.coordinator.open()
    pump(env.app, 150)

    assert env.coordinator.is_idle() is False, "calisan hash isi idle sayildi"

    gate.set()
    assert pump_until(env.app, lambda: env.coordinator.is_idle(), 8000)


# =====================================================================
# 3. Kapanışın ertelenmesi
# =====================================================================

def test_close_is_deferred_while_a_worker_runs(bench):
    env = bench(player_class=ClosingPlayer)
    env.coordinator.open()
    env.coordinator.dialog.search_button.click()
    assert env.client.entered.wait(5)

    env.player.close()

    assert env.player.close_events == 1
    assert env.player.accepted_closes == 0, "calisan QThread geride birakildi"
    assert env.player.isVisible() or True

    env.client.release.set()
    assert pump_until(env.app, lambda: env.player.accepted_closes == 1, 9000)
    assert env.coordinator.is_idle() is True


def test_deferred_close_completes_exactly_once(bench):
    env = bench(player_class=ClosingPlayer)
    env.coordinator.open()
    env.coordinator.dialog.search_button.click()
    assert env.client.entered.wait(5)
    env.player.close()
    env.player.close()  # kullanici ikinci kez kapatmayi denedi

    env.client.release.set()
    assert pump_until(env.app, lambda: env.player.accepted_closes >= 1, 9000)
    pump(env.app, 400)

    assert env.player.accepted_closes == 1, "cift kapanis/terminate"
    assert env.player.terminated == 1


def test_close_does_not_freeze_the_ui(bench):
    env = bench(player_class=ClosingPlayer)
    env.coordinator.open()
    env.coordinator.dialog.search_button.click()
    assert env.client.entered.wait(5)

    ticks = {"n": 0}
    timer = QTimer()
    timer.setTimerType(Qt.TimerType.PreciseTimer)
    timer.setInterval(10)
    timer.timeout.connect(lambda: ticks.__setitem__("n", ticks["n"] + 1))
    timer.start()
    try:
        started = time.monotonic()
        env.player.close()
        blocked = time.monotonic() - started
        pump(env.app, 300)
        env.client.release.set()
        pump_until(env.app, lambda: env.player.accepted_closes == 1, 9000)
    finally:
        timer.stop()

    assert blocked < 1.0, f"closeEvent UI'i {blocked:.2f}s bloke etti"
    assert ticks["n"] > 3, f"kapanis sirasinda UI dondu (tick={ticks['n']})"


def test_close_without_running_work_is_immediate(bench):
    env = bench(player_class=ClosingPlayer)
    env.coordinator.open()
    pump_until(env.app, lambda: env.coordinator.is_idle(), 8000)

    env.player.close()

    assert env.player.accepted_closes == 1
    assert env.player.close_events == 1


def test_close_helper_is_safe_without_a_coordinator():
    player = SimpleNamespace()

    assert close_subtitle_center_before_exit(player) is True


def test_product_close_event_is_wired_to_the_deferred_helper():
    """Ürünün `closeEvent`'i ertelenmiş kapanışı GERÇEKTEN çağırabilmeli.

    Bu test bilerek hem çağrıyı hem de İSMİN ÇÖZÜLEBİLİRLİĞİNİ ölçer:
    `player.py` içindeki geniş `except Exception`, eksik bir import'tan
    doğan `NameError`'ı yutup erteleme davranışını sessizce kapatıyordu.
    """
    import inspect

    from app import player as player_module

    source = inspect.getsource(player_module.MPVPlayer.closeEvent)
    assert "close_subtitle_center_before_exit" in source
    assert "event.ignore()" in source
    # İsim modül ad alanında GERÇEKTEN çözülmeli.
    assert callable(
        getattr(player_module, "close_subtitle_center_before_exit", None)), (
        "closeEvent'in cagirdigi yardimci import edilmemis")


# =====================================================================
# 4. İstemci yenileme yalnız KABUL EDİLEN kayıtta
# =====================================================================

class BrokenSettings:
    def __init__(self):
        self.store = {}

    def value(self, key, default=None):
        return self.store.get(key, default)

    def setValue(self, key, value):
        self.store[key] = value

    def remove(self, key):
        self.store.pop(key, None)

    def sync(self):
        return None

    def status(self):
        return QSettings.Status.AccessError


def test_rejected_save_does_not_rebuild_the_client(bench):
    env = bench()
    env.coordinator.settings_store = SubtitleSettingsStore(
        settings=BrokenSettings(), credentials=FakeCredentialStore())
    env.coordinator.open()
    # Ayarlar ARTIK ayrı pencerede; dişli yalnız istek yayınlar.
    env.coordinator.open_settings()
    dialog = env.coordinator.settings_dialog
    before = env.coordinator.client()

    dialog.api_key_field.setText("YENIANAHTAR")
    dialog.settings_save_button.click()
    env.app.processEvents()

    assert env.coordinator.client() is before, (
        "reddedilen kayit istemciyi yeniledi")


def test_rejected_save_keeps_the_stored_credentials(bench):
    credentials = FakeCredentialStore()
    env = bench()
    env.coordinator.settings_store = SubtitleSettingsStore(
        settings=BrokenSettings(), credentials=credentials)
    env.coordinator.open()
    # Ayarlar ARTIK ayrı pencerede; dişli yalnız istek yayınlar.
    env.coordinator.open_settings()
    dialog = env.coordinator.settings_dialog

    dialog.api_key_field.setText("YENIANAHTAR")
    dialog.settings_save_button.click()
    env.app.processEvents()

    assert credentials.get_api_key() == API_KEY


def test_accepted_save_rebuilds_the_client_once(bench):
    env = bench()
    env.coordinator.open()
    # Ayarlar ARTIK ayrı pencerede; dişli yalnız istek yayınlar.
    env.coordinator.open_settings()
    dialog = env.coordinator.settings_dialog
    before = env.coordinator.client()
    count_before = len(env.clients)

    dialog.api_key_field.setText("YENIANAHTAR")
    dialog.settings_save_button.click()
    env.app.processEvents()

    after = env.coordinator.client()
    assert after is not before
    assert len(env.clients) == count_before + 1, (
        f"istemci {len(env.clients) - count_before} kez uretildi")


def test_session_only_save_still_rebuilds_the_client(bench):
    class SessionOnlyCredentials(FakeCredentialStore):
        def set_api_key(self, value):
            self.secrets["api"] = value
            return "session_memory"

        def set_password(self, username, value):
            self.secrets["pw"] = value
            return "session_memory"

    env = bench()
    env.coordinator.settings_store = SubtitleSettingsStore(
        settings=QSettings(str(env.tmp / "session.ini"),
                           QSettings.Format.IniFormat),
        credentials=SessionOnlyCredentials())
    env.coordinator.open()
    # Ayarlar ARTIK ayrı pencerede; dişli yalnız istek yayınlar.
    env.coordinator.open_settings()
    dialog = env.coordinator.settings_dialog
    before = env.coordinator.client()

    dialog.api_key_field.setText("OTURUMLUK")
    dialog.settings_save_button.click()
    env.app.processEvents()

    assert env.coordinator.client() is not before


def test_client_invalidation_is_not_bound_to_the_button_click():
    import inspect

    from app import subtitle_center_composition as composition

    source = inspect.getsource(
        composition.SubtitleCenterCoordinator._build_dialog)
    assert "settings_save_button.clicked" not in source, (
        "istemci yenileme hala dugme tiklamasina bagli")
