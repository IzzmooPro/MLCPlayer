# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Altyazı Merkezi ayar kalıcılığı ve GİZLİ BİLGİ regresyonları.

Bu tur YALNIZCA ayar katmanıdır: gerçek ağ YOK, indirme YOK, menü
entegrasyonu YOK, görsel değişiklik YOK.

Ölçülen kurallar
----------------
1. Kullanıcı adı, dil ve indirme sonrası davranış QSettings'te kalır.
2. PAROLA **ve API ANAHTARI** QSettings/INI içinde HİÇBİR biçimde bulunmaz;
   ayrı credential target'larında tutulur.
3. Credential Manager kullanılamıyorsa secret yalnız OTURUM belleğindedir ve
   bu kullanıcıya açıkça bildirilir (yanlış kalıcılık sözü verilmez).
4. Oturum belleği target/kullanıcı izolasyonludur: A'nın parolası B'ye dönmez.
5. `QSettings.status()` hatası başarı gibi raporlanmaz.
6. Kullanıcı adı değişiminde yeni kayıt ÖNCE yazılır, eski kayıt EN SON
   ve yalnız her şey başarılıysa temizlenir.
7. Boş API anahtarı açık bir silme isteğidir; boş parola ise kayıtlı
   parolayı silmez.
8. Credential silme İDEMPOTENT'tir.

Testler gerçek HKCU ayarlarını ve gerçek Credential Manager'ı KİRLETMEZ:
QSettings her testte tmp_path altında benzersiz bir INI'dir, kimlik deposu
ya sahtedir ya da `use_credential_manager=False` ile açılır. Gerçek
Credential Manager yalnızca opt-in testte (MLC_CREDENTIAL_SMOKE=1)
benzersiz target ile kullanılır ve `try/finally` ile temizlenir.
"""
import os
import uuid

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QEvent, QSettings
from PyQt6.QtWidgets import QApplication, QMainWindow

from app import opensubtitles as osub
from app.subtitle_center import SubtitleCenterDialog
from app.subtitle_center_settings_dialog import SubtitleCenterSettingsDialog
# `AFTER_DOWNLOAD_*` sabitleri KALDIRILDI: ayar hiçbir davranışı
# etkilemiyordu. Eski anahtarın tolere edildiğini ölçen testler aşağıda
# ham dize ("download_only") kullanır.
from app.subtitle_settings import (
    DEFAULT_LANGUAGE,
    LEGACY_API_KEY_KEY, SECRETS_PERSISTENT, SECRETS_SESSION_ONLY,
    SubtitleSettingsStore)
from app.subtitle_settings_controller import (
    STATUS_CLEANUP_FAILED, STATUS_MIGRATION_FAILED, STATUS_ROLLBACK_FAILED,
    STATUS_SAVE_FAILED, STATUS_SAVED, STATUS_SAVED_SESSION_ONLY,
    STATUS_SECRETS_FAILED, SubtitleSettingsController)

MEDIA = {
    "file_name": "Resident.Alien.S01E01.Pilot.1080p.WEB-DL.mkv",
    "title": "Resident Alien",
    "season": 1, "episode": 1, "is_series": True,
    "target_name": "Resident.Alien.S01E01.Pilot.1080p.WEB-DL.srt",
}

PASSWORD = "P4rolaGizli!"
API_KEY = "APIKEYSUPERSECRET123"


# --- Sahte kimlik deposu: gerçek Credential Manager'a DOKUNMAZ ---

class FakeCredentialStore:
    """Gerçek `CredentialStore` sözleşmesini taklit eder.

    `storage` ile "kalıcı yazabildim" / "yalnız oturum belleği" ayrımı
    seçilebilir; böylece iki mesaj yolu da gerçek Windows'a bağlı olmadan
    ölçülür.
    """

    API_TARGET = "fake/api-key"

    def __init__(self, storage=SECRETS_PERSISTENT, fail=False,
                 delete_fail=False, api_write_error=False,
                 delete_fail_users=None):
        self.storage = storage
        self.fail = fail
        # Backend silmeyi REDDEDER (False döner) — atomiklik testleri için.
        self.delete_fail = delete_fail
        # YALNIZCA bu kullanıcıların silinmesi reddedilir. Gerçekçi senaryo:
        # eski kaydın temizlenmesi başarısız olur ama geri alma çalışır.
        self.delete_fail_users = set(delete_fail_users or ())
        # `set_api_key` GERÇEK exception fırlatır — migration testleri için.
        self.api_write_error = api_write_error
        self.secrets = {}
        self.deleted = []

    # -- parola --
    def _password_target(self, username):
        return f"fake/password/{username or 'default'}"

    def set_password(self, username, password):
        if self.fail:
            raise RuntimeError("yazilamadi")
        self.secrets[self._password_target(username)] = password
        return self.storage

    def get_password(self, username):
        return self.secrets.get(self._password_target(username))

    def delete_password(self, username):
        target = self._password_target(username)
        self.deleted.append(target)
        if self.delete_fail or username in self.delete_fail_users:
            return False
        self.secrets.pop(target, None)
        return True

    # -- API anahtarı --
    def set_api_key(self, api_key):
        if self.api_write_error:
            raise RuntimeError("guvenli depoya yazilamadi")
        if self.fail:
            raise RuntimeError("yazilamadi")
        self.secrets[self.API_TARGET] = api_key
        return self.storage

    def get_api_key(self):
        return self.secrets.get(self.API_TARGET)

    def delete_api_key(self):
        self.deleted.append(self.API_TARGET)
        if self.delete_fail:
            return False
        self.secrets.pop(self.API_TARGET, None)
        return True


class BrokenSettings:
    """`sync()` sonrası hata bildiren sahte QSettings backend'i."""

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


class RemoveResistantSettings:
    """Yazma çalışır ama `remove()` etkisizdir (plaintext silinemez)."""

    def __init__(self):
        self.store = {}
        self.remove_calls = []

    def value(self, key, default=None):
        return self.store.get(key, default)

    def setValue(self, key, value):
        self.store[key] = value

    def remove(self, key):
        # Silme isteği KAYDEDİLİR ama uygulanmaz.
        self.remove_calls.append(key)

    def sync(self):
        return None

    def status(self):
        return QSettings.Status.NoError


def make_settings(tmp_path, name="settings.ini"):
    return QSettings(str(tmp_path / name), QSettings.Format.IniFormat)


def make_store(tmp_path, credentials=None, settings=None):
    """İzole store: gerçek HKCU ve gerçek Credential Manager KULLANILMAZ."""
    return SubtitleSettingsStore(
        settings=settings if settings is not None else make_settings(tmp_path),
        credentials=credentials if credentials is not None
        else FakeCredentialStore())


def stored_text(tmp_path):
    """tmp_path altındaki bütün dosyaların ham içeriği."""
    text = ""
    for path in tmp_path.rglob("*"):
        if path.is_file():
            text += path.read_text(encoding="utf-8", errors="ignore")
    return text


