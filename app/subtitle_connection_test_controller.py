"""«Bağlantıyı Test Et» denetleyicisi.

Kullanıcı ayarları kaydetmeden önce API anahtarının/hesabının çalıştığını
görebilmeli. Kurallar:

- Ağ işi ASLA UI thread'inde çalışmaz (QThread + kooperatif iptal).
- KOTA TÜKETİLMEZ: `/download` çağrılmaz. Anahtar-only testte sabit ve
  sentetik bir arama yapılır; hesap bilgileri tamsa `login()` denenir.
- Kullanıcı adı/parolanın YALNIZ BİRİ doluysa ağa hiç çıkılmaz.
- Test KALICI ayar yazmaz; geçici bir istemci kurulur.
- Düğme aktif testte ikinci isteği başlatmaz (login rate limit'e saygı).
- Dialog kapanırken worker fail-closed yaşam döngüsüyle drain edilir;
  `terminate()` YOKTUR.
- Kullanıcıya yalnız `safe_message()`; anahtar/parola/token sızmaz.
"""
from PyQt6.QtCore import QObject, QThread, pyqtSignal

from app.opensubtitles import (
    AuthError, OpenSubtitlesClient, SubtitleServiceError, safe_message)
from app.translate import tr_mark

# Modul duzeyi durum metinleri: yalniz ISARETLENIR; ceviri TEK sinirda,
# `set_operation_status()` icinde yapilir.
STATUS_NEEDS_KEY = tr_mark("Önce API anahtarını girin.")
STATUS_PARTIAL_ACCOUNT = tr_mark(
    "Kullanıcı adı ve parolanın ikisini de girin ya da ikisini de boş "
    "bırakın.")
STATUS_TESTING = tr_mark("Bağlantı test ediliyor…")
STATUS_OK = tr_mark("Bağlantı başarılı.")
STATUS_AUTH_FAILED = tr_mark(
    "API anahtarı, kullanıcı adı veya parola doğrulanamadı.")
STATUS_FAILED = tr_mark("Bağlantı doğrulanamadı.")

# Kota tüketmeyen, sabit ve kamusal sentetik sorgu.
PROBE_QUERY = "The Matrix"
PROBE_LANGUAGE = "tr"


class _TestWorker(QObject):
    """Login ya da sentetik arama; indirme ASLA çağrılmaz."""

    done = pyqtSignal(int, bool, str)
    finished = pyqtSignal()

    def __init__(self, client, use_login, generation):
        super().__init__()
        self._client = client
        self._use_login = bool(use_login)
        self._generation = int(generation)
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            if self._cancelled:
                return
            if self._use_login:
                self._client.login()
                ok = bool(getattr(self._client, "has_token", lambda: True)())
            else:
                self._client.search(query=PROBE_QUERY,
                                    languages=PROBE_LANGUAGE)
                ok = True
            if not self._cancelled:
                self.done.emit(self._generation, ok,
                               STATUS_OK if ok else STATUS_FAILED)
        except AuthError:
            if not self._cancelled:
                self.done.emit(self._generation, False, STATUS_AUTH_FAILED)
        except SubtitleServiceError as error:
            if not self._cancelled:
                # Timeout / rate-limit / ağ metinleri mevcut güvenli
                # katmandan gelir.
                self.done.emit(self._generation, False, safe_message(error))
        except Exception:
            if not self._cancelled:
                self.done.emit(self._generation, False, STATUS_FAILED)
        finally:
            self.finished.emit()


