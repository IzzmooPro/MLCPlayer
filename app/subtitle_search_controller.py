"""Altyazı Merkezi arama denetleyicisi: dialog ↔ çekirdek zinciri, QThread ile.

Bu modül arama ALGORİTMASINI İÇERMEZ. Tek arama davranışı kaynağı
`app.opensubtitles.SubtitleSearchWorker`'dır; buradaki Qt katmanı yalnızca
bir adapter'dır:

    QThread ──▶ QtSearchWorker (adapter)
                   └─▶ opensubtitles.SubtitleSearchWorker.run()
                          on_results ──▶ Qt `results` signal
                          on_error   ──▶ Qt `failed`  signal
                   cancel() ──▶ core.cancel()

Böylece çekirdekteki ileriki davranış değişiklikleri controller'a
kendiliğinden yansır.

Yaşam döngüsü kuralları:

- Ağ/arama işi ASLA ana Qt thread'inde çalışmaz.
- Zorla thread sonlandırma YOKTUR; iptal kooperatiftir.
- Controller dialog'a DEĞİL, daha uzun yaşayan bir owner'a bağlanır; dialog
  yok edilse bile thread sahipliği sürer ve referanslar `finished` gelene
  kadar korunur.
- Normal GUI kapanış yolu thread'i BEKLEMEZ; yalnızca iptal ister.

Bu modül ağ istemcisini kendisi oluşturmaz; `client` dışarıdan enjekte edilir.
"""
from PyQt6.QtCore import QObject, QThread, pyqtSignal

from app import opensubtitles
from app.opensubtitles import (
    SubtitleServiceError, build_search_plan, safe_message)

# Kullanıcıya teknik kod gösterilmez; çeviri burada yapılır.
LANGUAGE_CODES = {
    "Türkçe": "tr",
    "İngilizce": "en",
    "Almanca": "de",
    "Fransızca": "fr",
    "İspanyolca": "es",
}
DEFAULT_LANGUAGE_CODE = "tr"


class QtSearchWorker(QObject):
    """Çekirdek arama worker'ını QThread'e taşıyan ADAPTER.

    Arama sırası, normalize/filter/rank adımları burada YENİDEN
    UYGULANMAZ; hepsi çekirdek worker'ın sorumluluğundadır.
    """

    results = pyqtSignal(int, list)
    failed = pyqtSignal(int, str)
    finished = pyqtSignal()

    def __init__(self, client, plan, language, generation):
        super().__init__()
        self._language = language
        self._generation = generation
        self._emitted = False
        # Çekirdek worker sınıfı ÇALIŞMA ANINDA modülden okunur; böylece
        # testler monkeypatch ile gerçek delegasyonu doğrulayabilir.
        self._core = opensubtitles.SubtitleSearchWorker(
            client=client, plan=plan,
            on_results=self._forward_results,
            on_error=self._forward_error)

    @property
    def core(self):
        return self._core

    def cancel(self):
        self._core.cancel()

    def is_cancelled(self):
        return self._core.is_cancelled()

    def _forward_results(self, ranked):
        if self._core.is_cancelled():
            return
        self._emitted = True
        self.results.emit(self._generation, list(ranked or []))

    def _forward_error(self, message):
        if self._core.is_cancelled():
            return
        self._emitted = True
        self.failed.emit(self._generation, message)

    def run(self):
        """QThread.started ile çağrılır; worker thread'inde çalışır."""
        try:
            self._core.run(self._language)
            if not self._emitted and not self._core.is_cancelled():
                # Çekirdek hiçbir callback tetiklemediyse boş sonuç bildir.
                self.results.emit(self._generation, [])
        except SubtitleServiceError as error:
            if not self._core.is_cancelled():
                self.failed.emit(self._generation, safe_message(error))
        except Exception:
            if not self._core.is_cancelled():
                self.failed.emit(self._generation,
                                 safe_message(SubtitleServiceError()))
        finally:
            self.finished.emit()