@pytest.fixture
def dialog_factory():
    """Ayar alanları ARTIK ayrı pencerededir.

    Eski sağdan açılan çekmece ana arama alanını 35 px'e daraltıyordu ve
    kullanıcı kararıyla kaldırıldı. Controller sözleşmesi değişmedi:
    `SubtitleCenterSettingsDialog` aynı alan adlarını sağlar, `language_box`
    ve arama durumu ana pencereye vekâleten iletilir.
    """
    app = QApplication.instance() or QApplication([])
    created = []

    def factory():
        window = QMainWindow()
        window.resize(1280, 720)
        center = SubtitleCenterDialog(window, media=MEDIA)
        dialog = SubtitleCenterSettingsDialog(center)
        app.processEvents()
        created.append((window, center, dialog))
        return app, window, dialog

    yield factory

    for window, center, dialog in created:
        for widget in (dialog, center, window):
            try:
                widget.close()
                widget.deleteLater()
            except RuntimeError:
                pass
    app.processEvents()


# =====================================================================
# 1. Gizli bilgi QSettings'e ASLA yazılmaz
# =====================================================================

def test_api_key_and_password_never_reach_the_settings_file(tmp_path):
    store = make_store(tmp_path)

    store.save({"api_key": API_KEY, "username": "kullanici",
                "password": PASSWORD, "language": "Türkçe",
                "after_download": "download_only"})   # eski anahtar

    written = stored_text(tmp_path)
    assert API_KEY not in written, "API anahtari duz ayar dosyasina yazildi"
    assert PASSWORD not in written, "parola duz ayar dosyasina yazildi"
    # Gizli OLMAYAN alanlar kalıcıdır.
    assert "kullanici" in written


def test_api_key_is_not_exposed_by_load(tmp_path):
    store = make_store(tmp_path)
    store.save({"api_key": API_KEY, "username": "kullanici",
                "password": PASSWORD})

    values = store.load()

    assert "api_key" not in values
    assert "password" not in values
    assert store.load_api_key() == API_KEY
    assert store.load_password("kullanici") == PASSWORD


def test_settings_group_has_no_secret_keys(tmp_path):
    settings = make_settings(tmp_path)
    store = make_store(tmp_path, settings=settings)
    store.save({"api_key": API_KEY, "username": "kullanici",
                "password": PASSWORD})

    keys = [key for key in settings.allKeys() if key.startswith("subtitle_center/")]

    assert sorted(keys) == ["subtitle_center/username"], keys


def test_store_repr_does_not_leak_secrets(tmp_path):
    store = make_store(tmp_path)
    result = store.save({"api_key": API_KEY, "password": PASSWORD,
                         "username": "kullanici"})

    blob = " ".join([repr(result), str(result), repr(store.load())])

    assert API_KEY not in blob
    assert PASSWORD not in blob


# =====================================================================
# 2. Ayrı credential target'ları
# =====================================================================

def test_api_key_and_password_use_separate_targets():
    store = osub.CredentialStore(namespace="MLCPlayerTest/Sep",
                                 use_credential_manager=False)

    assert store._api_target() != store._target("kullanici")
    # Kullanıcı adı ne olursa olsun iki uzay kesişmez.
    for username in ("api-key", "default", "", "ApiKey"):
        assert store._api_target() != store._target(username)


def test_api_key_and_password_do_not_overwrite_each_other():
    store = osub.CredentialStore(namespace="MLCPlayerTest/Sep2",
                                 use_credential_manager=False)

    store.set_password("kullanici", PASSWORD)
    store.set_api_key(API_KEY)

    assert store.get_password("kullanici") == PASSWORD
    assert store.get_api_key() == API_KEY


def test_deleting_the_api_key_keeps_the_password():
    store = osub.CredentialStore(namespace="MLCPlayerTest/Sep3",
                                 use_credential_manager=False)
    store.set_password("kullanici", PASSWORD)
    store.set_api_key(API_KEY)

    store.delete_api_key()

    assert store.get_api_key() is None
    assert store.get_password("kullanici") == PASSWORD


# =====================================================================
# 3. Oturum belleği izolasyonu
# =====================================================================

def test_session_fallback_is_isolated_per_user():
    store = osub.CredentialStore(namespace="MLCPlayerTest/Iso",
                                 use_credential_manager=False)

    store.set_password("kullanici_A", "PAROLA_A")

    assert store.get_password("kullanici_A") == "PAROLA_A"
    assert store.get_password("kullanici_B") is None, (
        "A'nin parolasi B icin dondu")


def test_session_fallback_keeps_other_users_after_delete():
    store = osub.CredentialStore(namespace="MLCPlayerTest/Iso2",
                                 use_credential_manager=False)
    store.set_password("A", "PAROLA_A")
    store.set_password("B", "PAROLA_B")

    store.delete_password("A")

    assert store.get_password("A") is None
    assert store.get_password("B") == "PAROLA_B"


def test_session_fallback_reports_session_memory():
    store = osub.CredentialStore(namespace="MLCPlayerTest/Iso3",
                                 use_credential_manager=False)

    assert store.set_password("kullanici", PASSWORD) == SECRETS_SESSION_ONLY
    assert store.set_api_key(API_KEY) == SECRETS_SESSION_ONLY


def test_credential_delete_is_idempotent():
    store = osub.CredentialStore(namespace="MLCPlayerTest/Idem",
                                 use_credential_manager=False)

    # Hic yazilmamis kayit silinebilmeli.
    assert store.delete_password("hic-olmayan") is True
    assert store.delete_api_key() is True
    store.set_password("kullanici", PASSWORD)
    assert store.delete_password("kullanici") is True
    assert store.delete_password("kullanici") is True


# =====================================================================
# 4. Kullanıcıya doğru kalıcılık bildirimi
# =====================================================================

def test_persistent_save_reports_full_success(tmp_path, dialog_factory):
    store = make_store(tmp_path,
                       credentials=FakeCredentialStore(SECRETS_PERSISTENT))
    app, window, dialog = dialog_factory()
    controller = SubtitleSettingsController(dialog, store, owner=window)

    dialog.api_key_field.setText(API_KEY)
    dialog.username_field.setText("kullanici")
    dialog.password_field.setText(PASSWORD)
    assert controller.save() is True

    assert dialog.status_text() == STATUS_SAVED


def test_session_only_save_warns_the_user(tmp_path, dialog_factory):
    store = make_store(tmp_path,
                       credentials=FakeCredentialStore(SECRETS_SESSION_ONLY))
    app, window, dialog = dialog_factory()
    controller = SubtitleSettingsController(dialog, store, owner=window)

    dialog.api_key_field.setText(API_KEY)
    dialog.username_field.setText("kullanici")
    dialog.password_field.setText(PASSWORD)
    assert controller.save() is True

    assert dialog.status_text() == STATUS_SAVED_SESSION_ONLY
    assert "oturum" in dialog.status_text().lower()


def test_settings_write_failure_reports_failure(tmp_path, dialog_factory):
    store = make_store(tmp_path, settings=BrokenSettings())
    app, window, dialog = dialog_factory()
    controller = SubtitleSettingsController(dialog, store, owner=window)

    dialog.api_key_field.setText(API_KEY)
    dialog.username_field.setText("kullanici")
    dialog.password_field.setText(PASSWORD)

    assert controller.save() is False
    assert dialog.status_text() == STATUS_SAVE_FAILED


