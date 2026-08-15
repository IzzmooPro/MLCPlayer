"""Altyazı Merkezi'nin ürün composition'ı: TEK uzun ömürlü koordinatör.

Neden ayrı modül
----------------
Dialog, ayar deposu, ayar/arama/indirme controller'ları ve OpenSubtitles
istemcisi player, menü ve dialog arasına dağıtılırsa yaşam döngüsü sahipliği
kaybolur. Burada hepsini TEK bir `SubtitleCenterCoordinator` sahiplenir; o da
player'a bağlıdır.

    MPVPlayer
      └─ SubtitleCenterCoordinator      (player'a parent'lı, uzun ömürlü)
           ├─ SubtitleSettingsStore     (QSettings + Credential Manager)
           ├─ SubtitleSettingsController
           ├─ SubtitleSearchController
           ├─ SubtitleDownloadController
           ├─ SubtitleCenterDialog      (tek pencere; kapanınca yeniden açılır)
           └─ istemci fabrikası         (ayar kaydından sonra YENİDEN kurulur)

GLOBAL SINGLETON YOKTUR: koordinatör player örneğine bağlanır. İstemci, ayar
deposu ve QSettings testlerde enjekte edilebilir.

Kurallar:

- Yerel bir video yoksa pencere AÇILMAZ; kullanıcıya ürünün kendi OSD'siyle
  kısa bir bilgi verilir. Bu durumda hash, ağ, dosya yazma ve credential
  erişimi HİÇ başlamaz.
- Aynı anda tek pencere: menüye tekrar basmak yeni pencere üretmez, mevcut
  pencereyi öne getirir.
- `WindowStaysOnTopHint` KULLANILMAZ; başka uygulamaya geçildiğinde pencere
  önde asılı kalmaz.
- Hash hesaplaması ve arama planı UI thread'inde YAPILMAZ.
- Tek indirme eylemi vardır: "İndir ve Uygula". Üzerine yazma onayı
  SORULMAZ; hedef videodan tek anlamlı türer ve mevcut dosya yalnız
  doğrulanmış içerikle atomik olarak değişir.
"""
import os
import time

from PyQt6.QtCore import QObject, QThread, QTimer, Qt, pyqtSignal
from app import subtitle_service as service
from app.opensubtitles import OpenSubtitlesClient
from app.subtitle_center import SubtitleCenterDialog
from app.subtitle_center_settings_dialog import SubtitleCenterSettingsDialog
from app.subtitle_connection_test_controller import (
    SubtitleConnectionTestController)
from app.subtitle_download_controller import SubtitleDownloadController
from app.subtitle_search_controller import SubtitleSearchController
from app.subtitle_settings import SubtitleSettingsStore
from app.subtitle_settings_controller import SubtitleSettingsController

LOCAL_MEDIA_REQUIRED = "Önce bir video açın."
CLOSE_STILL_BUSY = "Altyazı işlemi sürüyor; bitince kapanacak."
MISSING_CREDENTIALS = ("OpenSubtitles API anahtarı tanımlı değil. "
                       "Ayarlar bölümünden ekleyin.")

_REMOTE_SCHEMES = ("http://", "https://", "ftp://", "rtsp://", "rtmp://",
                   "smb://", "mms://", "srt://", "udp://", "rtp://")

# Ertelenmiş kapanış: drenaj kontrolü aralığı ve toplam üst sınır.
CLOSE_POLL_MS = 50
CLOSE_TIMEOUT_MS = 5000


def _media_key(path):
    """Medya kimliği: karşılaştırma için normalize edilmiş mutlak yol."""
    try:
        return os.path.normcase(os.path.abspath(str(path or "")))
    except (OSError, ValueError):
        return str(path or "")


def is_local_media(path):
    """Yalnızca GERÇEK yerel bir medya dosyası kabul edilir.

    URL, ağ akışı, boş yol, klasör ve bulunmayan dosya reddedilir.
    """
    if not path or not isinstance(path, str):
        return False
    lowered = path.strip().lower()
    if not lowered:
        return False
    if lowered.startswith(_REMOTE_SCHEMES):
        return False
    try:
        return os.path.isfile(path)
    except (OSError, ValueError):
        return False


