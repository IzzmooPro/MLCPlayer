"""Altyazı Merkezi ayar kalıcılığı: QSettings + Windows Credential Manager.

Katman kuralı:

    SubtitleCenterDialog  (saf görsel kabuk — kalıcılık BİLMEZ)
        ▲
        │ SubtitleSettingsController (Qt bağlantıları)
        ▼
    SubtitleSettingsStore  (bu modül)
        ├─ QSettings        → username, language        (GİZLİ DEĞİL)
        └─ CredentialStore  → PAROLA ve API ANAHTARI (ayrı target'lar)

Kurallar:

- PAROLA **ve API ANAHTARI** QSettings'e, INI'ye veya başka bir düz metin
  dosyasına ASLA yazılmaz. İkisi ayrı credential target'ında tutulur.
- Credential Manager kullanılamıyorsa secret yalnız OTURUM belleğinde kalır;
  bu durum çağırana açıkça bildirilir — kullanıcıya yanlış kalıcılık sözü
  verilmez.
- `QSettings` ve `CredentialStore` DIŞARIDAN enjekte edilebilir; testler
  gerçek HKCU ayarlarını ve gerçek Credential Manager'ı kirletmez.
- `settings.sync()` sonrası `status()` kontrol edilir; yazma hatası başarı
  gibi raporlanmaz.
- Bilinmeyen/bozuk kayıtlı değerler sessizce varsayılana düşer.
- Bu modül ağ çağrısı YAPMAZ ve ağ istemcisi oluşturmaz.
"""
from PyQt6.QtCore import QSettings

from app.opensubtitles import (
    STORAGE_CREDENTIAL_MANAGER, STORAGE_SESSION_MEMORY, CredentialStore)

SETTINGS_ORGANIZATION = "MLCPlayer"
SETTINGS_APPLICATION = "MLCPlayer"
SETTINGS_GROUP = "subtitle_center"
# Eski geliştirme sürümü API anahtarını BURAYA düz metin yazıyordu. Artık
# yalnızca migration için okunur ve ardından SİLİNİR.
LEGACY_API_KEY_KEY = "api_key"

# Dil, kullanıcıya görünen etiketle saklanır; teknik kod çevirisi
# `subtitle_search_controller.LANGUAGE_CODES` sorumluluğundadır.
SUPPORTED_LANGUAGES = ("Türkçe", "İngilizce", "Almanca", "Fransızca",
                       "İspanyolca")
DEFAULT_LANGUAGE = "Türkçe"

# `after_download` KALDIRILDI. Ayar hiçbir davranışı etkilemiyordu;
# indirme akışı artık her zaman "indir + uygula"dır. Eski QSettings
# anahtarı okunmaz ve yazılmaz; varlığı hata üretmez (bkz. `load()`).

# Secret depolama sonucu
SECRETS_NONE = "none"                                  # secret verilmedi
SECRETS_PERSISTENT = STORAGE_CREDENTIAL_MANAGER        # kalıcı
SECRETS_SESSION_ONLY = STORAGE_SESSION_MEMORY          # yalnız bu oturum


class MigrationResult:
    """Eski düz metin API anahtarı göçünün AÇIK sonucu.

    `secure_ok` gerçekten güvenli depoya yazılıp yazılmadığını söyler.
    ÖNEMLİ: üretim fallback'i olan `session_memory` bir BAŞARIDIR (secret
    gerçekten oturum belleğine kondu); yalnız yazma hiç gerçekleşmediyse
    (exception) `secure_ok` False olur.
    """

    def __init__(self, performed=False, storage=SECRETS_NONE, secure_ok=True,
                 plaintext_removed=True):
        self.performed = bool(performed)
        self.storage = storage
        self.secure_ok = bool(secure_ok)
        self.plaintext_removed = bool(plaintext_removed)

    @property
    def ok(self):
        return self.secure_ok and self.plaintext_removed

    @property
    def failed(self):
        return not self.ok

    def __bool__(self):
        return self.ok

    def __repr__(self):
        # Secret DEĞERİ asla yazılmaz.
        return (f"MigrationResult(performed={self.performed}, "
                f"storage={self.storage!r}, secure_ok={self.secure_ok}, "
                f"plaintext_removed={self.plaintext_removed})")