def test_store_reports_failure_when_settings_backend_errors(tmp_path):
    store = make_store(tmp_path, settings=BrokenSettings())

    result = store.save({"username": "kullanici", "language": "Türkçe"})

    assert result.failed is True
    assert bool(result) is False


def test_secret_success_does_not_mask_settings_failure(tmp_path):
    """Secret yazılabilmiş olması ayar hatasını ÖRTMEZ.

    NOT: Yazılan secret'lar artık geri de alınır (bkz. rollback bölümü);
    burada ölçülen şey, sonucun tam başarı sayılmamasıdır.
    """
    credentials = FakeCredentialStore(SECRETS_PERSISTENT)
    store = make_store(tmp_path, credentials=credentials,
                       settings=BrokenSettings())

    result = store.save({"username": "kullanici", "password": PASSWORD,
                         "api_key": API_KEY})

    assert result.failed is True, "secret yazildi diye tam basari gosterildi"
    assert result.ok is False


def test_status_messages_never_leak_secrets(tmp_path, dialog_factory):
    for credentials in (FakeCredentialStore(SECRETS_PERSISTENT),
                        FakeCredentialStore(SECRETS_SESSION_ONLY)):
        store = make_store(tmp_path, credentials=credentials,
                           settings=make_settings(tmp_path, "leak.ini"))
        app, window, dialog = dialog_factory()
        controller = SubtitleSettingsController(dialog, store, owner=window)
        dialog.api_key_field.setText(API_KEY)
        dialog.username_field.setText("gizlikullanici")
        dialog.password_field.setText(PASSWORD)
        controller.save()

        status = dialog.status_text()
        for secret in (API_KEY, PASSWORD, "gizlikullanici", "fake/",
                       "AccessError", str(tmp_path)):
            assert secret not in status, f"durum mesaji sizdirdi: {secret}"


def test_failed_save_keeps_the_password_field_for_retry(tmp_path,
                                                        dialog_factory):
    store = make_store(tmp_path, settings=BrokenSettings())
    app, window, dialog = dialog_factory()
    controller = SubtitleSettingsController(dialog, store, owner=window)

    dialog.username_field.setText("kullanici")
    dialog.password_field.setText(PASSWORD)
    controller.save()

    assert dialog.password_field.text() == PASSWORD, (
        "basarisiz kayitta kullanici bastan yazmak zorunda kaliyor")


def test_failed_save_does_not_change_the_search_language(tmp_path,
                                                         dialog_factory):
    store = make_store(tmp_path, settings=BrokenSettings())
    app, window, dialog = dialog_factory()
    controller = SubtitleSettingsController(dialog, store, owner=window)
    before = dialog.language_box.currentText()

    dialog.settings_language_box.setCurrentText("Almanca")
    controller.save()

    assert dialog.language_box.currentText() == before


# =====================================================================
# 5. Kullanıcı adı değişimi
# =====================================================================

def test_username_change_removes_the_old_credential(tmp_path):
    credentials = FakeCredentialStore()
    store = make_store(tmp_path, credentials=credentials)
    store.save({"username": "eski", "password": PASSWORD})

    store.save({"username": "yeni", "password": "YeniParola!"})

    assert credentials.get_password("eski") is None, "eski kayit sahipsiz kaldi"
    assert credentials.get_password("yeni") == "YeniParola!"


def test_username_change_without_password_does_not_rebind_the_secret(tmp_path):
    credentials = FakeCredentialStore()
    store = make_store(tmp_path, credentials=credentials)
    store.save({"username": "eski", "password": PASSWORD})

    store.save({"username": "yeni"})

    # KARAR: parola yeni kullaniciya BAGLANMAZ; eski kayit da sahipsiz
    # birakilmaz, temizlenir.
    assert credentials.get_password("yeni") is None
    assert credentials.get_password("eski") is None
    assert store.load_password("yeni") == ""


def test_old_credential_survives_when_the_settings_write_fails(tmp_path):
    credentials = FakeCredentialStore()
    seed = make_store(tmp_path, credentials=credentials)
    seed.save({"username": "eski", "password": PASSWORD})

    broken = BrokenSettings()
    broken.store["subtitle_center/username"] = "eski"
    store = SubtitleSettingsStore(settings=broken, credentials=credentials)
    store.save({"username": "yeni", "password": "YeniParola!"})

    assert credentials.get_password("eski") == PASSWORD, (
        "kayit basarisizken eski credential erken silindi")


def test_new_credential_is_written_before_the_old_one_is_removed(tmp_path):
    """Sıra kanıtı: silme çağrısı yazma çağrısından SONRA gelmeli."""
    order = []

    class OrderedStore(FakeCredentialStore):
        def set_password(self, username, password):
            order.append(f"write:{username}")
            return super().set_password(username, password)

        def delete_password(self, username):
            order.append(f"delete:{username}")
            return super().delete_password(username)

    credentials = OrderedStore()
    store = make_store(tmp_path, credentials=credentials)
    store.save({"username": "eski", "password": PASSWORD})
    order.clear()

    store.save({"username": "yeni", "password": "YeniParola!"})

    assert order == ["write:yeni", "delete:eski"], order


def test_unchanged_username_keeps_its_credential(tmp_path):
    credentials = FakeCredentialStore()
    store = make_store(tmp_path, credentials=credentials)
    store.save({"username": "kullanici", "password": PASSWORD})

    store.save({"username": "kullanici", "language": "Almanca"})

    assert credentials.get_password("kullanici") == PASSWORD
    assert credentials.deleted == []


# =====================================================================
# 6. API anahtarı temizleme ve eski plaintext göçü
# =====================================================================

def test_empty_api_key_deletes_the_stored_secret(tmp_path):
    credentials = FakeCredentialStore()
    store = make_store(tmp_path, credentials=credentials)
    store.save({"api_key": API_KEY})

    store.save({"api_key": ""})

    assert credentials.get_api_key() is None
    assert store.load_api_key() == ""
    assert FakeCredentialStore.API_TARGET in credentials.deleted


def test_empty_password_does_not_erase_the_stored_one(tmp_path):
    credentials = FakeCredentialStore()
    store = make_store(tmp_path, credentials=credentials)
    store.save({"username": "kullanici", "password": PASSWORD})

    store.save({"username": "kullanici", "password": "", "api_key": "YENI"})

    assert credentials.get_password("kullanici") == PASSWORD
    assert credentials.get_api_key() == "YENI"


def test_legacy_plaintext_api_key_is_migrated_and_removed(tmp_path):
    settings = make_settings(tmp_path)
    settings.setValue(f"subtitle_center/{LEGACY_API_KEY_KEY}", "LEGACYKEY123")
    settings.sync()
    credentials = FakeCredentialStore()
    store = make_store(tmp_path, credentials=credentials, settings=settings)

    migrated = store.load_api_key()

    assert migrated == "LEGACYKEY123"
    assert credentials.get_api_key() == "LEGACYKEY123"
    assert "LEGACYKEY123" not in stored_text(tmp_path), (
        "eski plaintext anahtar INI icinde kaldi")