class SubtitleSearchController(QObject):
    """Dialog ile arama çekirdeğini güvenli QThread yaşam döngüsüyle bağlar."""

    def __init__(self, dialog, client, parent=None, owner=None):
        # ÖNEMLİ: controller dialog'a parent'lanmaz. Dialog `deleteLater()`
        # ile yok edilse bile controller yaşamalı ve çalışan thread'i
        # sahiplenmeye devam etmelidir.
        lifecycle_owner = parent or owner or dialog.parent() or None
        super().__init__(lifecycle_owner)
        self.dialog = dialog
        self.client = client
        self._thread = None
        self._worker = None
        self._generation = 0
        self._cancelled = False

        dialog.search_button.clicked.connect(self.start_search)
        # Normal GUI yolu: yalnız iptal ister, BEKLEMEZ.
        dialog.finished.connect(lambda _code: self.cancel())
        dialog.destroyed.connect(self._on_dialog_destroyed)

    # --- Durum sorguları ---

    def generation(self):
        return self._generation

    def is_cancelled(self):
        return self._cancelled

    def thread_is_running(self):
        return bool(self._thread is not None and self._thread.isRunning())

    def is_idle(self):
        return self._thread is None and self._worker is None

    def selected_file_id(self):
        """Seçili kart YOKSA daima None. Eski kimlik hatırlanmaz."""
        dialog = self.dialog
        if dialog is None:
            return None
        try:
            result = dialog.selected_result()
        except RuntimeError:
            return None
        return result.get("file_id") if result else None

    # --- Arama ---

    def _language_code(self):
        return LANGUAGE_CODES.get(self.dialog.language_box.currentText(),
                                  DEFAULT_LANGUAGE_CODE)

    def _parsed_from_dialog(self):
        media = dict(self.dialog.media or {})
        parsed = {
            "title": self.dialog.title_field.text().strip()
            or media.get("title", ""),
            "is_series": bool(media.get("is_series")),
            "season": None,
            "episode": None,
            "year": media.get("year"),
        }
        if parsed["is_series"]:
            for key, field in (("season", self.dialog.season_field),
                               ("episode", self.dialog.episode_field)):
                text = field.text().strip()
                parsed[key] = int(text) if text.isdigit() else media.get(key)
        return parsed

    def start_search(self):
        """Aramayı başlatır. İlk arama sürerken ikincisi başlatılmaz."""
        if not self.is_idle() or self.dialog is None:
            return False

        media = dict(self.dialog.media or {})
        language = self._language_code()
        plan = build_search_plan(
            video_path=media.get("file_name", ""),
            movie_hash=media.get("movie_hash") or "",
            file_size=media.get("file_size") or 0,
            parsed=self._parsed_from_dialog(),
            language=language)

        self._generation += 1
        self._cancelled = False
        self.dialog.show_loading()
        self.dialog.search_button.setEnabled(False)

        self._thread = QThread()
        self._worker = QtSearchWorker(self.client, plan, language,
                                      self._generation)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.results.connect(self._on_results)
        self._worker.failed.connect(self._on_failed)
        # Sıra önemlidir: worker biter -> thread quit -> thread finished ->
        # nesneler deleteLater ile silinir, referanslar EN SON bırakılır.
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._on_thread_finished)
        self._thread.start()
        return True

    # --- Worker sinyalleri (ana thread'de çalışır) ---

    def _is_current(self, generation):
        return generation == self._generation and not self._cancelled

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

    def _on_results(self, generation, results):
        if not self._is_current(generation):
            return  # STALE: gecikmiş worker yeni sonucu bozamaz.
        dialog = self._ui()
        if dialog is None:
            return  # Dialog yok edilmiş: UI'a dokunulmaz.
        dialog.show_results(results)

    def _on_failed(self, generation, message):
        if not self._is_current(generation):
            return
        dialog = self._ui()
        if dialog is None:
            return
        dialog.show_error(message)

    def _on_dialog_destroyed(self, *_args):
        """Dialog gerçekten yok edildi: referans bırakılır, arama iptal edilir."""
        self.dialog = None
        self.cancel()

    def _on_thread_finished(self):
        # Referanslar ANCAK thread gerçekten bittikten sonra bırakılır.
        self._thread = None
        self._worker = None
        dialog = self._ui()
        if dialog is not None:
            dialog.search_button.setEnabled(True)

    # --- İptal / kapanış ---

    def cancel(self):
        """Kooperatif iptal. GUI yolunda ASLA thread beklenmez."""
        self._cancelled = True
        if self._worker is not None:
            try:
                self._worker.cancel()
            except RuntimeError:
                pass
        if self._thread is not None:
            try:
                self._thread.requestInterruption()
            except RuntimeError:
                pass

    def shutdown(self, wait_ms=5000):
        """Yalnız test/uygulama sonlandırma yardımcısı: doğal bitişi bekler.

        Normal GUI kapanış yolunda ÇAĞRILMAZ.
        """
        self.cancel()
        thread = self._thread
        if thread is None:
            return True
        try:
            thread.quit()
            finished = thread.wait(wait_ms)
        except RuntimeError:
            return True
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None:
            app.processEvents()
        return finished