class _HashWorker(QObject):
    """Dosya hash'ini WORKER thread'inde hesaplar.

    `opensubtitles_hash` dosyanın başından ve sonundan 64'er KiB okur. Ağ
    sürücüsündeki bir dosyada bu okuma UI'ı dondurabilir, bu yüzden ana
    thread'de yapılmaz.
    """

    # generation, medya kimliği, hash, boyut
    done = pyqtSignal(int, str, str, int)
    finished = pyqtSignal()

    def __init__(self, path, generation):
        super().__init__()
        self._path = path
        self._generation = int(generation)
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            if self._cancelled:
                return
            size = os.path.getsize(self._path)
            digest = service.opensubtitles_hash(self._path)
            if not self._cancelled:
                # Sonuç KİMİN İÇİN hesaplandığını taşır; alıcı doğrular.
                self.done.emit(self._generation, _media_key(self._path),
                               str(digest or ""), int(size))
        except Exception:
            # Hash zorunlu değildir; yoksa arama ada göre yapılır.
            pass
        finally:
            self.finished.emit()


class SubtitleCenterCoordinator(QObject):
    """Altyazı Merkezi'nin tek sahibi. Player yaşam döngüsüne bağlıdır."""

    def __init__(self, player, client_factory=None, settings_store=None,
                 store=None, session=None, parent=None):
        super().__init__(parent or player)
        self.player = player
        self.settings_store = settings_store or SubtitleSettingsStore()
        self.client_factory = client_factory or self._default_client_factory
        # Dosya katmanı: testler geçici dizine yönlendirebilsin diye enjekte
        # edilebilir; varsayılanı controller kendisi kurar.
        self._store = store
        self._session = session

        self._dialog = None
        self._settings_dialog = None
        self._settings_controller = None
        self._connection_tester = None
        self._search_controller = None
        self._download_controller = None
        self._client = None
        # Kapatılan dialogun HÂLÂ ÇALIŞAN controller'ları burada tutulur.
        # Referansı hemen bırakmak, thread'i sahipsiz ve takipsiz bırakırdı.
        self._draining = []
        # Aktif hash işleri: (thread, worker). Eski bir iş yenisini ENGELLEMEZ.
        self._hash_jobs = []
        self._media_generation = 0
        self._closing = False
        self._close_timer = None
        self._close_callback = None
        self._close_deadline = 0.0
        self._close_notified = False

    # --- Durum ---

    @staticmethod
    def _controller_drained(controller):
        """Controller TAMAMEN bitti mi? (thread + ana thread'deki apply)"""
        if controller is None:
            return True
        try:
            if not controller.is_idle():
                return False
            applying = getattr(controller, "is_applying", None)
            if callable(applying) and applying():
                return False
        except RuntimeError:
            return True
        return True

    def _prune_draining(self):
        """Doğal olarak biten controller'lar sahiplik listesinden düşer."""
        self._draining = [c for c in self._draining
                          if not self._controller_drained(c)]
        self._hash_jobs = [(thread, worker) for thread, worker
                           in self._hash_jobs if self._thread_alive(thread)]

    @staticmethod
    def _thread_alive(thread):
        if thread is None:
            return False
        try:
            return bool(thread.isRunning())
        except RuntimeError:
            return False

    def draining_count(self):
        """Kapatılmış dialoglardan kalan, hâlâ çalışan controller sayısı."""
        self._prune_draining()
        return len(self._draining)

    def media_generation(self):
        """Her açılışta artan medya kuşağı; bayat sonuçları eler."""
        return self._media_generation

    @property
    def settings_dialog(self):
        """Yaşayan ayar penceresi ya da None."""
        dialog = self._settings_dialog
        if dialog is None:
            return None
        try:
            dialog.objectName()
        except RuntimeError:
            self._settings_dialog = None
            return None
        return dialog

    # --- Oynatma katmanı bastırma ---

    def _set_overlay_suppressed(self, suppressed):
        """Altyazı Merkezi açıkken cinematic katman GİZLİ tutulur.

        Katman ayrı bir top-level Tool penceresidir; owner olayları onu
        diriltip `raise_()` ile dialogun üstüne taşıyabiliyordu.
        """
        frame = getattr(self.player, "video_frame", None)
        setter = getattr(frame, "set_overlay_suppressed", None)
        if callable(setter):
            try:
                setter(bool(suppressed))
            except Exception:
                pass

    @property
    def dialog(self):
        """Yaşayan dialog ya da None."""
        dialog = self._dialog
        if dialog is None:
            return None
        try:
            dialog.objectName()
        except RuntimeError:
            self._dialog = None
            return None
        return dialog

    def _active_controllers(self):
        """Şu anda sahiplenilen çalışan işler (bağlantı testi DÂHİL)."""
        return (self._search_controller, self._download_controller,
                self._connection_tester)

    def is_idle(self):
        """Hem GÜNCEL hem DRAINING işler hesaba katılır."""
        self._prune_draining()
        for controller in self._active_controllers():
            if not self._controller_drained(controller):
                return False
        if self._draining:
            return False
        return not self._hash_jobs

    def local_media_path(self):
        path = getattr(self.player, "current_file", "")
        return path if is_local_media(path) else ""

    # --- İstemci ---

    @staticmethod
    def _default_client_factory(**kwargs):
        return OpenSubtitlesClient(**kwargs)

    def client(self):
        """Kurulu istemci. Ayar kaydından sonra YENİDEN kurulur."""
        if self._client is None:
            values = self.settings_store.load()
            username = values.get("username", "")
            self._client = self.client_factory(
                api_key=self.settings_store.load_api_key(),
                username=username,
                password=self.settings_store.load_password(username))
        return self._client

    def _invalidate_client(self):
        """Bayat istemci/credential değerleri cache'te kalmaz."""
        self._client = None
        client = self.client()
        for controller in (self._search_controller, self._download_controller):
            if controller is not None:
                controller.client = client
        return client

    def has_credentials(self):
        try:
            return bool(self.settings_store.load_api_key())
        except Exception:
            return False

    # --- Açılış ---

    def open(self):
        """Menü eylemi. Yerel video yoksa pencere AÇILMAZ."""
        path = self.local_media_path()
        if not path:
            self._notify(LOCAL_MEDIA_REQUIRED)
            return False

        dialog = self.dialog
        if dialog is not None:
            # Tek pencere: yenisi üretilmez, mevcut olan öne getirilir.
            dialog.show()
            dialog.raise_()
            dialog.activateWindow()
            return True

        self._prune_draining()
        # Her açılış YENİ kuşaktır; önceki açılışın geç gelen sonuçları elenir.
        self._media_generation += 1
        self._dialog = self._build_dialog(path)
        self._set_overlay_suppressed(True)
        self._dialog.show()
        self._dialog.raise_()
        self._dialog.activateWindow()
        self._start_hash(path)
        if not self.has_credentials():
            # Ağ isteği YOK; kullanıcı önce anahtarı girsin.
            self._dialog.show_error(MISSING_CREDENTIALS)
            self.open_settings()
        return True

    # --- Ayar penceresi (TEK örnek) ---

    def open_settings(self):
        """Dişli isteği. İkinci pencere üretmez; mevcut olanı öne getirir."""
        center = self.dialog
        if center is None:
            return False
        settings = self.settings_dialog
        if settings is None:
            settings = SubtitleCenterSettingsDialog(center)
            self._settings_dialog = settings
            self._settings_controller = SubtitleSettingsController(
                settings, self.settings_store, owner=self)
            self._settings_controller.accepted.connect(self._on_settings_saved)
            # Bağlantı testi GEÇİCİ istemci kurar; kalıcı ayar yazmaz.
            self._connection_tester = SubtitleConnectionTestController(
                settings, client_factory=self.client_factory,
                settings_store=self.settings_store, owner=self)
            settings.finished.connect(self._on_settings_finished)
            settings.destroyed.connect(self._on_settings_destroyed)
        settings.show()
        settings.raise_()
        settings.activateWindow()
        return True

    def _on_settings_finished(self, _code=0):
        dialog = self.settings_dialog
        self._drain_connection_tester()
        self._settings_dialog = None
        self._settings_controller = None
        if dialog is not None:
            try:
                dialog.deleteLater()
            except RuntimeError:
                pass

    def _on_settings_destroyed(self, *_args):
        self._settings_dialog = None
        self._settings_controller = None
        self._connection_tester = None

    def _notify(self, text):
        frame = getattr(self.player, "video_frame", None)
        show_osd = getattr(frame, "show_osd", None)
        if callable(show_osd):
            try:
                show_osd(text)
            except Exception:
                pass

    def _media_info(self, path):
        """Metadata TEK kaynaktan gelir: `subtitle_service` ayrıştırıcısı.

        UI içinde ikinci bir dosya adı parser'ı YOKTUR.
        """
        parsed = service.parse_release(path)
        return {
            "file_name": path,
            "title": parsed["title"],
            "season": parsed["season"],
            "episode": parsed["episode"],
            "is_series": parsed["is_series"],
            "year": parsed["year"],
            "target_name": os.path.basename(service.subtitle_target_path(path)),
            # Hash worker thread'inden gelir; başlangıçta boştur.
            "movie_hash": "",
            "file_size": 0,
        }

    def _build_dialog(self, path):
        # Yardımcı pencere: ana pencereye aittir ama önde asılı KALMAZ.
        # Bunun için ek bir pencere bayrağı verilmez; QDialog varsayılanı
        # zaten "her zaman üstte" değildir.
        dialog = SubtitleCenterDialog(self.player, media=self._media_info(path))
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        client = self.client()
        # Ayarlar AYRI pencerede açılır; dişli yalnız istek yayınlar.
        dialog.settings_requested.connect(self.open_settings)
        self._search_controller = SubtitleSearchController(
            dialog, client=client, owner=self)
        download_kwargs = {}
        if self._store is not None:
            download_kwargs["store"] = self._store
        if self._session is not None:
            download_kwargs["session"] = self._session
        self._download_controller = SubtitleDownloadController(
            dialog, client=client, player=self.player, owner=self,
            **download_kwargs)

        dialog.finished.connect(self._on_dialog_finished)
        dialog.destroyed.connect(self._on_dialog_destroyed)
        return dialog

    def _on_settings_saved(self):
        """Kaydedilen ayarlar SONRAKİ aramada geçerli olsun; restart gerekmez."""
        self._invalidate_client()

    # --- Hash (worker thread) ---

    def _start_hash(self, path):
        """Yeni medyanın hash'i, eski iş sürüyor olsa bile BAŞLATILIR.

        Eski iş doğal bitişine kadar sahiplenilir; yeni medyayı bekletmez.
        """
        thread = QThread()
        worker = _HashWorker(path, self._media_generation)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.done.connect(self._on_hash_ready)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._prune_draining)
        self._hash_jobs.append((thread, worker))
        thread.start()

    def _on_hash_ready(self, generation, media_key, digest, size):
        """Sonuç YALNIZCA kendi kuşağına ve kendi medyasına yazılır."""
        if generation != self._media_generation:
            return  # BAYAT: başka bir açılışa ait.
        dialog = self.dialog
        if dialog is None:
            return
        if _media_key(dialog.media.get("file_name")) != media_key:
            return  # Aynı kuşakta bile olsa BAŞKA medya: yazılmaz.
        dialog.media["movie_hash"] = digest
        dialog.media["file_size"] = size

    # --- Kapanış ---

    def _release_controllers(self):
        """Aktif controller'ları bırakır; HÂLÂ ÇALIŞANLAR draining'e taşınır.

        Referansı doğrudan silmek, çalışan QThread'i takipsiz bırakıyordu:
        `is_idle()` "boşta" diyor, `shutdown()` onu beklemiyordu.
        """
        for controller in (self._search_controller, self._download_controller):
            if controller is None:
                continue
            if (not self._controller_drained(controller)
                    and controller not in self._draining):
                self._draining.append(controller)
        self._settings_controller = None
        self._search_controller = None
        self._download_controller = None

    def _on_dialog_finished(self, _code=0):
        # Dialog kapandı: controller'lar iptal ister (BEKLEMEZ) ve draining
        # listesine geçer; yeniden açılışta sinyaller İKİNCİ kez bağlanmaz.
        dialog = self.dialog
        for controller in (self._search_controller, self._download_controller):
            if controller is not None:
                try:
                    controller.cancel()
                except RuntimeError:
                    pass
        self._close_settings_dialog()
        self._dialog = None
        self._release_controllers()
        self._cancel_hash()
        # Oynatma katmanı normal akışına döner.
        self._set_overlay_suppressed(False)
        # Kapatılan pencere YOK EDİLİR. Aksi halde her aç/kapa turunda
        # player'a bağlı gizli bir top-level kabuk birikiyor ve kapanışta
        # QApplication'dan sonra yıkılan bu yığın native çökmeye yol açıyor.
        # Çalışan worker varsa bu, testlerle doğrulanmış "destroy" yoludur:
        # controller'lar dialog'a parent'lı değildir ve `destroyed` sinyaliyle
        # referanslarını bırakır.
        if dialog is not None:
            try:
                dialog.deleteLater()
            except RuntimeError:
                pass

    def _on_dialog_destroyed(self, *_args):
        self._dialog = None
        self._release_controllers()

    def _drain_connection_tester(self):
        """Kooperatif iptal ister; UI thread'inde BEKLEMEZ.

        Eskiden burada `shutdown(wait_ms=3000)` çağrılıyordu: ayar penceresi
        kapanırken UI üç saniyeye kadar donuyor ve süre dolduğunda controller
        hâlâ çalışırken referansı bırakılıyordu. Artık bitmeyen tester
        `_draining` listesinde SAHİPLENİLİR; `is_idle()`, `shutdown()`,
        `begin_close()` ve zaman aşımı güvenliği onu da sayar.
        """
        tester = self._connection_tester
        self._connection_tester = None
        if tester is None:
            return
        try:
            tester.cancel()
        except RuntimeError:
            return
        if (not self._controller_drained(tester)
                and tester not in self._draining):
            self._draining.append(tester)

    def _close_settings_dialog(self):
        dialog = self.settings_dialog
        self._drain_connection_tester()
        self._settings_dialog = None
        self._settings_controller = None
        if dialog is None:
            return
        try:
            dialog.close()
            dialog.deleteLater()
        except RuntimeError:
            pass

    def _cancel_hash(self):
        for _thread, worker in list(self._hash_jobs):
            try:
                worker.cancel()
            except RuntimeError:
                pass

    def _cancel_all(self):
        """Kooperatif iptal; hiçbir şey BEKLENMEZ."""
        self._cancel_hash()
        for controller in self._active_controllers():
            if controller is None:
                continue
            try:
                controller.cancel()
            except RuntimeError:
                pass
        for controller in list(self._draining):
            try:
                controller.cancel()
            except RuntimeError:
                pass

    def is_fully_drained(self):
        """Aktif VE draining bütün işler bitti mi?"""
        return self.is_idle()

    def shutdown(self, wait_ms=5000):
        """Player kapanışı: çalışan işler güvenli biçimde sonlandırılır.

        Bütçe TOPLAMDIR: her controller için ayrı ayrı `wait_ms` beklenmez,
        aksi halde kapanış controller sayısıyla çarpılırdı. QThread hâlâ
        çalışırken nesne yok EDİLMEZ ve `terminate()` KULLANILMAZ.
        """
        self._cancel_all()
        deadline = time.monotonic() + max(0, wait_ms) / 1000.0

        def remaining_ms():
            return max(0, int((deadline - time.monotonic()) * 1000))

        finished = True
        controllers = [c for c in self._active_controllers()
                       if c is not None]
        for controller in self._draining:
            if controller not in controllers:
                controllers.append(controller)

        # BİTMEYEN iş listeden DÜŞMEZ. Aksi halde çalışan bir QThread
        # sahipsiz kalıyor, "tamamlandı" diye raporlanıyor ve yıkım
        # sırasında native çökmeye yol açıyordu.
        still_running = []
        for controller in controllers:
            try:
                done = bool(controller.shutdown(wait_ms=remaining_ms()))
            except RuntimeError:
                done = True
            if not (done and self._controller_drained(controller)):
                finished = False
                if controller not in still_running:
                    still_running.append(controller)

        remaining_jobs = []
        for thread, worker in list(self._hash_jobs):
            try:
                thread.quit()
                waited = bool(thread.wait(remaining_ms()))
            except RuntimeError:
                waited = True
            if not waited and self._thread_alive(thread):
                finished = False
                remaining_jobs.append((thread, worker))
        self._hash_jobs = remaining_jobs
        # Sıra önemlidir: aşağıdaki `dialog.close()` hâlâ çalışan aktif
        # controller'ları `_release_controllers()` üzerinden bu listeye
        # ekleyebilir; bu istenen davranıştır.
        self._draining = still_running

        self._close_settings_dialog()
        dialog = self.dialog
        if dialog is not None:
            try:
                dialog.close()
                dialog.deleteLater()
            except RuntimeError:
                pass
        self._dialog = None
        self._settings_controller = None
        self._connection_tester = None
        self._search_controller = None
        self._download_controller = None
        self._set_overlay_suppressed(False)
        return finished

    # --- Ertelenmiş (donmayan) kapanış ---

    def begin_close(self, on_ready=None, timeout_ms=CLOSE_TIMEOUT_MS):
        """Kapanışı hazırlar. Hazırsa True, drenaj gerekiyorsa False döner.

        UI ASLA saniyelerce bloke edilmez: iş sürüyorsa iptal istenir ve
        kısa ömürlü bir denetleyici, işler doğal olarak bitince `on_ready`
        geri çağrısını TEK KEZ tetikler. Çalışan QThread zorla
        sonlandırılmaz.
        """
        self._cancel_all()
        if self.is_fully_drained():
            self._finish_close()
            return True
        if self._closing:
            # Drenaj zaten sürüyor; ikinci kapatma isteği yeni bir tur
            # başlatmaz ve çift kapanış üretmez.
            return False
        self._closing = True
        self._close_callback = on_ready
        self._close_notified = False
        self._close_deadline = time.monotonic() + max(0, timeout_ms) / 1000.0
        # Kısa ömürlü ve TEK amaçlı: yalnız kapanış drenajı boyunca yaşar.
        timer = QTimer(self)
        timer.setInterval(CLOSE_POLL_MS)
        timer.timeout.connect(self._on_close_tick)
        self._close_timer = timer
        timer.start()
        return False

    def _on_close_tick(self):
        if not self._closing:
            return
        if not self.is_fully_drained():
            # ZAMAN AŞIMI KAPANIŞ İZNİ DEĞİLDİR. Çalışan iş varken ne
            # pencere kapatılır ne de nesneler yok edilir; yalnızca bir KEZ
            # kısa ve güvenli bir bilgi gösterilir ve izlemeye devam edilir.
            # Ağ katmanının kendi timeout'ları işin doğal olarak bitmesini
            # sağlar.
            if (not self._close_notified
                    and time.monotonic() >= self._close_deadline):
                self._close_notified = True
                self._notify(CLOSE_STILL_BUSY)
            return
        self._stop_close_timer()
        self._closing = False
        callback = self._close_callback
        self._close_callback = None
        self._finish_close()
        if callable(callback):
            callback()

    def _stop_close_timer(self):
        timer = self._close_timer
        self._close_timer = None
        if timer is None:
            return
        try:
            timer.stop()
            timer.deleteLater()
        except RuntimeError:
            pass

    def _finish_close(self):
        """Her şey bitti: pencere ve referanslar bırakılır."""
        self._stop_close_timer()
        self.shutdown(wait_ms=0)