def test_legacy_key_is_removed_even_when_only_session_storage_is_available(
        tmp_path):
    settings = make_settings(tmp_path)
    settings.setValue(f"subtitle_center/{LEGACY_API_KEY_KEY}", "LEGACYKEY456")
    settings.sync()
    credentials = FakeCredentialStore(SECRETS_SESSION_ONLY)
    store = make_store(tmp_path, credentials=credentials, settings=settings)

    store.load_api_key()

    assert "LEGACYKEY456" not in stored_text(tmp_path), (
        "guvenli yazim oturumluk kalinca plaintext kopya birakildi")


# =====================================================================
# 7. Varsayılanlar ve geri yükleme
# =====================================================================

def test_store_returns_defaults_when_nothing_saved(tmp_path):
    values = make_store(tmp_path).load()

    assert values["username"] == ""
    assert values["language"] == DEFAULT_LANGUAGE
    # `after_download` artık YOK: sözleşme "okunmaz ve üretilmez".
    assert "after_download" not in values


def test_round_trip_of_non_secret_values(tmp_path):
    credentials = FakeCredentialStore()
    settings = make_settings(tmp_path)
    make_store(tmp_path, credentials=credentials, settings=settings).save(
        {"username": "kullanici", "language": "İngilizce",
         "after_download": "download_only"})    # tolere edilir, yazılmaz

    values = SubtitleSettingsStore(
        settings=make_settings(tmp_path), credentials=credentials).load()

    assert values["username"] == "kullanici"
    assert values["language"] == "İngilizce"
    assert "after_download" not in values


def test_unknown_stored_values_fall_back_to_defaults(tmp_path):
    settings = make_settings(tmp_path)
    make_store(tmp_path, settings=settings).save(
        {"language": "Klingonca", "after_download": "her ne ise"})

    values = SubtitleSettingsStore(settings=make_settings(tmp_path),
                                   credentials=FakeCredentialStore()).load()

    assert values["language"] == DEFAULT_LANGUAGE
    assert "after_download" not in values


def test_controller_restores_saved_values_into_the_drawer(tmp_path,
                                                          dialog_factory):
    credentials = FakeCredentialStore()
    store = make_store(tmp_path, credentials=credentials)
    store.save({"api_key": API_KEY, "username": "kullanici",
                "language": "Almanca", "after_download": "download_only"})

    app, window, dialog = dialog_factory()
    SubtitleSettingsController(dialog, store, owner=window)
    app.processEvents()

    assert dialog.api_key_field.text() == API_KEY
    assert dialog.username_field.text() == "kullanici"
    assert dialog.settings_language_box.currentText() == "Almanca"
    # "İndirme sonrası" kutusu KALDIRILDI; eski kayıtlı değer arayüze
    # hiçbir biçimde yansımaz ve pencerenin açılmasını engellemez.
    assert not hasattr(dialog, "after_download_box")
    assert dialog.language_box.currentText() == "Almanca"


def test_password_field_is_never_prefilled(tmp_path, dialog_factory):
    credentials = FakeCredentialStore()
    store = make_store(tmp_path, credentials=credentials)
    store.save({"username": "kullanici", "password": PASSWORD})

    app, window, dialog = dialog_factory()
    controller = SubtitleSettingsController(dialog, store, owner=window)
    app.processEvents()

    assert dialog.password_field.text() == ""
    controller.revert()
    assert dialog.password_field.text() == ""


def test_api_key_field_stays_masked(tmp_path, dialog_factory):
    from PyQt6.QtWidgets import QLineEdit

    credentials = FakeCredentialStore()
    store = make_store(tmp_path, credentials=credentials)
    store.save({"api_key": API_KEY})

    app, window, dialog = dialog_factory()
    SubtitleSettingsController(dialog, store, owner=window)

    assert dialog.api_key_field.echoMode() == QLineEdit.EchoMode.Password


def test_cancel_restores_stored_values_and_discards_edits(tmp_path,
                                                          dialog_factory):
    credentials = FakeCredentialStore()
    store = make_store(tmp_path, credentials=credentials)
    store.save({"api_key": "ESKIKEY", "username": "eski",
                "language": "Türkçe"})
    app, window, dialog = dialog_factory()
    SubtitleSettingsController(dialog, store, owner=window)

    dialog.api_key_field.setText("KAYDEDILMEYEN")
    dialog.password_field.setText(PASSWORD)
    dialog.settings_cancel_button.click()
    app.processEvents()

    assert dialog.api_key_field.text() == "ESKIKEY"
    assert dialog.password_field.text() == ""
    assert credentials.get_api_key() == "ESKIKEY"


def test_save_button_persists_drawer_values(tmp_path, dialog_factory):
    credentials = FakeCredentialStore()
    settings = make_settings(tmp_path)
    store = make_store(tmp_path, credentials=credentials, settings=settings)
    app, window, dialog = dialog_factory()
    SubtitleSettingsController(dialog, store, owner=window)

    dialog.api_key_field.setText(API_KEY)
    dialog.username_field.setText("kullanici")
    dialog.password_field.setText(PASSWORD)
    dialog.settings_language_box.setCurrentText("Fransızca")
    dialog.settings_save_button.click()
    app.processEvents()

    values = SubtitleSettingsStore(settings=make_settings(tmp_path),
                                   credentials=credentials).load()
    assert values["username"] == "kullanici"
    assert values["language"] == "Fransızca"
    assert "after_download" not in values
    assert credentials.get_api_key() == API_KEY
    assert credentials.get_password("kullanici") == PASSWORD
    assert dialog.password_field.text() == ""
    written = stored_text(tmp_path)
    assert API_KEY not in written and PASSWORD not in written


# =====================================================================
# 8. Katman saflığı ve yaşam döngüsü
# =====================================================================

def test_visual_shell_module_stays_free_of_persistence():
    import inspect

    from app import subtitle_center

    source = inspect.getsource(subtitle_center)
    for forbidden in ("QSettings", "CredentialStore", "OpenSubtitlesClient"):
        assert forbidden not in source, (
            f"gorsel kabuk kaliciligi ustlendi: {forbidden}")


def test_settings_layer_makes_no_network_calls():
    import inspect

    from app import subtitle_settings, subtitle_settings_controller

    for module in (subtitle_settings, subtitle_settings_controller):
        source = inspect.getsource(module)
        for forbidden in ("urllib", "OpenSubtitlesClient", "UrllibTransport",
                          "api.opensubtitles.com"):
            assert forbidden not in source, (
                f"ayar katmani ag katmanina bulasti: {forbidden}")


def test_controller_is_not_parented_to_the_dialog(tmp_path, dialog_factory):
    store = make_store(tmp_path)
    app, window, dialog = dialog_factory()

    controller = SubtitleSettingsController(dialog, store, owner=window)

    assert controller.parent() is not dialog