class SubtitleConnectionTestController(QObject):
    """Ayar penceresindeki «Bağlantıyı Test Et» düğmesini yürütür."""

    def __init__(self, dialog, client_factory=None, settings_store=None,
                 parent=None, owner=None):
        # Controller dialog'a parent'lanmaz; çalışan thread sahipliği sürer.
        lifecycle_owner = parent or owner or dialog.parent() or None
        super().__init__(lifecycle_owner)
        self.dialog = dialog
        self.client_factory = client_factory or self._default_client_factory
        # Parola forma geri DOLDURULMAZ (güvenlik kararı). Kayıtlı parolası
        # olan kullanıcı yine de bağlantısını test edebilmeli; bu yüzden
        # depo enjekte edilir ve parola YALNIZCA bellekte kullanılır.
        self.settings_store = settings_store
        self._thread = None
        self._worker = None
        self._generation = 0
        self._cancelled = False

        request = getattr(dialog, "connection_test_requested", None)
        if request is not None:
            request.connect(self.start_test)
        dialog.finished.connect(lambda _code: self.cancel())
        dialog.destroyed.connect(self._on_dialog_destroyed)

    @staticmethod
    def _default_client_factory(**kwargs):
        return OpenSubtitlesClient(**kwargs)

    # --- Durum ---

    def is_idle(self):
        return self._thread is None and self._worker is None

    def _ui(self):
        dialog = self.dialog
        if dialog is None:
            return None
        try:
            dialog.objectName()
        except RuntimeError:
            self.dialog = None
            return None
        return dialog

    def _status(self, text):
        dialog = self._ui()
        if dialog is not None:
            dialog.set_operation_status(text)

    def _set_button_enabled(self, enabled):
        """Test sürerken Kaydet de kilitlenir.

        Aksi halde iki farklı credential seti (formdaki ile test edilen)
        eşzamanlı işlem başlatabilirdi.
        """
        dialog = self._ui()
        if dialog is None:
            return
        for name in ("test_button", "settings_save_button"):
            button = getattr(dialog, name, None)
            if button is None:
                continue
            try:
                button.setEnabled(bool(enabled))
            except RuntimeError:
                pass

    def _stored_password_for(self, username):
        """Kayıtlı parola — YALNIZCA aynı kullanıcı adı için.

        Kullanıcı adı formda DEĞİŞTİRİLMİŞSE eski kullanıcının parolası
        ASLA kullanılmaz; aksi halde yanlış kimlikle ağa çıkılırdı.
        """
        store = self.settings_store
        if store is None or not username:
            return ""
        try:
            stored_username = (store.load() or {}).get("username", "")
        except Exception:
            return ""
        if not stored_username or stored_username != username:
            return ""
        try:
            return store.load_password(username) or ""
        except Exception:
            return ""

    # --- Test ---

    def start_test(self):
        dialog = self._ui()
        if dialog is None or not self.is_idle():
            return False

        api_key = dialog.api_key_field.text().strip()
        if not api_key:
            # AĞA ÇIKILMAZ ve kimlik deposu bile OKUNMAZ.
            self._status(STATUS_NEEDS_KEY)
            return False

        username = dialog.username_field.text().strip()
        password = dialog.password_field.text()
        if username and not password:
            # Parola alanı boş: aynı kullanıcının KAYITLI parolası varsa
            # kullanılır. Forma geri YAZILMAZ, yalnız bellekte kalır.
            password = self._stored_password_for(username)
        if bool(username) != bool(password):
            self._status(STATUS_PARTIAL_ACCOUNT)
            return False

        use_login = bool(username and password)
        # GEÇİCİ istemci: kalıcı ayar yazılmaz, cache kirletilmez.
        client = self.client_factory(api_key=api_key, username=username,
                                     password=password)

        self._generation += 1
        self._cancelled = False
        self._status(STATUS_TESTING)
        self._set_button_enabled(False)

        self._thread = QThread()
        self._worker = _TestWorker(client, use_login, self._generation)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.done.connect(self._on_done)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._on_thread_finished)
        self._thread.start()
        return True

    def _on_done(self, generation, ok, message):
        if generation != self._generation or self._cancelled:
            return  # BAYAT ya da iptal edilmiş sonuç.
        self._status(message)

    def _on_dialog_destroyed(self, *_args):
        self.dialog = None
        self.cancel()

    def _on_thread_finished(self):
        self._thread = None
        self._worker = None
        self._set_button_enabled(True)

    # --- İptal / kapanış ---

    def cancel(self):
        self._cancelled = True
        worker = self._worker
        if worker is not None:
            try:
                worker.cancel()
            except RuntimeError:
                pass

    def shutdown(self, wait_ms=5000):
        self.cancel()
        thread = self._thread
        if thread is None:
            return True
        try:
            thread.quit()
            finished = bool(thread.wait(wait_ms))
        except RuntimeError:
            return True
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None:
            app.processEvents()
        return finished
