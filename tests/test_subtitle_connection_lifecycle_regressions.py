# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Bağlantı testi YAŞAM DÖNGÜSÜ ve KAYITLI PAROLA regresyonları.

İki dar açık:

1. Ayar penceresi kapanırken `_drain_connection_tester()` UI thread'inde
   `shutdown(wait_ms=3000)` çağırıyordu: kapanış üç saniyeye kadar donabilir
   ve bu sırada coordinator tester'ı takipten çıkarıyordu.
2. `start_test()` "kullanıcı adı dolu + parola alanı boş" durumunu koşulsuz
   eksik hesap sayıyordu. Parola forma geri doldurulmadığı için (doğru
   güvenlik kararı) kayıtlı parolası olan kullanıcı bağlantıyı hiç test
   edemiyordu.

GERÇEK AĞA ÇIKILMAZ; gerçek HKCU/Credential Manager kullanılmaz.
"""
import os
import threading
import time
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QEvent, QSettings, Qt, QTimer
from PyQt6.QtWidgets import QApplication, QMainWindow

from app.subtitle_center_composition import SubtitleCenterCoordinator
from app.subtitle_center_settings_dialog import SubtitleCenterSettingsDialog
from app.subtitle_connection_test_controller import (
    STATUS_OK, STATUS_PARTIAL_ACCOUNT, SubtitleConnectionTestController)
from app.subtitle_settings import SubtitleSettingsStore

VIDEO = "Resident.Alien.S01E01.Pilot.1080p.AMZN.WEB-DL.mkv"
API_KEY = "APIKEYSUPERSECRET123"
STORED_PASSWORD = "KayitliP4rola!"
FORM_PASSWORD = "FormdakiYeniP4rola!"
USER = "MuratPH"


class FakeCredentialStore:
    def __init__(self, api_key=API_KEY, password=None, username=None):
        self.secrets = {}
        if api_key:
            self.secrets["api"] = api_key
        if password and username:
            self.secrets[f"pw/{username}"] = password
        self.reads = []

    def set_api_key(self, value):
        self.secrets["api"] = value
        return "credential_manager"

    def get_api_key(self):
        return self.secrets.get("api")

    def delete_api_key(self):
        self.secrets.pop("api", None)
        return True

    def set_password(self, username, value):
        self.secrets[f"pw/{username}"] = value
        return "credential_manager"

    def get_password(self, username):
        self.reads.append(username)
        return self.secrets.get(f"pw/{username}")

    def delete_password(self, username):
        self.secrets.pop(f"pw/{username}", None)
        return True


class SlowClient:
    """`login`/`search` testin serbest bırakacağı ana kadar bekler."""

    def __init__(self, gate=None, **kwargs):
        self.gate = gate
        self.kwargs = dict(kwargs)
        self.login_calls = 0
        self.search_calls = 0
        self.download_calls = 0

    def _wait(self):
        if self.gate is not None:
            self.gate.wait(20)

    def login(self):
        self.login_calls += 1
        self._wait()
        return True

    def has_token(self):
        return True

    def search(self, **kwargs):
        self.search_calls += 1
        self._wait()
        return []

    def download_link(self, file_id):
        self.download_calls += 1
        raise AssertionError("baglanti testi kota tuketmemeli")

    def fetch(self, url):
        raise AssertionError("baglanti testi indirme yapmamali")


class StubVideoFrame:
    def __init__(self):
        self.osd_messages = []
        self.suppressed = False

    def set_overlay_suppressed(self, suppressed):
        self.suppressed = bool(suppressed)

    def show_osd(self, text, duration=1200):
        self.osd_messages.append(text)

    def _update_overlay_subtitle_state(self):
        pass


class StubPlayer(QMainWindow):
    def __init__(self, current_file):
        super().__init__()
        self.current_file = current_file
        self.video_frame = StubVideoFrame()
        self.mpv_player = SimpleNamespace(
            track_list=[], sid="no", sub_visibility=False,
            sub_add=lambda p, *a: None, sub_remove=lambda s: None)


class ClosingPlayer(StubPlayer):
    def __init__(self, current_file):
        super().__init__(current_file)
        self.accepted_closes = 0
        self.terminated = 0

    def closeEvent(self, event):
        from app.subtitle_center_composition import (
            close_subtitle_center_before_exit)

        if not close_subtitle_center_before_exit(self):
            event.ignore()
            return
        self.accepted_closes += 1
        self.terminated += 1
        event.accept()


@pytest.fixture
def bench(tmp_path):
    app = QApplication.instance() or QApplication([])
    created = []

    def factory(stored_username="", stored_password=None,
                player_class=StubPlayer, gate=None):
        path = tmp_path / VIDEO
        path.write_bytes(b"\0" * (140 * 1024))
        player = player_class(str(path))
        credentials = FakeCredentialStore(password=stored_password,
                                          username=stored_username)
        settings = QSettings(str(tmp_path / "settings.ini"),
                             QSettings.Format.IniFormat)
        store = SubtitleSettingsStore(settings=settings,
                                      credentials=credentials)
        if stored_username:
            settings.setValue("subtitle_center/username", stored_username)
            settings.sync()
        clients = []

        def client_factory(**kwargs):
            client = SlowClient(gate=gate, **kwargs)
            clients.append(client)
            return client

        coordinator = SubtitleCenterCoordinator(
            player, client_factory=client_factory, settings_store=store)
        player._subtitle_center = coordinator
        created.append((player, coordinator))
        return SimpleNamespace(app=app, player=player, store=store,
                               credentials=credentials, clients=clients,
                               coordinator=coordinator, tmp=tmp_path)

    yield factory

    for player, coordinator in created:
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


def pump_until(app, predicate, timeout_ms=12000):
    end = time.time() + timeout_ms / 1000.0
    while time.time() < end:
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.005)
    app.processEvents()
    return predicate()


def start_running_test(env, gate):
    env.coordinator.open()
    env.coordinator.open_settings()
    settings = env.coordinator.settings_dialog
    settings.api_key_field.setText(API_KEY)
    settings.connection_test_requested.emit()
    env.app.processEvents()
    return settings


# =====================================================================
# 1. Kapanış UI'ı BLOKE ETMEZ
# =====================================================================

def test_closing_settings_during_a_test_is_fast(bench):
    gate = threading.Event()
    env = bench(gate=gate)
    settings = start_running_test(env, gate)

    started = time.monotonic()
    settings.close()
    elapsed = time.monotonic() - started

    assert elapsed < 0.25, f"kapanis UI'i {elapsed:.3f}s bloke etti"
    gate.set()
    assert pump_until(env.app, lambda: env.coordinator.is_idle())


def test_ui_keeps_ticking_while_the_test_drains(bench):
    gate = threading.Event()
    env = bench(gate=gate)
    settings = start_running_test(env, gate)
    ticks = {"n": 0}
    timer = QTimer()
    timer.setTimerType(Qt.TimerType.PreciseTimer)
    timer.setInterval(10)
    timer.timeout.connect(lambda: ticks.__setitem__("n", ticks["n"] + 1))
    timer.start()
    try:
        settings.close()
        pump(env.app, 400)
    finally:
        timer.stop()
        gate.set()
    pump_until(env.app, lambda: env.coordinator.is_idle())

    assert ticks["n"] > 3, f"drenaj sirasinda UI dondu (tick={ticks['n']})"


def test_coordinator_still_owns_the_running_tester(bench):
    gate = threading.Event()
    env = bench(gate=gate)
    settings = start_running_test(env, gate)

    settings.close()
    pump(env.app, 200)

    assert env.coordinator.is_idle() is False, (
        "calisan baglanti testi takipten cikti")
    assert env.coordinator.draining_count() >= 1

    gate.set()
    assert pump_until(env.app, lambda: env.coordinator.is_idle())
    assert env.coordinator.draining_count() == 0


def test_late_result_never_touches_a_destroyed_dialog(bench):
    gate = threading.Event()
    env = bench(gate=gate)
    settings = start_running_test(env, gate)

    settings.close()
    env.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    pump(env.app, 200)
    gate.set()

    assert pump_until(env.app, lambda: env.coordinator.is_idle())
    # Yok edilmiş widget'a dokunulsaydı RuntimeError ile patlardı.
    assert env.coordinator.settings_dialog is None


def test_settings_can_be_reopened_immediately(bench):
    gate = threading.Event()
    env = bench(gate=gate)
    settings = start_running_test(env, gate)
    settings.close()
    pump(env.app, 100)

    assert env.coordinator.open_settings() is True
    fresh = env.coordinator.settings_dialog
    assert fresh is not None and fresh is not settings

    gate.set()
    assert pump_until(env.app, lambda: env.coordinator.is_idle())
    assert fresh.status_text() != STATUS_OK, (
        "eski worker sonucu yeni pencereye yazildi")


def test_old_and_new_testers_are_tracked_separately(bench):
    gate = threading.Event()
    env = bench(gate=gate)
    settings = start_running_test(env, gate)
    settings.close()
    pump(env.app, 100)
    env.coordinator.open_settings()

    assert env.coordinator.draining_count() >= 1
    assert env.coordinator.is_idle() is False

    gate.set()
    assert pump_until(env.app, lambda: env.coordinator.is_idle())


def test_a_tester_is_never_tracked_twice(bench):
    gate = threading.Event()
    env = bench(gate=gate)
    settings = start_running_test(env, gate)

    settings.close()
    pump(env.app, 100)
    env.coordinator._drain_connection_tester()
    env.coordinator._drain_connection_tester()

    assert env.coordinator.draining_count() == 1
    gate.set()
    assert pump_until(env.app, lambda: env.coordinator.is_idle())


def test_player_close_waits_for_the_connection_test(bench):
    gate = threading.Event()
    env = bench(gate=gate, player_class=ClosingPlayer)
    settings = start_running_test(env, gate)
    settings.close()
    pump(env.app, 100)

    env.player.close()

    assert env.player.accepted_closes == 0, "calisan test geride birakildi"
    assert env.player.terminated == 0

    gate.set()
    assert pump_until(env.app, lambda: env.player.accepted_closes == 1)
    assert env.coordinator.is_fully_drained() is True


def test_close_deadline_is_not_a_permission_to_terminate(bench):
    gate = threading.Event()
    env = bench(gate=gate, player_class=ClosingPlayer)
    settings = start_running_test(env, gate)
    settings.close()
    pump(env.app, 100)
    calls = {"n": 0}

    env.coordinator.begin_close(lambda: calls.__setitem__("n", calls["n"] + 1),
                                timeout_ms=150)
    pump(env.app, 700)

    assert calls["n"] == 0, "zaman asiminda kapanis zorlandi"
    assert env.coordinator.is_fully_drained() is False

    gate.set()
    assert pump_until(env.app, lambda: calls["n"] == 1)


def test_no_thread_or_controller_leak_after_cycles(bench):
    env = bench()
    before = threading.active_count()

    for _ in range(3):
        env.coordinator.open()
        env.coordinator.open_settings()
        settings = env.coordinator.settings_dialog
        settings.api_key_field.setText(API_KEY)
        settings.connection_test_requested.emit()
        assert pump_until(env.app, lambda: env.coordinator.is_idle())
        settings.close()
        pump(env.app, 100)

    pump(env.app, 200)
    assert env.coordinator.draining_count() == 0
    assert threading.active_count() <= before


# =====================================================================
# 2. Kayıtlı parola karar matrisi
# =====================================================================

def make_tester(env, dialog=None):
    dialog = dialog or env.coordinator.settings_dialog
    return SubtitleConnectionTestController(
        dialog, client_factory=lambda **kwargs: env.clients.append(
            SlowClient(**kwargs)) or env.clients[-1],
        settings_store=env.store, owner=env.player)


def open_settings(env):
    env.coordinator.open()
    env.coordinator.open_settings()
    return env.coordinator.settings_dialog


def test_A_stored_password_is_used_when_the_field_is_empty(bench):
    env = bench(stored_username=USER, stored_password=STORED_PASSWORD)
    dialog = open_settings(env)
    tester = make_tester(env)
    dialog.api_key_field.setText(API_KEY)
    dialog.username_field.setText(USER)
    dialog.password_field.setText("")

    assert tester.start_test() is True
    assert pump_until(env.app, lambda: tester.is_idle())

    client = env.clients[-1]
    assert client.login_calls == 1, f"login {client.login_calls} kez"
    assert client.search_calls == 0
    assert client.kwargs.get("password") == STORED_PASSWORD
    assert dialog.password_field.text() == "", "parola forma geri yazildi"


def test_A_stored_password_never_leaks_into_the_ui(bench):
    env = bench(stored_username=USER, stored_password=STORED_PASSWORD)
    dialog = open_settings(env)
    tester = make_tester(env)
    dialog.api_key_field.setText(API_KEY)
    dialog.username_field.setText(USER)

    tester.start_test()
    pump_until(env.app, lambda: tester.is_idle())

    blob = " ".join([dialog.status_text(), dialog.password_field.text(),
                     dialog.password_field.toolTip(),
                     dialog.username_field.toolTip(), repr(tester)])
    assert STORED_PASSWORD not in blob
    assert API_KEY not in blob


def test_B_changed_username_never_reuses_the_old_password(bench):
    env = bench(stored_username=USER, stored_password=STORED_PASSWORD)
    dialog = open_settings(env)
    tester = make_tester(env)
    dialog.api_key_field.setText(API_KEY)
    dialog.username_field.setText("BaskaKullanici")
    dialog.password_field.setText("")

    assert tester.start_test() is False
    assert dialog.status_text() == STATUS_PARTIAL_ACCOUNT
    assert all(c.login_calls == 0 for c in env.clients)
    assert all(c.search_calls == 0 for c in env.clients)


def test_C_form_password_wins_and_is_not_persisted(bench):
    env = bench(stored_username=USER, stored_password=STORED_PASSWORD)
    dialog = open_settings(env)
    tester = make_tester(env)
    dialog.api_key_field.setText(API_KEY)
    dialog.username_field.setText(USER)
    dialog.password_field.setText(FORM_PASSWORD)

    tester.start_test()
    assert pump_until(env.app, lambda: tester.is_idle())

    client = env.clients[-1]
    assert client.kwargs.get("password") == FORM_PASSWORD
    assert env.credentials.get_password(USER) == STORED_PASSWORD, (
        "test kayitli parolayi degistirdi")


def test_D_no_account_uses_api_key_only_search(bench):
    env = bench()
    dialog = open_settings(env)
    tester = make_tester(env)
    dialog.api_key_field.setText(API_KEY)
    dialog.username_field.setText("")
    dialog.password_field.setText("")

    assert tester.start_test() is True
    assert pump_until(env.app, lambda: tester.is_idle())

    client = env.clients[-1]
    assert client.search_calls == 1
    assert client.login_calls == 0
    assert client.download_calls == 0


def test_E_password_without_username_never_reaches_the_network(bench):
    env = bench()
    dialog = open_settings(env)
    tester = make_tester(env)
    dialog.api_key_field.setText(API_KEY)
    dialog.username_field.setText("")
    dialog.password_field.setText(FORM_PASSWORD)

    assert tester.start_test() is False
    assert dialog.status_text() == STATUS_PARTIAL_ACCOUNT
    assert all(c.login_calls == 0 and c.search_calls == 0
               for c in env.clients)


def test_F_missing_api_key_is_rejected_before_reading_credentials(bench):
    env = bench(stored_username=USER, stored_password=STORED_PASSWORD)
    dialog = open_settings(env)
    tester = make_tester(env)
    env.credentials.reads.clear()
    dialog.api_key_field.setText("")
    dialog.username_field.setText(USER)

    assert tester.start_test() is False
    assert env.credentials.reads == [], "anahtar yokken credential okundu"
    assert all(c.login_calls == 0 and c.search_calls == 0
               for c in env.clients)


# =====================================================================
# 3. Kaydet ve test birbirinden BAĞIMSIZ
# =====================================================================

def test_connection_test_writes_no_persistent_settings(bench):
    env = bench()
    dialog = open_settings(env)
    tester = make_tester(env)
    dialog.api_key_field.setText("TEST-ONLY-KEY")
    dialog.username_field.setText(USER)
    dialog.password_field.setText(FORM_PASSWORD)

    tester.start_test()
    assert pump_until(env.app, lambda: tester.is_idle())

    assert env.credentials.get_api_key() == API_KEY, (
        "test API anahtarini kalici yazdi")
    assert env.credentials.get_password(USER) is None
    assert env.store.load()["username"] == ""


def test_successful_test_does_not_imply_save(bench):
    env = bench()
    dialog = open_settings(env)
    tester = make_tester(env)
    dialog.api_key_field.setText("TEST-ONLY-KEY")

    tester.start_test()
    assert pump_until(env.app, lambda: tester.is_idle())

    assert dialog.status_text() == STATUS_OK
    assert env.credentials.get_api_key() == API_KEY


def test_save_is_blocked_while_a_connection_test_runs(bench):
    gate = threading.Event()
    env = bench(gate=gate)
    dialog = open_settings(env)
    dialog.api_key_field.setText(API_KEY)
    dialog.connection_test_requested.emit()
    env.app.processEvents()

    assert dialog.settings_save_button.isEnabled() is False, (
        "iki farkli credential setiyle es zamanli islem mumkun")

    gate.set()
    assert pump_until(env.app, lambda: env.coordinator.is_idle())
    assert dialog.settings_save_button.isEnabled() is True
