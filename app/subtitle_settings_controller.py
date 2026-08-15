"""Altyazı Merkezi ayar çekmecesini kalıcı depoya bağlayan denetleyici.

Görsel kabuk (`app.subtitle_center`) kalıcılık BİLMEZ; bu modül dişli
çekmecesindeki alanlarla `SubtitleSettingsStore` arasındaki tek köprüdür.

Yaşam döngüsü kuralları (diğer altyazı controller'larıyla aynı):

- Controller dialog'a parent'lanmaz; dialog yok edilse bile nesne yaşar.
- Dialog yok edildikten sonra hiçbir alan okunmaya çalışılmaz; işlemler
  sessizce ve HATASIZ atlanır.
- Parola alanı geri yüklemede DOLDURULMAZ ve kaydettikten sonra TEMİZLENİR;
  düz parola arayüzde asılı kalmaz. API anahtarı güvenli depodan MASKELİ
  alana geri yüklenebilir.
- Kullanıcıya gösterilen durum metni anahtar/parola/kullanıcı adı/target ya
  da sistem hata metni İÇERMEZ.
- Kalıcılık sözü gerçeğe uygundur: secret yalnız oturum belleğine
  düştüyse kullanıcı bunu görür.
"""
from PyQt6.QtCore import QObject, pyqtSignal

from app.subtitle_settings import DEFAULT_LANGUAGE

STATUS_SAVED = "Ayarlar kaydedildi."
STATUS_SAVED_SESSION_ONLY = ("Ayarlar kaydedildi; gizli bilgiler yalnız bu "
                             "oturumda kullanılacak.")
STATUS_SAVE_FAILED = "Ayarlar kaydedilemedi."
STATUS_ROLLBACK_FAILED = ("Ayarlar kaydedilemedi; güvenli bilgiler eski "
                          "durumuna döndürülemedi.")
STATUS_SECRETS_FAILED = ("Ayarlar kaydedilemedi; gizli bilgiler güvenli "
                         "depoya yazılamadı.")
STATUS_CLEANUP_FAILED = ("Ayarlar kaydedilemedi; eski güvenli bilgiler "
                         "temizlenemedi.")
STATUS_MIGRATION_FAILED = ("API anahtarı güvenli depoya taşınamadı; "
                           "yeniden girin.")
# OpenSubtitles REST API'de anahtar ZORUNLUDUR; hesap bilgileri yalnızca
# daha yüksek kota içindir. Kullanıcı yalnız kullanıcı adı/parola girip
# arama yapmayı denemişti.
STATUS_API_KEY_REQUIRED = "API anahtarı zorunludur."
STATUS_ACCOUNT_INCOMPLETE = ("Hesapla giriş için kullanıcı adı ve parolanın "
                             "ikisi de gerekir; ya ikisini de girin ya da "
                             "ikisini de boş bırakın.")