def test_controller_survives_dialog_destruction(tmp_path, dialog_factory):
    store = make_store(tmp_path)
    app, window, dialog = dialog_factory()
    controller = SubtitleSettingsController(dialog, store, owner=window)

    dialog.close()
    dialog.deleteLater()
    # `processEvents()` tek başına DeferredDelete kuyruğunu boşaltmaz.
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()

    assert controller.save() is False
    assert controller.revert() is False
    assert controller.dialog is None


# =====================================================================
# 9. Atomiklik: secret silme sonuçları yok sayılmaz
# =====================================================================

def test_failed_api_key_deletion_is_not_full_success(tmp_path):
    credentials = FakeCredentialStore()
    store = make_store(tmp_path, credentials=credentials)
    store.save({"api_key": API_KEY})
    credentials.delete_fail = True

    result = store.save({"api_key": ""})

    assert credentials.get_api_key() == API_KEY, "test kurulumu: silme reddedilmeli"
    assert result.secrets_saved is False
    assert result.ok is False, "silinemeyen secret tam basari sayildi"


def test_failed_api_key_deletion_is_not_reported_as_saved(tmp_path,
                                                          dialog_factory):
    credentials = FakeCredentialStore()
    store = make_store(tmp_path, credentials=credentials)
    store.save({"api_key": API_KEY})
    credentials.delete_fail = True

    app, window, dialog = dialog_factory()
    controller = SubtitleSettingsController(dialog, store, owner=window)
    dialog.api_key_field.setText("")
    controller.save()

    assert dialog.status_text() != STATUS_SAVED


def test_failed_old_credential_cleanup_is_reported(tmp_path):
    credentials = FakeCredentialStore()
    settings = make_settings(tmp_path)
    store = SubtitleSettingsStore(settings=settings, credentials=credentials)
    store.save({"username": "birinci", "password": PASSWORD})
    credentials.delete_fail_users = {"birinci"}

    result = store.save({"username": "ikinci", "password": "YeniParola!"})

    assert credentials.get_password("birinci") == PASSWORD
    assert result.cleanup_ok is False
    assert result.accepted is False, (
        "temizlenemeyen eski kayit kabul edilmis islem sayildi")
    assert committed_username(settings) == "birinci", "islem commit edildi"


def test_cleanup_failure_shows_a_safe_partial_message(tmp_path,
                                                      dialog_factory):
    credentials = FakeCredentialStore()
    store = make_store(tmp_path, credentials=credentials)
    # NOT: kullanici adlari mesajdaki Turkce kelimelerle CAKISMAMALI
    # ("eski"/"yeni" mesajin kendi metninde geciyor).
    store.save({"username": "birinci", "password": PASSWORD})
    credentials.delete_fail_users = {"birinci"}

    app, window, dialog = dialog_factory()
    controller = SubtitleSettingsController(dialog, store, owner=window)
    dialog.api_key_field.setText(API_KEY)
    dialog.username_field.setText("ikinci")
    dialog.password_field.setText("YeniParola!")
    controller.save()

    status = dialog.status_text()
    assert status == STATUS_CLEANUP_FAILED
    assert status != STATUS_SAVED
    for secret in (PASSWORD, "YeniParola!", "birinci", "ikinci", "fake/"):
        assert secret not in status


# =====================================================================
# 10. Migration exception session-only DEĞİLDİR
# =====================================================================

def seed_legacy(tmp_path, value, settings=None):
    settings = settings if settings is not None else make_settings(tmp_path)
    settings.setValue(f"subtitle_center/{LEGACY_API_KEY_KEY}", value)
    sync = getattr(settings, "sync", None)
    if callable(sync):
        sync()
    return settings


def test_migration_exception_is_not_session_only(tmp_path):
    settings = seed_legacy(tmp_path, "LEGACYKEY789")
    credentials = FakeCredentialStore(api_write_error=True)
    store = make_store(tmp_path, credentials=credentials, settings=settings)

    migration = store.migrate_legacy_api_key()

    assert credentials.get_api_key() is None
    assert migration.failed is True
    assert migration.storage != SECRETS_SESSION_ONLY, (
        "yazilamayan secret oturum bellegine yazilmis gibi raporlandi"
    )
    assert "LEGACYKEY789" not in stored_text(tmp_path)


def test_migration_failure_reaches_the_save_result(tmp_path):
    settings = seed_legacy(tmp_path, "LEGACYKEY790")
    credentials = FakeCredentialStore(api_write_error=True)
    store = make_store(tmp_path, credentials=credentials, settings=settings)

    result = store.save({"username": "kullanici"})

    assert result.migration_ok is False
    assert result.session_only is False
    assert result.ok is False


def test_save_repairs_a_failed_migration_and_reports_success(tmp_path,
                                                             dialog_factory):
    """Göç başarısızsa kullanıcı yeni anahtar girerek onarabilir.

    NOT: API anahtarı ARTIK zorunlu olduğu için ayar penceresinden yapılan
    her kayıt bir anahtar taşır ve kayıp göçü kapatır. Bu yüzden
    "göç başarısız + kullanıcı yeni anahtar vermedi" durumu bu yüzeyden
    ULAŞILAMAZ hâle geldi; kuralın kendisi store seviyesinde
    `test_migration_failure_reaches_the_save_result` ile kilitli kalır.
    """
    class MigrationOnlyFailure(FakeCredentialStore):
        def __init__(self):
            super().__init__()
            self.first_write = True

        def set_api_key(self, api_key):
            if self.first_write:
                self.first_write = False
                raise RuntimeError("guvenli depoya yazilamadi")
            return super().set_api_key(api_key)

    settings = seed_legacy(tmp_path, "LEGACYKEY791")
    credentials = MigrationOnlyFailure()
    store = make_store(tmp_path, credentials=credentials, settings=settings)

    app, window, dialog = dialog_factory()
    controller = SubtitleSettingsController(dialog, store, owner=window)
    assert store._migration_failed is True, "test kurulumu: goc basarisiz olmali"

    dialog.api_key_field.setText(API_KEY)
    dialog.username_field.setText("kullanici")
    dialog.password_field.setText(PASSWORD)
    assert controller.save() is True

    status = dialog.status_text()
    assert status == STATUS_SAVED
    assert credentials.get_api_key() == API_KEY
    assert store._migration_failed is False
    assert "LEGACYKEY791" not in status
    assert "RuntimeError" not in status
    assert "LEGACYKEY791" not in stored_text(tmp_path)


def test_real_session_fallback_stays_a_valid_session_only_success(tmp_path):
    """Gerçek üretim fallback'i (session_memory) HÂLÂ başarıdır."""
    settings = seed_legacy(tmp_path, "LEGACYKEY792")
    credentials = FakeCredentialStore(SECRETS_SESSION_ONLY)
    store = make_store(tmp_path, credentials=credentials, settings=settings)

    migration = store.migrate_legacy_api_key()

    assert migration.failed is False
    assert migration.storage == SECRETS_SESSION_ONLY
    assert credentials.get_api_key() == "LEGACYKEY792"


# =====================================================================
# 11. QSettings başarısızlığında geri alma (rollback)
# =====================================================================

