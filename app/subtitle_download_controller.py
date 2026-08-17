# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Altyazı indirme / kaydetme / MPV'ye uygulama denetleyicisi.

TEK akış vardır: **İndir ve Uygula**.

    seçili kart → file_id → client.download_link(file_id)
    → güvenilir HTTPS OpenSubtitles URL kontrolü → client.fetch(url)
    → SRT doğrulama + UTF-8 dönüşümü → SubtitleStore.save(hedef)
    → SubtitleSession.apply(...)

Kurallar:

- Hedef ad `subtitle_target_path()` ile hesaplanır: videonun klasöründe
  `<video adı>.srt`. Uzak dosya adı, dil eki ve `.1`/`(1)` türevleri
  KULLANILMAZ.
- Kullanıcıya klasör, dosya adı veya ÜZERİNE YAZMA onayı SORULMAZ.
  Hedef, videodan tek anlamlı biçimde türediği için "hangi dosya?"
  sorusu yoktur; eski `confirm_overwrite` kancası kaldırılmıştır.
- Üzerine yazma yalnız DOĞRULANMIŞ yeni içerikle ve atomik olarak yapılır
  (`SubtitleStore.save`: geçici dosya + flush/fsync + `os.replace`).
  Geçersiz/boş/HTML gövde mevcut sağlam `.srt`'yi BOZMAZ.
- Ağ ve dosya yazma işi worker thread'inde; MPV/Qt işleri ana thread'de.
- Zorla thread sonlandırma YOKTUR; iptal kooperatiftir.
- Controller dialog'a DEĞİL, daha uzun yaşayan owner'a bağlanır.
- Kullanıcıya yalnızca güvenli metin gösterilir; ham gövde/gizli veri sızmaz.
"""
import inspect

from PyQt6.QtCore import Qt, QEventLoop, QObject, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication

from app.opensubtitles import (
    SubtitleServiceError, UntrustedUrlError, is_trusted_download_url,
    safe_message)
from app.translate import tr_mark
from app.subtitle_service import (
    NotSrtError, SubtitleStore, SubtitleSession, SubtitleWriteError,
    TRACK_WAIT_ATTEMPTS, TRACK_WAIT_INTERVAL_S, subtitle_target_path)

# Her polling adımının GERÇEK süresi. Toplam üst sınır:
# TRACK_WAIT_ATTEMPTS x TRACK_WAIT_INTERVAL_MS ≈ 400 ms.
TRACK_WAIT_INTERVAL_MS = max(1, int(round(TRACK_WAIT_INTERVAL_S * 1000)))

# Modul duzeyi durum metinleri: yalniz ISARETLENIR; ceviri TEK sinirda,
# `set_operation_status()` icinde yapilir.
STATUS_DOWNLOADING = tr_mark("Altyazı indiriliyor…")
STATUS_DOWNLOADED = tr_mark("Altyazı indirildi.")
STATUS_APPLIED = tr_mark("Altyazı indirildi ve uygulandı.")
# Hedef videodan tek anlamlı biçimde türer ve kullanıcı zaten "indir"
# demiştir: üzerine yazma AYRI bir soru DEĞİLDİR. Store'un fail-closed
# kuralı korunsun diye açık ve tek yerde tanımlı bir "evet" verilir.


def _always_overwrite(_target):
    return True

STATUS_PARTIAL = tr_mark(
    "Altyazı indirildi ancak oynatıcıya uygulanamadı.")
STATUS_GENERIC_ERROR = tr_mark("Altyazı indirilemedi.")


class QtDownloadWorker(QObject):
    """Ağ indirmesini ve dosyaya yazmayı worker thread'inde yürütür."""

    saved = pyqtSignal(int, str)
    failed = pyqtSignal(int, str)
    finished = pyqtSignal()

    def __init__(self, client, file_id, target, store, generation):
        super().__init__()
        self._client = client
        self._file_id = file_id
        self._target = target
        self._store = store
        self._generation = generation
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def is_cancelled(self):
        return self._cancelled

    def run(self):
        try:
            if self._cancelled:
                return
            # POST /download bir kez; istemci katmanı retry yapmaz.
            link = self._client.download_link(self._file_id)
            if self._cancelled:
                return
            if not link or not is_trusted_download_url(link):
                raise UntrustedUrlError("untrusted link")
            payload = self._client.fetch(link)
            if self._cancelled:
                return
            # Yazma yalnız BURADA, indirme ve doğrulama tamamlandıktan
            # sonra yapılır: geçersiz gövde mevcut dosyaya hiç ulaşmaz.
            written = self._store.save(self._target, payload,
                                       confirm=_always_overwrite)
            if self._cancelled:
                return
            if not written:
                self.failed.emit(self._generation, STATUS_GENERIC_ERROR)
                return
            self.saved.emit(self._generation, self._target)
        except (SubtitleServiceError, UntrustedUrlError) as error:
            if not self._cancelled:
                self.failed.emit(self._generation, safe_message(error))
        except (NotSrtError, SubtitleWriteError):
            if not self._cancelled:
                # Ham içerik/sunucu gövdesi ASLA mesaja konmaz.
                self.failed.emit(self._generation, STATUS_GENERIC_ERROR)
        except Exception:
            if not self._cancelled:
                self.failed.emit(self._generation, STATUS_GENERIC_ERROR)
        finally:
            self.finished.emit()