class SecretSnapshot:
    """Bir secret'ın İŞLEM ÖNCESİ durumu.

    `readable=False`, "secret yoktu" DEMEK DEĞİLDİR: önceki durumun
    okunamadığını söyler. İkisini karıştırmak, geri alma sırasında var olan
    bir credential'ın yanlışlıkla silinmesine yol açardı.
    """

    def __init__(self, readable, value=None):
        self.readable = bool(readable)
        self.value = value

    @property
    def present(self):
        return bool(self.value)

    def __repr__(self):
        # Secret DEĞERİ asla yazılmaz; yalnız var olup olmadığı.
        return (f"SecretSnapshot(readable={self.readable}, "
                f"present={self.present})")


class SettingsSaveResult:
    """`save()` sonucunun AÇIK hâli.

    Alanların her biri ayrı bir gerçeği taşır; tek bir bayrak altında
    ezilmezler:

    - `settings_saved`  : gizli OLMAYAN ayarlar yazıldı mı
    - `secrets_saved`   : istenen secret yazma/silme işlemleri başarılı mı
    - `cleanup_ok`      : eski kullanıcının artık kaydı temizlendi mi
    - `migration_ok`    : eski düz metin anahtar göçü tamamlandı mı
    - `rollback_ok`     : başarısızlıkta geri alma tamamlandı mı
    - `secret_storage`  : secret'lar nereye gitti

    `bool(result)` == `accepted`: işlemin kullanıcı açısından kabul edilip
    edilmediği. Kalıcılık sözü için `persistent` / `session_only`
    kullanılmalıdır; `settings_saved` tek başına kabul anlamına GELMEZ.
    """

    def __init__(self, settings_saved, secrets_saved=True, cleanup_ok=True,
                 migration_ok=True, rollback_ok=True,
                 secret_storage=SECRETS_NONE):
        self.settings_saved = bool(settings_saved)
        self.secrets_saved = bool(secrets_saved)
        self.cleanup_ok = bool(cleanup_ok)
        self.migration_ok = bool(migration_ok)
        self.rollback_ok = bool(rollback_ok)
        self.secret_storage = secret_storage

    @property
    def accepted(self):
        """İşlem KULLANICI AÇISINDAN kabul edildi mi?

        Kabul edilen YALNIZCA iki sonuç vardır: tam kalıcı başarı ve gerçek
        session-memory fallback'i. Secret yazma/silme, temizleme, göç veya
        geri alma adımlarından biri bile eksikse işlem kabul EDİLMEZ ve
        hiçbir değişiklik commit edilmiş olmaz.
        """
        return (self.settings_saved and self.secrets_saved
                and self.cleanup_ok and self.migration_ok
                and self.rollback_ok)

    @property
    def failed(self):
        return not self.accepted

    @property
    def session_only(self):
        """Kabul edildi ama secret yalnız bu oturumda yaşayacak."""
        return self.accepted and self.secret_storage == SECRETS_SESSION_ONLY

    @property
    def persistent(self):
        """Kabul edildi ve bütün secret'lar KALICI."""
        return self.accepted and not self.session_only

    # Geriye uyum: `ok` her zaman "eksiksiz ve kalıcı" anlamındaydı.
    @property
    def ok(self):
        return self.persistent

    def __bool__(self):
        return self.accepted

    def __repr__(self):
        # Secret DEĞERİ değil, yalnız nereye gittiği yazılır.
        return (f"SettingsSaveResult(settings_saved={self.settings_saved}, "
                f"secrets_saved={self.secrets_saved}, "
                f"cleanup_ok={self.cleanup_ok}, "
                f"migration_ok={self.migration_ok}, "
                f"rollback_ok={self.rollback_ok}, "
                f"secret_storage={self.secret_storage!r})")