# --- Ürün giriş noktaları (global singleton YOK) ---

def _coordinator_of(player):
    """Player'a bağlı koordinatör; yoksa None.

    NOT: `__dict__` üzerinden okunur. Testlerdeki sip stub'larında
    (`super().__init__()` çağrılmamış QObject) normal öznitelik erişimi
    `RuntimeError` üretiyor; proje bu deseni `closeEvent` içinde de kullanır.
    """
    try:
        return player.__dict__.get("_subtitle_center")
    except AttributeError:
        return None


def subtitle_center_coordinator(player, **kwargs):
    """Player'a ait koordinatörü döndürür; yoksa bir kez oluşturur."""
    coordinator = _coordinator_of(player)
    if coordinator is None:
        coordinator = SubtitleCenterCoordinator(player, **kwargs)
        player._subtitle_center = coordinator
    return coordinator


def open_subtitle_center(player):
    """Menü eylemi hedefi: "Alt Yazı > Altyazı Bul…"."""
    return subtitle_center_coordinator(player).open()


def shutdown_subtitle_center(player, wait_ms=5000):
    """Player kapanışında çağrılır. Koordinatör yoksa hiçbir şey yapmaz."""
    coordinator = _coordinator_of(player)
    if coordinator is None:
        return True
    try:
        return coordinator.shutdown(wait_ms=wait_ms)
    except RuntimeError:
        return True


def subtitle_center_drained(player):
    """Kapanış koordinasyonu başarısızsa kullanılan FAIL-CLOSED yedeği.

    Yalnızca "gerçekten boşta" olduğu doğrulanabildiğinde True döner.
    Koordinatör yoksa yapılacak iş de yoktur. Herhangi bir belirsizlikte
    False döner: kanıt yoksa pencere kapanmaz.
    """
    coordinator = _coordinator_of(player)
    if coordinator is None:
        return True
    try:
        return bool(coordinator.is_fully_drained())
    except Exception:
        return False


def close_subtitle_center_before_exit(player, timeout_ms=CLOSE_TIMEOUT_MS):
    """`closeEvent` kapısı: kapanmaya HAZIR mıyız?

    True dönerse pencere hemen kapanabilir. False dönerse çağıran
    `event.ignore()` yapmalıdır; işler doğal olarak bitince pencere kapatma
    isteği TEK KEZ yeniden tetiklenir. UI bu süre boyunca donmaz.
    """
    coordinator = _coordinator_of(player)
    if coordinator is None:
        return True
    return coordinator.begin_close(player.close, timeout_ms=timeout_ms)