def test_settings_failure_rolls_back_the_new_password(tmp_path):
    credentials = FakeCredentialStore()
    seed = make_store(tmp_path, credentials=credentials)
    seed.save({"username": "eski", "password": PASSWORD})

    broken = BrokenSettings()
    broken.store["subtitle_center/username"] = "eski"
    store = SubtitleSettingsStore(settings=broken, credentials=credentials)
    result = store.save({"username": "yeni", "password": "YeniParola!"})

    assert result.failed is True
    assert credentials.get_password("eski") == PASSWORD, "eski kayit bozuldu"
    assert credentials.get_password("yeni") is None, (
        "yeni credential sahipsiz kaldi")


def test_settings_failure_restores_the_previous_api_key(tmp_path):
    credentials = FakeCredentialStore()
    credentials.set_api_key("ESKIKEY")

    broken = BrokenSettings()
    store = SubtitleSettingsStore(settings=broken, credentials=credentials)
    result = store.save({"username": "kullanici", "api_key": "YENIKEY"})

    assert result.failed is True
    assert credentials.get_api_key() == "ESKIKEY", (
        "basarisiz kayittan sonra yeni anahtar yarim state birakti")


def test_settings_failure_deletes_a_newly_created_api_key(tmp_path):
    credentials = FakeCredentialStore()  # onceden anahtar YOK

    store = SubtitleSettingsStore(settings=BrokenSettings(),
                                  credentials=credentials)
    store.save({"username": "kullanici", "api_key": "YENIKEY"})

    assert credentials.get_api_key() is None, "sahipsiz yeni anahtar kaldi"


def test_settings_failure_leaves_settings_keys_untouched(tmp_path):
    credentials = FakeCredentialStore()
    broken = BrokenSettings()
    broken.store["subtitle_center/username"] = "eski"
    broken.store["subtitle_center/language"] = "Türkçe"
    before = dict(broken.store)

    store = SubtitleSettingsStore(settings=broken, credentials=credentials)
    store.save({"username": "yeni", "language": "Almanca",
                "after_download": "download_only"})

    assert broken.store == before, f"yarim yazilmis ayar kaldi: {broken.store}"


def test_rollback_failure_is_reported_separately(tmp_path):
    class NoRollbackStore(FakeCredentialStore):
        def __init__(self):
            super().__init__()
            self.armed = False

        def delete_api_key(self):
            if self.armed:
                return False
            return super().delete_api_key()

    credentials = NoRollbackStore()
    store = SubtitleSettingsStore(settings=BrokenSettings(),
                                  credentials=credentials)
    credentials.armed = True

    result = store.save({"username": "kullanici", "api_key": "YENIKEY"})

    assert result.failed is True
    assert result.rollback_ok is False
    assert result.ok is False


def test_rollback_failure_shows_a_distinct_message(tmp_path, dialog_factory):
    class NoRollbackStore(FakeCredentialStore):
        def delete_api_key(self):
            super().delete_api_key()
            return False

    store = SubtitleSettingsStore(settings=BrokenSettings(),
                                  credentials=NoRollbackStore())
    app, window, dialog = dialog_factory()
    controller = SubtitleSettingsController(dialog, store, owner=window)
    dialog.api_key_field.setText("YENIKEY")

    assert controller.save() is False
    assert dialog.status_text() == STATUS_ROLLBACK_FAILED
    assert "YENIKEY" not in dialog.status_text()


# =====================================================================
# 12. Açık yeni API anahtarı legacy değeri EZMEZ
# =====================================================================

def test_explicit_api_key_wins_over_legacy_plaintext(tmp_path):
    settings = seed_legacy(tmp_path, "LEGACY_KEY_OLD")
    credentials = FakeCredentialStore()
    store = make_store(tmp_path, credentials=credentials, settings=settings)

    store.save({"api_key": "NEW_KEY_FROM_USER", "username": "kullanici"})

    assert credentials.get_api_key() == "NEW_KEY_FROM_USER", (
        "yeni anahtar legacy deger tarafindan ezildi")
    written = stored_text(tmp_path)
    assert "LEGACY_KEY_OLD" not in written
    assert "NEW_KEY_FROM_USER" not in written


def test_explicit_empty_api_key_wins_over_legacy_plaintext(tmp_path):
    settings = seed_legacy(tmp_path, "LEGACY_KEY_OLD2")
    credentials = FakeCredentialStore()
    store = make_store(tmp_path, credentials=credentials, settings=settings)

    store.save({"api_key": "", "username": "kullanici"})

    assert credentials.get_api_key() is None, "silme istegi legacy ile ezildi"
    assert "LEGACY_KEY_OLD2" not in stored_text(tmp_path)


def test_legacy_key_is_still_migrated_when_the_user_does_not_touch_it(tmp_path):
    settings = seed_legacy(tmp_path, "LEGACY_KEY_KEEP")
    credentials = FakeCredentialStore()
    store = make_store(tmp_path, credentials=credentials, settings=settings)

    store.save({"username": "kullanici"})  # api_key ANAHTARI YOK

    assert credentials.get_api_key() == "LEGACY_KEY_KEEP"
    assert "LEGACY_KEY_KEEP" not in stored_text(tmp_path)


# =====================================================================
# 13. Plaintext silinemezse migration başarılı sayılmaz
# =====================================================================

def test_plaintext_removal_failure_is_reported(tmp_path):
    settings = RemoveResistantSettings()
    settings.store[f"subtitle_center/{LEGACY_API_KEY_KEY}"] = "STUCKKEY"
    credentials = FakeCredentialStore()
    store = SubtitleSettingsStore(settings=settings, credentials=credentials)

    migration = store.migrate_legacy_api_key()

    assert credentials.get_api_key() == "STUCKKEY", "guvenli yazim calismali"
    assert migration.plaintext_removed is False
    assert migration.failed is True, "diskte kalan plaintext basari sayildi"


def test_plaintext_removal_failure_shows_a_safe_message(tmp_path,
                                                        dialog_factory):
    settings = RemoveResistantSettings()
    settings.store[f"subtitle_center/{LEGACY_API_KEY_KEY}"] = "STUCKKEY2"
    store = SubtitleSettingsStore(settings=settings,
                                  credentials=FakeCredentialStore())
    app, window, dialog = dialog_factory()
    controller = SubtitleSettingsController(dialog, store, owner=window)

    dialog.username_field.setText("kullanici")
    controller.save()

    status = dialog.status_text()
    assert status != STATUS_SAVED
    assert "STUCKKEY2" not in status


# =====================================================================
# 14. Controller sonuç matrisi
# =====================================================================