class SubtitleSettingsStore:
    """Gizli olmayan ayarlar QSettings'te; parola ve API anahtarı güvenli depoda."""

    def __init__(self, settings=None, credentials=None, group=SETTINGS_GROUP):
        self.settings = settings or QSettings(SETTINGS_ORGANIZATION,
                                              SETTINGS_APPLICATION)
        self.credentials = credentials or CredentialStore()
        self.group = group
        # Göç bir kez başarısız olduysa anahtar KAYBOLMUŞTUR. Bayrak, kullanıcı
        # yeni bir anahtar girene kadar yaşar; aksi halde hatayı ilk okuyan
        # çağrı (örn. formu doldurma) yutar ve kullanıcı hiç haberdar olmaz.
        self._migration_failed = False

    # --- Anahtarlar ---

    def _key(self, name):
        return f"{self.group}/{name}"

    def _text(self, name, default=""):
        try:
            value = self.settings.value(self._key(name), default)
        except Exception:
            return default
        if value is None:
            return default
        return str(value)

    def _settings_ok(self):
        """`sync()` sonrası backend durumu. Hata varsa başarı raporlanmaz."""
        try:
            self.settings.sync()
        except Exception:
            return False
        status = getattr(self.settings, "status", None)
        if not callable(status):
            return True
        try:
            return status() == QSettings.Status.NoError
        except Exception:
            return False

    def _remove_key(self, key):
        """Anahtarı siler ve GERÇEKTEN gittiğini doğrular."""
        try:
            self.settings.remove(key)
        except Exception:
            return False
        try:
            self.settings.sync()
        except Exception:
            pass
        try:
            return self.settings.value(key, None) in (None, "")
        except Exception:
            return False

    # --- Geri alınabilir ayar yazımı ---

    def _snapshot(self, names):
        """Yazılacak anahtarların İŞLEM ÖNCESİ hâli (yoksa None)."""
        snapshot = {}
        for name in names:
            key = self._key(name)
            try:
                snapshot[key] = self.settings.value(key, None)
            except Exception:
                snapshot[key] = None
        return snapshot

    def _restore(self, snapshot):
        """Ayarları snapshot'a döndürür ve GERİ DÖNDÜĞÜNÜ DOĞRULAR.

        `setValue`/`remove` exception atmaması yetmez: sessizce yazmayan bir
        backend "geri aldım" yalanı söyletirdi. Bu yüzden her anahtar
        yeniden OKUNUR; önceden olmayan anahtar gerçekten yok olmalı,
        önceden olan değer birebir geri gelmelidir.

        `status()` tek başına belirleyici değildir: hiç yazamayan bir
        backend'de disk zaten eski hâlindedir. Karar, gözlenebilir tek
        kanıt olan readback'e bırakılır.
        """
        ok = True
        for key, old in snapshot.items():
            try:
                if old is None:
                    self.settings.remove(key)
                else:
                    self.settings.setValue(key, old)
            except Exception:
                ok = False
        try:
            self.settings.sync()
        except Exception:
            ok = False

        # DOĞRULAMA
        for key, old in snapshot.items():
            try:
                current = self.settings.value(key, None)
            except Exception:
                ok = False
                continue
            if old is None:
                if current not in (None, ""):
                    ok = False
            elif str(current) != str(old):
                ok = False
        return ok

    # --- Secret snapshot / geri yükleme ---

    def _snapshot_api_key(self):
        try:
            return SecretSnapshot(True, self.credentials.get_api_key())
        except Exception:
            # Önceki durum BİLİNMİYOR; "yoktu" varsayılmaz.
            return SecretSnapshot(False)

    def _snapshot_password(self, username):
        try:
            return SecretSnapshot(True, self.credentials.get_password(username))
        except Exception:
            return SecretSnapshot(False)

    def _restore_api_key(self, snapshot):
        """Eski API anahtarını geri yazar ve READBACK ile doğrular."""
        if not snapshot.readable:
            return False
        try:
            if snapshot.present:
                self.credentials.set_api_key(snapshot.value)
            elif not self.credentials.delete_api_key():
                return False
            current = self.credentials.get_api_key()
        except Exception:
            return False
        if snapshot.present:
            return current == snapshot.value
        return not current

    def _restore_password(self, username, snapshot):
        """Eski parolayı DOĞRU kullanıcı için geri yazar ve doğrular."""
        if not snapshot.readable:
            return False
        try:
            if snapshot.present:
                self.credentials.set_password(username, snapshot.value)
            elif not self.credentials.delete_password(username):
                return False
            current = self.credentials.get_password(username)
        except Exception:
            return False
        if snapshot.present:
            return current == snapshot.value
        return not current

    # --- Okuma ---

    def load(self):
        """Gizli OLMAYAN ayarlar. Parola bu sözlükte ASLA bulunmaz."""
        language = self._text("language", DEFAULT_LANGUAGE)
        if language not in SUPPORTED_LANGUAGES:
            language = DEFAULT_LANGUAGE
        # Eski `after_download` anahtarı varsa YOK SAYILIR: okunmaz,
        # sözlüğe konmaz, silinmez (kullanıcı ayarlarına dokunulmaz).
        return {
            "username": self._text("username"),
            "language": language,
        }

    def load_api_key(self):
        """API anahtarı YALNIZCA güvenli depodan okunur."""
        self.migrate_legacy_api_key()
        try:
            return self.credentials.get_api_key() or ""
        except Exception:
            return ""

    def load_password(self, username=None):
        """Parolayı yalnızca kimlik deposundan okur."""
        if username is None:
            username = self.load()["username"]
        try:
            return self.credentials.get_password(username) or ""
        except Exception:
            return ""

    # --- Eski düz metin API anahtarı göçü ---

    def migrate_legacy_api_key(self, keep_existing=False):
        """QSettings'te kalmış düz metin API anahtarını güvenli depoya taşır.

        `keep_existing=True` iken legacy DEĞER TAŞINMAZ; yalnız düz metin
        anahtar silinir. Bu, kullanıcının aynı kaydetme işleminde AÇIKÇA yeni
        bir API anahtarı verdiği durumdur: eski değer yeni değerin üzerine
        yazılmamalıdır.

        Güvenli yazma başarısız olsa bile düz metin kopya BIRAKILMAZ (diskte
        kalan secret, kaybolan secret'tan kötüdür); ancak bu durum
        `secure_ok=False` ile açıkça bildirilir ve BAŞARI sayılmaz.
        """
        key = self._key(LEGACY_API_KEY_KEY)
        try:
            present = self.settings.value(key, None) is not None
        except Exception:
            present = False
        if not present:
            return MigrationResult(performed=False)

        legacy = self._text(LEGACY_API_KEY_KEY)
        storage = SECRETS_NONE
        secure_ok = True
        if legacy and not keep_existing:
            try:
                storage = self.credentials.set_api_key(legacy)
            except Exception:
                # Secret HİÇBİR yere yazılamadı. Bunu "oturum belleği"
                # gibi göstermek kullanıcıyı yanıltırdı.
                storage = SECRETS_NONE
                secure_ok = False

        plaintext_removed = self._remove_key(key)
        result = MigrationResult(True, storage, secure_ok, plaintext_removed)
        if result.failed:
            self._migration_failed = True
        return result

    # --- Yazma ---

    def save(self, values):
        """Ayarları TEK BİR İŞLEM olarak yazar: ya hepsi ya hiçbiri.

        Sıra:

        0. Legacy düz metin anahtar göçü (kullanıcı açık bir anahtar
           verdiyse eski değer TAŞINMAZ, yalnız düz metin silinir).
        1. Dokunulacak secret'ların İŞLEM ÖNCESİ durumu okunur. Önceki durum
           OKUNAMIYORSA işleme hiç başlanmaz: güvenli geri alma garanti
           edilemeyeceği için mevcut credential'a dokunulmaz.
        2. Secret'lar yazılır/silinir; her değişiklik için doğrulanabilir bir
           geri alma kaydedilir.
        3. Bir secret adımı bile başarısızsa QSettings'e HİÇ DOKUNULMAZ ve
           yapılan secret değişiklikleri geri alınır.
        4. QSettings yazılır ve `status()` ile doğrulanır.
        5. Eski kullanıcının credential'ı temizlenir. Temizlenemezse işlem
           kabul edilmez ve QSettings dâhil her şey geri alınır.

        Kabul edilen YALNIZCA iki sonuç vardır: tam kalıcı başarı ve gerçek
        session-memory fallback'i.

        Boş parola kayıtlı parolayı SİLMEZ (alan her açılışta boş gelir).
        Boş API anahtarı ise AÇIK bir silme isteğidir.
        """
        values = dict(values or {})
        explicit_api_key = "api_key" in values

        migration = self.migrate_legacy_api_key(keep_existing=explicit_api_key)
        migration_ok = migration.ok and not self._migration_failed

        previous_username = self.load()["username"]
        new_username = values.get("username")
        if new_username is None:
            new_username = previous_username
        new_username = str(new_username or "")

        secret_storage = SECRETS_NONE

        def record(storage):
            nonlocal secret_storage
            if storage == SECRETS_SESSION_ONLY:
                secret_storage = SECRETS_SESSION_ONLY
            elif (storage == SECRETS_PERSISTENT
                  and secret_storage == SECRETS_NONE):
                secret_storage = SECRETS_PERSISTENT

        if migration.performed:
            record(migration.storage)

        undo = []

        def rollback():
            """Yapılmış secret değişikliklerini ters sırayla geri alır."""
            ok = True
            for action in reversed(undo):
                try:
                    if not action():
                        ok = False
                except Exception:
                    ok = False
            return ok

        def rejected(secrets_saved=True, cleanup_ok=True, rollback_ok=True):
            return SettingsSaveResult(
                False, secrets_saved=secrets_saved, cleanup_ok=cleanup_ok,
                migration_ok=migration_ok, rollback_ok=rollback_ok,
                secret_storage=secret_storage)

        # 1) İşlem öncesi secret durumu — okunamıyorsa HİÇ BAŞLAMA.
        password = values.get("password") or ""
        api_snapshot = self._snapshot_api_key() if explicit_api_key else None
        password_snapshot = (self._snapshot_password(new_username)
                             if password else None)
        for snapshot in (api_snapshot, password_snapshot):
            if snapshot is not None and not snapshot.readable:
                # Önceki durum bilinmiyor: mevcut credential'a DOKUNULMAZ.
                return rejected(secrets_saved=False)

        # 2) Secret yazma/silme
        secrets_saved = True
        if explicit_api_key:
            api_key = str(values.get("api_key") or "")
            if api_key:
                try:
                    record(self.credentials.set_api_key(api_key))
                    undo.append(lambda: self._restore_api_key(api_snapshot))
                    # Kullanıcı yeni anahtarı girdi: kayıp göç kapandı.
                    self._migration_failed = False
                    migration_ok = migration.ok
                except Exception:
                    secrets_saved = False
            elif api_snapshot.present:
                # Alanı temizlemek AÇIK bir silme isteğidir.
                try:
                    if self.credentials.delete_api_key():
                        undo.append(
                            lambda: self._restore_api_key(api_snapshot))
                    else:
                        secrets_saved = False
                except Exception:
                    secrets_saved = False

        if password and secrets_saved:
            try:
                record(self.credentials.set_password(new_username, password))
                undo.append(
                    lambda: self._restore_password(new_username,
                                                   password_snapshot))
            except Exception:
                secrets_saved = False

        # 3) Secret adımı eksikse QSettings'e HİÇ dokunulmaz.
        if not secrets_saved:
            return rejected(secrets_saved=False, rollback_ok=rollback())
        if not migration_ok:
            # Anahtar kaybolmuş ve kullanıcı yenisini vermemiş: gizli olmayan
            # değişiklikler de kabul edilmiş gibi yazılmaz.
            return rejected(rollback_ok=rollback())

        # 4) Gizli OLMAYAN ayarlar — önce snapshot, sonra yazma.
        names = [name for name in ("username", "language")
                 if name in values]
        snapshot = self._snapshot(names)
        try:
            if "username" in values:
                self.settings.setValue(self._key("username"), new_username)
            if "language" in values:
                language = str(values.get("language") or "")
                if language not in SUPPORTED_LANGUAGES:
                    language = DEFAULT_LANGUAGE
                self.settings.setValue(self._key("language"), language)
            # `after_download` gönderilse bile YAZILMAZ (eski çağıranlar
            # için tolere edilir, davranışı etkilemez).
            settings_saved = self._settings_ok()
        except Exception:
            settings_saved = False

        if not settings_saved:
            rollback_ok = self._restore(snapshot)
            if not rollback():
                rollback_ok = False
            return rejected(rollback_ok=rollback_ok)

        # 5) Eski kullanıcının credential'ı temizlenir; sonucu YOK SAYILMAZ.
        username_changed = (previous_username
                            and previous_username != new_username)
        if username_changed:
            try:
                cleaned = bool(
                    self.credentials.delete_password(previous_username))
            except Exception:
                cleaned = False
            if not cleaned:
                # Eski kayıt duruyor: yeni durumu commit etmek iki target'ı
                # birden sahipsiz bırakırdı. İşlem TAMAMEN geri alınır.
                rollback_ok = self._restore(snapshot)
                if not rollback():
                    rollback_ok = False
                return rejected(cleanup_ok=False, rollback_ok=rollback_ok)

        return SettingsSaveResult(
            True, secrets_saved=True, cleanup_ok=True,
            migration_ok=migration_ok, rollback_ok=True,
            secret_storage=secret_storage)

    def clear_password(self, username=None):
        if username is None:
            username = self.load()["username"]
        try:
            return bool(self.credentials.delete_password(username))
        except Exception:
            return False

    def clear_api_key(self):
        try:
            return bool(self.credentials.delete_api_key())
        except Exception:
            return False
