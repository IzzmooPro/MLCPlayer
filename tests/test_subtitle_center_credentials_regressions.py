"""API anahtarı doğrulaması ve "Bağlantıyı Test Et" regresyonları.

Kullanıcı yalnız kullanıcı adı/parola girip arama yapmayı denedi; API
anahtarı boştu. OpenSubtitles REST API'de anahtar ZORUNLUDUR, hesap
bilgileri yalnızca daha yüksek kota içindir. Arayüz bunu anlatmalı ve
eksik anahtarla kaydı REDDETMELİDİR.

GERÇEK AĞA ÇIKILMAZ: bağlantı testi sahte istemciyle ölçülür.
"""
import os
import threading
import time
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QEvent, QSettings
from PyQt6.QtWidgets import QApplication, QMainWindow

from app import opensubtitles as osub
from app.subtitle_center import SubtitleCenterDialog
from app.subtitle_center_settings_dialog import (
    API_KEY_HELP_URL, SubtitleCenterSettingsDialog)
from app.subtitle_connection_test_controller import (
    STATUS_AUTH_FAILED, STATUS_NEEDS_KEY, STATUS_OK, STATUS_PARTIAL_ACCOUNT,
    SubtitleConnectionTestController)
from app.subtitle_settings import SubtitleSettingsStore
from app.subtitle_settings_controller import (
    STATUS_ACCOUNT_INCOMPLETE, STATUS_API_KEY_REQUIRED, STATUS_SAVED,
    SubtitleSettingsController)

API_KEY = "APIKEYSUPERSECRET123"
PASSWORD = "P4rolaGizli!"


class FakeCredentialStore:
    def __init__(self, api_key=""):
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


@pytest.fixture
def bench(tmp_path):
    app = QApplication.instance() or QApplication([])
    created = []

    def factory(api_key=""):
        window = QMainWindow()
        center = SubtitleCenterDialog(window, media={
            "title": "Resident Alien", "season": 1, "episode": 1,
            "is_series": True, "target_name": "x.srt"})
        dialog = SubtitleCenterSettingsDialog(center)
        credentials = FakeCredentialStore(api_key)
        store = SubtitleSettingsStore(
            settings=QSettings(str(tmp_path / "settings.ini"),
                               QSettings.Format.IniFormat),
            credentials=credentials)
        controller = SubtitleSettingsController(dialog, store, owner=window)
        app.processEvents()
        created.append((window, center, dialog))
        return SimpleNamespace(app=app, window=window, center=center,
                               dialog=dialog, store=store,
                               credentials=credentials, controller=controller)

    yield factory

    for window, center, dialog in created:
        for widget in (dialog, center, window):
            try:
                widget.close()
                widget.deleteLater()
            except RuntimeError:
                pass
    app.processEvents()


def fill(dialog, api_key="", username="", password=""):
    dialog.api_key_field.setText(api_key)
    dialog.username_field.setText(username)
    dialog.password_field.setText(password)


# =====================================================================
# 1. Arayüz anlatımı
# =====================================================================

def test_field_labels_state_what_is_required(bench):
    from PyQt6.QtWidgets import QLabel

    env = bench()
    labels = [w.text() for w in env.dialog.findChildren(QLabel)]
    joined = " ".join(labels)

    assert "API anahtarı (zorunlu)" in joined
    assert "kullanıcı adı (isteğe bağlı)" in joined
    assert "Parola (isteğe bağlı)" in joined


def test_hint_explains_key_and_optional_account(bench):
    env = bench()

    hint = env.dialog.credential_hint_text()
    assert "API anahtarı gerekir" in hint
    assert "isteğe bağlı" in hint


def test_hint_points_at_the_new_dot_com_site(bench):
    env = bench()

    hint = env.dialog.credential_hint_text()
    assert "OpenSubtitles.com" in hint
    assert "opensubtitles.org" in hint, "eski site farkı açıkça belirtilmeli"


def test_help_button_opens_the_official_guide_only_on_click(bench,
                                                            monkeypatch):
    opened = []
    monkeypatch.setattr(
        "app.subtitle_center_settings_dialog.webbrowser.open",
        lambda url: opened.append(url) or True)
    env = bench()

    assert opened == [], "pencere acilisinda tarayici acildi"
    env.dialog.help_button.click()
    env.app.processEvents()

    assert opened == [API_KEY_HELP_URL]


def test_help_url_is_the_documented_guide():
    assert API_KEY_HELP_URL == (
        "https://opensubtitles.tawk.help/article/getting-started")