def test_controller_message_matrix(tmp_path, dialog_factory):
    """Her sonuç durumu için TEK ve doğru mesaj."""
    cases = []

    # 1) Tam kalıcı başarı
    cases.append(("tam_basari", FakeCredentialStore(SECRETS_PERSISTENT),
                  make_settings(tmp_path, "m1.ini"), {}, STATUS_SAVED, True))
    # 2) Yalnız oturum
    cases.append(("session_only", FakeCredentialStore(SECRETS_SESSION_ONLY),
                  make_settings(tmp_path, "m2.ini"), {},
                  STATUS_SAVED_SESSION_ONLY, True))
    # 3) Genel QSettings başarısızlığı
    cases.append(("settings_failure", FakeCredentialStore(), BrokenSettings(),
                  {}, STATUS_SAVE_FAILED, False))
    # 4) Secret yazma başarısızlığı — KABUL EDİLMEZ
    cases.append(("secret_write_failure", FakeCredentialStore(fail=True),
                  make_settings(tmp_path, "m4.ini"), {},
                  STATUS_SECRETS_FAILED, False))

    for name, credentials, settings, seed, expected, accepted in cases:
        store = SubtitleSettingsStore(settings=settings,
                                      credentials=credentials)
        app, window, dialog = dialog_factory()
        controller = SubtitleSettingsController(dialog, store, owner=window)
        dialog.api_key_field.setText(API_KEY)
        dialog.username_field.setText("kullanici")
        dialog.password_field.setText(PASSWORD)

        returned = controller.save()

        assert dialog.status_text() == expected, f"{name}: {dialog.status_text()!r}"
        assert returned is accepted, name
        for secret in (API_KEY, PASSWORD):
            assert secret not in dialog.status_text(), name


def test_accepted_save_clears_the_password_field(tmp_path, dialog_factory):
    for credentials in (FakeCredentialStore(SECRETS_PERSISTENT),
                        FakeCredentialStore(SECRETS_SESSION_ONLY)):
        store = SubtitleSettingsStore(
            settings=make_settings(tmp_path, f"clr{id(credentials)}.ini"),
            credentials=credentials)
        app, window, dialog = dialog_factory()
        controller = SubtitleSettingsController(dialog, store, owner=window)
        dialog.api_key_field.setText(API_KEY)
        dialog.username_field.setText("kullanici")
        dialog.password_field.setText(PASSWORD)

        controller.save()

        assert dialog.password_field.text() == ""


def test_rejected_save_keeps_the_password_field(tmp_path, dialog_factory):
    store = SubtitleSettingsStore(settings=BrokenSettings(),
                                  credentials=FakeCredentialStore())
    app, window, dialog = dialog_factory()
    controller = SubtitleSettingsController(dialog, store, owner=window)
    dialog.username_field.setText("kullanici")
    dialog.password_field.setText(PASSWORD)

    controller.save()

    assert dialog.password_field.text() == PASSWORD


# =====================================================================
# 15. Save GERÇEK bir transaction'dır
# =====================================================================

class PasswordFailStore(FakeCredentialStore):
    """API anahtarı yazılır ama PAROLA yazılamaz."""

    def set_password(self, username, password):
        raise RuntimeError("parola yazilamadi")


class SilentSettings:
    """`setValue` exception ATMAZ ama değeri gerçekten değiştirmez.

    Sessizce yazmayan backend: rollback'in `readback` ile doğrulanması
    gerektiğini kanıtlar.
    """

    def __init__(self, initial=None):
        self.store = dict(initial or {})
        self.writes = []

    def value(self, key, default=None):
        return self.store.get(key, default)

    def setValue(self, key, value):
        self.writes.append(key)  # kaydeder, UYGULAMAZ

    def remove(self, key):
        self.writes.append(key)

    def sync(self):
        return None

    def status(self):
        return QSettings.Status.NoError


class UnreadableSecretStore(FakeCredentialStore):
    """Snapshot okuması HATA verir: önceki durum BİLİNMEZ."""

    def get_api_key(self):
        raise RuntimeError("okunamadi")


def committed_username(settings):
    return settings.value("subtitle_center/username", None)


# --- A. Parola yazılamazken username commit edilmemeli ---

def test_password_write_failure_does_not_commit_the_username(tmp_path):
    credentials = PasswordFailStore()
    settings = make_settings(tmp_path)
    seed = SubtitleSettingsStore(settings=settings,
                                 credentials=FakeCredentialStore())
    seed.credentials.set_password("eski", PASSWORD)
    seed.save({"username": "eski"})

    store = SubtitleSettingsStore(settings=settings, credentials=credentials)
    result = store.save({"username": "yeni", "password": "YeniParola!"})

    assert result.accepted is False
    assert committed_username(settings) == "eski", (
        "secret yazilamadi ama username commit edildi")


def test_password_write_failure_is_rejected_by_the_controller(tmp_path,
                                                              dialog_factory):
    settings = make_settings(tmp_path)
    store = SubtitleSettingsStore(settings=settings,
                                  credentials=PasswordFailStore())
    app, window, dialog = dialog_factory()
    controller = SubtitleSettingsController(dialog, store, owner=window)
    before_language = dialog.language_box.currentText()

    dialog.api_key_field.setText(API_KEY)
    dialog.username_field.setText("kullanici")
    dialog.password_field.setText(PASSWORD)
    dialog.settings_language_box.setCurrentText("Almanca")

    assert controller.save() is False
    assert dialog.password_field.text() == PASSWORD, "parola alani temizlendi"
    assert dialog.language_box.currentText() == before_language
    assert dialog.status_text() == STATUS_SECRETS_FAILED


# --- B. API anahtarı yazıldıysa parola hatasında GERİ ALINMALI ---

def test_api_key_is_rolled_back_when_the_password_write_fails(tmp_path):
    credentials = PasswordFailStore()
    store = SubtitleSettingsStore(settings=make_settings(tmp_path),
                                  credentials=credentials)

    result = store.save({"api_key": "YENIKEY", "username": "kullanici",
                         "password": PASSWORD})

    assert result.accepted is False
    assert credentials.get_api_key() is None, (
        "parola hatasinda yeni API anahtari geri alinmadi")


def test_previous_api_key_is_restored_when_the_password_write_fails(tmp_path):
    credentials = PasswordFailStore()
    credentials.secrets[FakeCredentialStore.API_TARGET] = "ESKIKEY"
    store = SubtitleSettingsStore(settings=make_settings(tmp_path),
                                  credentials=credentials)

    store.save({"api_key": "YENIKEY", "password": PASSWORD})

    assert credentials.get_api_key() == "ESKIKEY"


def test_api_key_delete_failure_blocks_the_settings_write(tmp_path):
    credentials = FakeCredentialStore()
    settings = make_settings(tmp_path)
    store = SubtitleSettingsStore(settings=settings, credentials=credentials)
    store.save({"api_key": API_KEY, "username": "eski"})
    credentials.delete_fail = True

    result = store.save({"api_key": "", "username": "yeni"})

    assert result.accepted is False
    assert committed_username(settings) == "eski", "ayarlar yine de yazildi"
    assert credentials.get_api_key() == API_KEY, "eski anahtar korunmali"


# --- C. Cleanup başarısızlığında TAM rollback ---