class SubtitleSettingsController(QObject):
    """Çekmece alanları ↔ kalıcı ayar deposu."""

    # Kayıt KABUL EDİLDİĞİNDE yayılır (tam kalıcı ya da session-only).
    # Reddedilen kayıtta yayılmaz. Sinyal HİÇBİR gizli değer taşımaz;
    # dinleyiciler yalnız "artık yeni ayarlar geçerli" bilgisini alır.
    accepted = pyqtSignal()

    def __init__(self, dialog, store, parent=None, owner=None):
        # ÖNEMLİ: dialog parent OLARAK kullanılmaz.
        lifecycle_owner = parent or owner or dialog.parent() or None
        super().__init__(lifecycle_owner)
        self.dialog = dialog
        self.store = store

        dialog.settings_save_button.clicked.connect(self.save)
        # "Vazgeç" düzenlemeleri atar; çekmeceyi kapatma işini dialog yapar.
        dialog.settings_cancel_button.clicked.connect(self.revert)
        dialog.destroyed.connect(self._on_dialog_destroyed)

        self.revert()

    # --- Dialog erişimi ---

    def _ui(self):
        """Dialog yaşıyorsa döner; yok edilmişse None."""
        dialog = self.dialog
        if dialog is None:
            return None
        try:
            dialog.objectName()
        except RuntimeError:
            self.dialog = None
            return None
        return dialog

    def _on_dialog_destroyed(self, *_args):
        self.dialog = None

    # --- Depodan arayüze ---

    def _has_stored_password(self, username):
        """Parola alanı boş ama KAYITLI parola varsa hesap eksik sayılmaz.

        Parola hiçbir zaman forma geri doldurulmaz; kullanıcı yalnızca
        kullanıcı adını değiştirmiyorsa boş alan "değiştirme" demektir.
        """
        if not username:
            return False
        loader = getattr(self.store, "load_password", None)
        if not callable(loader):
            return False
        try:
            return bool(loader(username))
        except Exception:
            return False

    def _stored_api_key(self):
        loader = getattr(self.store, "load_api_key", None)
        if not callable(loader):
            return ""
        try:
            return loader() or ""
        except Exception:
            return ""

    def revert(self):
        """Kayıtlı değerleri çekmeceye yükler; kaydedilmemiş düzenlemeler gider."""
        dialog = self._ui()
        if dialog is None:
            return False
        values = self.store.load()
        # API anahtarı QSettings'te DEĞİL, güvenli depodadır.
        dialog.api_key_field.setText(self._stored_api_key())
        dialog.username_field.setText(values["username"])
        # Parola ASLA geri yüklenmez.
        dialog.password_field.clear()
        dialog.settings_language_box.setCurrentText(values["language"])
        # Varsayılan dil arama satırında da seçili gelir.
        dialog.language_box.setCurrentText(values["language"])
        return True

    # --- Arayüzden depoya ---

    def save(self):
        """Çekmece değerlerini kalıcı yapar. Dialog yoksa sessizce atlar.

        Dönen değer kaydın KABUL EDİLİP edilmediğidir: tam başarıda ve
        yalnız-oturum durumunda True, gizli olmayan ayarlar bile
        yazılamadığında False. Başarısızlıkta form OLDUĞU GİBİ bırakılır ki
        kullanıcı yeniden deneyebilsin.
        """
        dialog = self._ui()
        if dialog is None:
            return False

        # ÖN DOĞRULAMA: eksik/çelişkili girdi hiç depoya ulaşmaz. Form
        # olduğu gibi korunur ki kullanıcı düzeltip yeniden denesin.
        api_key = dialog.api_key_field.text().strip()
        username = dialog.username_field.text().strip()
        password = dialog.password_field.text()
        if not api_key:
            dialog.set_operation_status(STATUS_API_KEY_REQUIRED)
            return False
        if bool(username) != bool(password) and not self._has_stored_password(
                username):
            dialog.set_operation_status(STATUS_ACCOUNT_INCOMPLETE)
            return False

        language = dialog.settings_language_box.currentText()
        if not language:
            language = DEFAULT_LANGUAGE
        result = self.store.save({
            "api_key": api_key,
            "username": username,
            "password": password,
            "language": language,
        })

        if not getattr(result, "accepted", bool(result)):
            # Hiçbir şey commit edilmedi: kalıcılık sözü VERİLMEZ, parola
            # alanı korunur ve arama dili DEĞİŞMEZ.
            dialog.set_operation_status(self._rejected_status(result))
            return False

        # Düz parola arayüzde asılı kalmaz.
        dialog.password_field.clear()
        # Yeni varsayılan dil arama satırına YALNIZCA kabul edilen kayıttan
        # sonra yansır.
        dialog.language_box.setCurrentText(language)
        dialog.set_operation_status(
            STATUS_SAVED_SESSION_ONLY
            if getattr(result, "session_only", False) else STATUS_SAVED)
        # Yalnız KABUL EDİLEN kayıtta yayılır; dinleyiciler (örn. istemci
        # yenileme) düğme tıklamasına değil bu sonuca bağlanmalıdır.
        self.accepted.emit()
        return True

    # --- Sonuç → mesaj matrisi ---

    @staticmethod
    def _rejected_status(result):
        """Kayıt KABUL EDİLMEDİ; nedeni en ciddiden en hafife doğru seçilir.

        Her durumda TEK mesaj gösterilir ve hiçbiri secret, kullanıcı adı,
        target, sistem hata metni veya yerel yol içermez.
        """
        if not getattr(result, "rollback_ok", True):
            return STATUS_ROLLBACK_FAILED
        if not getattr(result, "secrets_saved", True):
            return STATUS_SECRETS_FAILED
        if not getattr(result, "migration_ok", True):
            return STATUS_MIGRATION_FAILED
        if not getattr(result, "cleanup_ok", True):
            return STATUS_CLEANUP_FAILED
        return STATUS_SAVE_FAILED


__all__ = ["SubtitleSettingsController", "STATUS_SAVED",
           "STATUS_SAVED_SESSION_ONLY", "STATUS_SAVE_FAILED",
           "STATUS_ROLLBACK_FAILED", "STATUS_SECRETS_FAILED",
           "STATUS_CLEANUP_FAILED", "STATUS_MIGRATION_FAILED"]