# =====================================================================
# 2. API anahtarı doğrulama matrisi
# =====================================================================

def test_empty_api_key_is_rejected(bench):
    env = bench()
    fill(env.dialog, api_key="", username="MuratPH", password="")

    assert env.controller.save() is False
    assert env.dialog.status_text() == STATUS_API_KEY_REQUIRED


def test_rejected_save_keeps_existing_settings_untouched(bench):
    env = bench(api_key=API_KEY)
    env.store.save({"username": "eski", "language": "Türkçe"})
    fill(env.dialog, api_key="", username="yeni", password=PASSWORD)

    env.controller.save()

    assert env.store.load()["username"] == "eski"
    assert env.credentials.get_api_key() == API_KEY
    assert env.dialog.password_field.text() == PASSWORD, (
        "reddedilen kayitta parola alani temizlendi")


def test_username_without_password_is_warned(bench):
    env = bench()
    fill(env.dialog, api_key=API_KEY, username="MuratPH", password="")

    assert env.controller.save() is False
    assert env.dialog.status_text() == STATUS_ACCOUNT_INCOMPLETE


def test_password_without_username_is_warned(bench):
    env = bench()
    fill(env.dialog, api_key=API_KEY, username="", password=PASSWORD)

    assert env.controller.save() is False
    assert env.dialog.status_text() == STATUS_ACCOUNT_INCOMPLETE


def test_api_key_only_is_accepted(bench):
    env = bench()
    fill(env.dialog, api_key=API_KEY, username="", password="")

    assert env.controller.save() is True
    assert env.dialog.status_text() == STATUS_SAVED
    assert env.credentials.get_api_key() == API_KEY


def test_full_credentials_are_accepted(bench):
    env = bench()
    fill(env.dialog, api_key=API_KEY, username="MuratPH", password=PASSWORD)

    assert env.controller.save() is True
    assert env.store.load()["username"] == "MuratPH"
    assert env.credentials.get_password("MuratPH") == PASSWORD


@pytest.mark.parametrize("case", [
    {"api_key": "", "username": "MuratPH", "password": ""},
    {"api_key": API_KEY, "username": "MuratPH", "password": ""},
    {"api_key": API_KEY, "username": "", "password": PASSWORD},
])
def test_validation_messages_never_leak_secrets(bench, case):
    env = bench()
    fill(env.dialog, **case)

    env.controller.save()

    status = env.dialog.status_text()
    for secret in (API_KEY, PASSWORD, "MuratPH"):
        if secret:
            assert secret not in status


# =====================================================================
# 3. Bağlantıyı Test Et
# =====================================================================

class FakeClient:
    def __init__(self, gate=None, error=None, token=True):
        self.gate = gate
        self.error = error
        self.token = token
        self.login_calls = 0
        self.search_calls = 0
        self.download_calls = 0

    def _wait(self):
        if self.gate is not None:
            self.gate.wait(15)

    def login(self):
        self.login_calls += 1
        self._wait()
        if self.error:
            raise self.error
        return self.token

    def has_token(self):
        return bool(self.token)

    def search(self, **kwargs):
        self.search_calls += 1
        self._wait()
        if self.error:
            raise self.error
        return []

    def download_link(self, file_id):
        self.download_calls += 1
        raise AssertionError("baglanti testi kota tuketmemeli")


def make_tester(env, client):
    return SubtitleConnectionTestController(
        env.dialog, client_factory=lambda **kwargs: client, owner=env.window)


def pump_until(app, predicate, timeout_ms=8000):
    end = time.time() + timeout_ms / 1000.0
    while time.time() < end:
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()


def test_test_without_an_api_key_makes_no_network_call(bench):
    env = bench()
    client = FakeClient()
    tester = make_tester(env, client)
    fill(env.dialog, api_key="", username="MuratPH", password=PASSWORD)

    assert tester.start_test() is False
    assert env.dialog.status_text() == STATUS_NEEDS_KEY
    assert client.login_calls == 0 and client.search_calls == 0


def test_api_key_only_test_uses_search_not_download(bench):
    env = bench()
    client = FakeClient()
    tester = make_tester(env, client)
    fill(env.dialog, api_key=API_KEY)

    assert tester.start_test() is True
    assert pump_until(env.app, lambda: tester.is_idle())

    assert client.search_calls == 1
    assert client.login_calls == 0
    assert client.download_calls == 0, "kota tuketildi"
    assert env.dialog.status_text() == STATUS_OK