class SubtitleDownloadController(QObject):
    """Tek akış: "İndir ve Uygula"."""

    def __init__(self, dialog, client, player=None,
                 store=None, session=None, parent=None, owner=None):
        lifecycle_owner = parent or owner or dialog.parent() or None
        super().__init__(lifecycle_owner)
        self.dialog = dialog
        self.client = client
        self.player = player
        self.store = store or SubtitleStore()
        self.session = session or SubtitleSession(store=self.store)

        self._thread = None
        self._worker = None
        self._generation = 0
        self._cancelled = False
        # Apply beklemesi ana thread'de İÇ İÇE bir event loop çalıştırır;
        # bu sırada düğmeler/kısayollar yeni bir indirme başlatamamalıdır.
        self._applying = False

        dialog.apply_button.clicked.connect(self.download_and_apply)
        dialog.finished.connect(lambda _code: self.cancel())
        dialog.destroyed.connect(self._on_dialog_destroyed)

    # --- Durum ---

    def generation(self):
        return self._generation

    def is_cancelled(self):
        return self._cancelled

    def thread_is_running(self):
        return bool(self._thread is not None and self._thread.isRunning())

    def is_idle(self):
        return self._thread is None and self._worker is None

    def is_applying(self):
        """MPV apply beklemesi ANA thread'de sürüyor mu?"""
        return self._applying

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

    # --- Genel akış ---

    def download_and_apply(self):
        """Tek kullanıcı eylemi: indir, kaydet, uygula."""
        return self._start()

    def _target_path(self):
        media = dict((self.dialog.media if self.dialog else None) or {})
        video = media.get("file_name", "")
        if not video:
            return ""
        # Uzak dosya adı bilinçli olarak YOK SAYILIR.
        return subtitle_target_path(video)

    def _start(self):
        dialog = self._ui()
        # `is_applying()` ayrıca kontrol edilir: apply'ın iç içe event loop'u
        # sırasında worker thread çoktan bitmiş (is_idle True) olabilir.
        if dialog is None or not self.is_idle() or self._applying:
            return False
        result = dialog.selected_result()
        if not result:
            return False
        file_id = result.get("file_id")
        target = self._target_path()
        if file_id is None or not target:
            return False

        # ÜZERİNE YAZMA ONAYI YOKTUR. Hedef videodan türer ve kullanıcı
        # zaten indirmeyi istemiştir; mevcut dosya ancak DOĞRULANMIŞ yeni
        # içerikle, atomik biçimde değişir.
        self._generation += 1
        self._cancelled = False
        dialog.set_operation_status(STATUS_DOWNLOADING)
        dialog.apply_button.setEnabled(False)

        self._thread = QThread()
        self._worker = QtDownloadWorker(self.client, file_id, target,
                                        self.store, self._generation)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.saved.connect(self._on_saved)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._on_thread_finished)
        self._thread.start()
        return True

    # --- Worker sinyalleri (ana thread) ---

    def _is_current(self, generation):
        return generation == self._generation and not self._cancelled

    def _on_saved(self, generation, target):
        if not self._is_current(generation):
            return
        # Dil, apply'dan ÖNCE okunur: iç içe event loop sırasında dialog
        # kapanırsa seçim erişilemez olur.
        language = self._selected_language()
        self._applying = True
        try:
            applied = self._apply_to_player(target, generation,
                                            language=language)
        finally:
            self._applying = False

        # Bekleme sırasında olaylar işlendiği için kullanıcı dialogu
        # kapatmış ya da yok etmiş olabilir; durum YENİDEN sorulur.
        if not self._is_current(generation):
            # İptal edildi: ne başarı ne kısmi başarı yazılır.
            self._sync_action_buttons()
            return
        dialog = self._ui()
        if dialog is not None:
            dialog.set_operation_status(
                STATUS_APPLIED if applied else STATUS_PARTIAL)
        self._sync_action_buttons()

    def _selected_language(self):
        """Seçili sonucun dil kodu; MPV parça metadata'sı için kullanılır.

        Dosya ADI etkilenmez — hedef ad her zaman video adı + `.srt`'dir.
        """
        dialog = self._ui()
        if dialog is None:
            return ""
        try:
            result = dialog.selected_result() or {}
        except RuntimeError:
            return ""
        return str(result.get("language") or "").strip()

    @staticmethod
    def _supported_apply_kwargs(apply_callable):
        """`apply()` imzasının GERÇEKTEN kabul ettiği isteğe bağlı adlar.

        Desteklenmeyen adlar çağrıdan ÖNCE elenir. Böylece `apply()`
        GÖVDESİNDEN gelen bir `TypeError` "imza uyuşmazlığı" sanılıp aynı
        altyazı ikinci kez uygulanmaya çalışılmaz.
        """
        optional = ("wait", "attempts", "is_cancelled", "language", "title")
        try:
            parameters = inspect.signature(apply_callable).parameters
        except (TypeError, ValueError):
            # İmza okunamıyorsa en güvenli ortak alt küme kullanılır.
            return {"wait", "attempts"}
        if any(p.kind == inspect.Parameter.VAR_KEYWORD
               for p in parameters.values()):
            return set(optional)
        return {name for name in optional if name in parameters}

    def _apply_to_player(self, target, generation=None, language=None):
        """MPV işi ANA thread'de yapılır; bekleme Qt dostu ve sınırlıdır.

        `apply()` TAM OLARAK BİR KEZ çağrılır; hata durumunda tekrar
        denenmez.
        """
        if self.player is None:
            return False
        if generation is None:
            generation = self._generation
        supported = self._supported_apply_kwargs(self.session.apply)
        candidates = {
            "wait": self._qt_wait,
            "attempts": TRACK_WAIT_ATTEMPTS,
            "is_cancelled": lambda: not self._is_current(generation),
            "language": language,
        }
        kwargs = {name: value for name, value in candidates.items()
                  if name in supported}
        try:
            return bool(self.session.apply(self.player, target, **kwargs))
        except Exception:
            # TypeError dâhil her hata TEK çağrı sonrası False'a dönüşür.
            return False

    def _qt_wait(self):
        """Polling adımı başına GERÇEK süre harcar; ana thread'i UYUTMAZ.

        `processEvents(..., 10)` yalnızca ÜST SINIR verir: olay kuyruğu boşsa
        hemen döner ve `TRACK_WAIT_ATTEMPTS` denemesi birkaç milisaniyede
        tükenirdi (ölçüldü: 40 deneme ≈ 8 ms). Gerçek MPV `track_list`'i
        onlarca ms sonra güncellediği için doğru track kaçırılıyordu.

        Burada KISA ÖMÜRLÜ yerel bir `QEventLoop`, `PreciseTimer` ile
        ~`TRACK_WAIT_INTERVAL_MS` sonra kapatılır. Böylece hem gerçek zaman
        geçer hem de UI olayları işlenmeye devam eder. `time.sleep` YOKTUR.
        Kalıcı/genel timer eklenmez: loop ve timer yalnız aktif apply
        beklemesi boyunca yaşar.
        """
        app = QApplication.instance()
        if app is None:
            return
        loop = QEventLoop()
        QTimer.singleShot(TRACK_WAIT_INTERVAL_MS, Qt.TimerType.PreciseTimer,
                          loop.quit)
        loop.exec()

    def _on_failed(self, generation, message):
        if not self._is_current(generation):
            return
        dialog = self._ui()
        if dialog is not None:
            dialog.show_error(message or STATUS_GENERIC_ERROR)

    def _on_dialog_destroyed(self, *_args):
        self.dialog = None
        self.cancel()

    def _on_thread_finished(self):
        self._thread = None
        self._worker = None
        # NOT: bu slot apply'ın iç içe event loop'u SIRASINDA çalışabilir.
        # Düğmeler o anda açılırsa kullanıcı apply bitmeden yeni indirme
        # başlatabilirdi; bu yüzden karar tek noktada verilir.
        self._sync_action_buttons()

    def _sync_action_buttons(self):
        """Düğmeler yalnız iş TAMAMEN bittiğinde ve seçim varsa açılır."""
        if not self.is_idle() or self._applying:
            return
        dialog = self._ui()
        if dialog is None:
            return
        has_selection = dialog.selected_result() is not None
        dialog.apply_button.setEnabled(has_selection)

    # --- İptal / kapanış ---

    def cancel(self):
        self._cancelled = True
        for obj, method in ((self._worker, "cancel"),
                            (self._thread, "requestInterruption")):
            if obj is not None:
                try:
                    getattr(obj, method)()
                except RuntimeError:
                    pass

    def shutdown(self, wait_ms=5000):
        """Yalnız test/sonlandırma yardımcısı; GUI kapanış yolunda çağrılmaz."""
        self.cancel()
        thread = self._thread
        if thread is None:
            return True
        try:
            thread.quit()
            finished = thread.wait(wait_ms)
        except RuntimeError:
            return True
        app = QApplication.instance()
        if app is not None:
            app.processEvents()
        return finished