def test_cleanup_failure_rolls_the_settings_back(tmp_path):
    credentials = FakeCredentialStore()
    settings = make_settings(tmp_path)
    store = SubtitleSettingsStore(settings=settings, credentials=credentials)
    store.save({"username": "birinci", "password": PASSWORD,
                "language": "Türkçe"})
    # YALNIZCA eski kaydin silinmesi reddedilir; geri alma calisabilmeli.
    credentials.delete_fail_users = {"birinci"}

    result = store.save({"username": "ikinci", "password": "YeniParola!",
                         "language": "Almanca"})

    assert result.accepted is False
    assert result.cleanup_ok is False
    assert committed_username(settings) == "birinci", (
        "cleanup basarisizken yeni username commit edildi")
    assert settings.value("subtitle_center/language") == "Türkçe"
    # Eski kayit zaten silinemedi; yenisi de sahipsiz birakilmaz.
    assert credentials.get_password("birinci") == PASSWORD
    assert credentials.get_password("ikinci") is None


def test_cleanup_failure_is_rejected_by_the_controller(tmp_path,
                                                       dialog_factory):
    credentials = FakeCredentialStore()
    store = make_store(tmp_path, credentials=credentials)
    store.save({"username": "birinci", "password": PASSWORD})
    credentials.delete_fail_users = {"birinci"}

    app, window, dialog = dialog_factory()
    controller = SubtitleSettingsController(dialog, store, owner=window)
    dialog.api_key_field.setText(API_KEY)
    dialog.username_field.setText("ikinci")
    dialog.password_field.setText("YeniParola!")

    assert controller.save() is False
    assert dialog.password_field.text() == "YeniParola!"
    assert dialog.status_text() == STATUS_CLEANUP_FAILED


# --- D. Sessizce yazmayan backend rollback'i doğrulamalı ---

def test_silent_restore_backend_is_detected(tmp_path):
    settings = SilentSettings({"subtitle_center/username": "eski"})
    credentials = PasswordFailStore()
    store = SubtitleSettingsStore(settings=settings, credentials=credentials)

    result = store.save({"username": "yeni", "password": PASSWORD})

    # Bu backend hicbir sey yazmadigi icin islem zaten reddedilir; onemli
    # olan rollback'in "yazdim" diye YALAN sOylememesidir.
    assert result.accepted is False


def test_rollback_readback_catches_a_settings_backend_that_ignores_writes(
        tmp_path):
    """QSettings yazdı sanıp geri alamayan backend `rollback_ok` düşürmeli."""

    class WriteOnceThenIgnore(SilentSettings):
        """İlk yazma çalışır, GERİ ALMA sessizce yok sayılır."""

        def __init__(self, initial=None):
            super().__init__(initial)
            self.allow_writes = True

        def setValue(self, key, value):
            if self.allow_writes:
                self.store[key] = value
            else:
                self.writes.append(key)

        def remove(self, key):
            if self.allow_writes:
                self.store.pop(key, None)
            else:
                self.writes.append(key)

        def status(self):
            # Yazma bitti; commit dogrulamasi basarisiz.
            return (QSettings.Status.NoError if self.allow_writes
                    else QSettings.Status.AccessError)

    settings = WriteOnceThenIgnore({"subtitle_center/username": "eski"})
    credentials = FakeCredentialStore()
    credentials.delete_fail = True
    store = SubtitleSettingsStore(settings=settings, credentials=credentials)
    store.save({"username": "eski"})
    settings.allow_writes = False

    result = store.save({"username": "yeni", "password": PASSWORD})

    assert result.accepted is False
    assert result.rollback_ok is False, (
        "geri alinamayan ayar 'geri alindi' sayildi")


# --- E. Secret snapshot okunamıyorsa işleme BAŞLANMAZ ---

def test_unreadable_secret_snapshot_rejects_the_transaction(tmp_path):
    credentials = UnreadableSecretStore()
    settings = make_settings(tmp_path)
    store = SubtitleSettingsStore(settings=settings, credentials=credentials)

    result = store.save({"api_key": "YENIKEY", "username": "kullanici"})

    assert result.accepted is False
    assert committed_username(settings) is None, "bilinmeyen durumda yazildi"


def test_unreadable_secret_snapshot_does_not_touch_the_credential(tmp_path):
    credentials = UnreadableSecretStore()
    credentials.secrets[FakeCredentialStore.API_TARGET] = "MEVCUTKEY"
    store = SubtitleSettingsStore(settings=make_settings(tmp_path),
                                  credentials=credentials)

    store.save({"api_key": "", "username": "kullanici"})

    assert credentials.secrets[FakeCredentialStore.API_TARGET] == "MEVCUTKEY", (
        "onceki durum bilinmezken mevcut credential silindi")
    assert FakeCredentialStore.API_TARGET not in credentials.deleted


# --- Kabul edilen tek iki sonuç ---

def test_session_memory_fallback_is_an_accepted_save(tmp_path):
    settings = make_settings(tmp_path)
    store = SubtitleSettingsStore(
        settings=settings, credentials=FakeCredentialStore(SECRETS_SESSION_ONLY))

    result = store.save({"username": "kullanici", "password": PASSWORD})

    assert result.accepted is True
    assert result.session_only is True
    assert result.persistent is False
    assert committed_username(settings) == "kullanici"


def test_persistent_save_is_accepted_and_persistent(tmp_path):
    store = make_store(tmp_path)

    result = store.save({"username": "kullanici", "password": PASSWORD})

    assert result.accepted is True
    assert result.persistent is True
    assert result.session_only is False
    assert bool(result) is True


def test_bool_of_result_means_accepted(tmp_path):
    store = SubtitleSettingsStore(settings=BrokenSettings(),
                                  credentials=FakeCredentialStore())

    assert bool(store.save({"username": "kullanici"})) is False


# =====================================================================
# 16. Opt-in: GERÇEK Credential Manager roundtrip
# =====================================================================

@pytest.mark.skipif(os.environ.get("MLC_CREDENTIAL_SMOKE") != "1",
                    reason="opt-in: MLC_CREDENTIAL_SMOKE=1 gerekir")
@pytest.mark.skipif(os.name != "nt", reason="yalniz Windows")
def test_real_credential_manager_roundtrip_and_cleanup():
    """Gerçek Credential Manager: yaz / oku / sil / yok.

    Benzersiz target kullanılır ve `try/finally` ile HER durumda temizlenir;
    kullanıcının mevcut kimlik bilgilerine dokunulmaz.
    """
    namespace = f"MLCPlayerTest/Smoke/{uuid.uuid4().hex}"
    store = osub.CredentialStore(namespace=namespace,
                                 use_credential_manager=True)
    username = "mlc-test-user"
    try:
        assert store.set_password(username, PASSWORD) == SECRETS_PERSISTENT
        assert store.get_password(username) == PASSWORD

        assert store.set_api_key(API_KEY) == SECRETS_PERSISTENT
        assert store.get_api_key() == API_KEY
        # Ayri target'lar: biri digerini ezmez.
        assert store.get_password(username) == PASSWORD

        assert store.delete_api_key() is True
        assert store.get_api_key() is None
        assert store.get_password(username) == PASSWORD

        assert store.delete_password(username) is True
        assert store.get_password(username) is None
        # Idempotent: ikinci silme de basari.
        assert store.delete_password(username) is True
        assert store.delete_api_key() is True
    finally:
        # ARTIK BIRAKILMAZ.
        store.delete_password(username)
        store.delete_api_key()

    assert store.get_password(username) is None
    assert store.get_api_key() is None