def test_full_credentials_test_uses_login(bench):
    env = bench()
    client = FakeClient()
    tester = make_tester(env, client)
    fill(env.dialog, api_key=API_KEY, username="MuratPH", password=PASSWORD)

    tester.start_test()
    assert pump_until(env.app, lambda: tester.is_idle())

    assert client.login_calls == 1
    assert client.search_calls == 0
    assert env.dialog.status_text() == STATUS_OK


@pytest.mark.parametrize("case", [
    {"username": "MuratPH", "password": ""},
    {"username": "", "password": PASSWORD},
])
def test_partial_account_never_reaches_the_network(bench, case):
    env = bench()
    client = FakeClient()
    tester = make_tester(env, client)
    fill(env.dialog, api_key=API_KEY, **case)

    assert tester.start_test() is False
    assert env.dialog.status_text() == STATUS_PARTIAL_ACCOUNT
    assert client.login_calls == 0 and client.search_calls == 0


def test_second_click_does_not_start_a_second_request(bench):
    env = bench()
    gate = threading.Event()
    client = FakeClient(gate=gate)
    tester = make_tester(env, client)
    fill(env.dialog, api_key=API_KEY, username="MuratPH", password=PASSWORD)

    assert tester.start_test() is True
    env.app.processEvents()
    assert tester.start_test() is False, "ikinci istek baslatildi"
    assert env.dialog.test_button.isEnabled() is False

    gate.set()
    assert pump_until(env.app, lambda: tester.is_idle())
    assert client.login_calls == 1, f"login {client.login_calls} kez"
    assert env.dialog.test_button.isEnabled() is True


def test_auth_failure_shows_the_documented_message(bench):
    env = bench()
    client = FakeClient(error=osub.AuthError("401"))
    tester = make_tester(env, client)
    fill(env.dialog, api_key=API_KEY, username="MuratPH", password=PASSWORD)

    tester.start_test()
    assert pump_until(env.app, lambda: tester.is_idle())

    assert env.dialog.status_text() == STATUS_AUTH_FAILED


@pytest.mark.parametrize("error,expected", [
    (osub.NetworkTimeoutError(), osub.NetworkTimeoutError.user_message),
    (osub.RateLimitError(), osub.RateLimitError.user_message),
    (osub.NetworkError(), osub.NetworkError.user_message),
])
def test_other_errors_use_the_safe_message_layer(bench, error, expected):
    env = bench()
    client = FakeClient(error=error)
    tester = make_tester(env, client)
    fill(env.dialog, api_key=API_KEY)

    tester.start_test()
    assert pump_until(env.app, lambda: tester.is_idle())

    assert env.dialog.status_text() == expected


def test_test_messages_never_leak_secrets(bench):
    env = bench()
    client = FakeClient(error=osub.AuthError(f"401 {API_KEY}"))
    tester = make_tester(env, client)
    fill(env.dialog, api_key=API_KEY, username="MuratPH", password=PASSWORD)

    tester.start_test()
    pump_until(env.app, lambda: tester.is_idle())

    status = env.dialog.status_text()
    for secret in (API_KEY, PASSWORD):
        assert secret not in status


def test_test_does_not_persist_settings(bench):
    env = bench()
    client = FakeClient()
    tester = make_tester(env, client)
    fill(env.dialog, api_key=API_KEY, username="MuratPH", password=PASSWORD)

    tester.start_test()
    pump_until(env.app, lambda: tester.is_idle())

    assert env.credentials.get_api_key() is None, (
        "test kaydetmeden kalici ayar degistirdi")
    assert env.store.load()["username"] == ""


def test_closing_the_dialog_drains_the_test_worker(bench):
    env = bench()
    gate = threading.Event()
    client = FakeClient(gate=gate)
    tester = make_tester(env, client)
    fill(env.dialog, api_key=API_KEY)
    tester.start_test()
    env.app.processEvents()

    env.dialog.close()
    env.app.processEvents()
    assert tester.is_idle() is False

    gate.set()
    assert pump_until(env.app, lambda: tester.is_idle(), 10000)
    assert tester.shutdown(wait_ms=3000) is True


def test_network_work_never_runs_on_the_ui_thread(bench):
    env = bench()
    seen = {}
    client = FakeClient()
    original = client.search

    def spy(**kwargs):
        seen["thread"] = threading.get_ident()
        return original(**kwargs)

    client.search = spy
    tester = make_tester(env, client)
    fill(env.dialog, api_key=API_KEY)

    tester.start_test()
    assert pump_until(env.app, lambda: tester.is_idle())

    assert seen.get("thread") not in (None, threading.get_ident())
