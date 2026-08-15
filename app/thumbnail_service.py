"""Oynatma listesi küçük resimlerini ana MPV örneğine dokunmadan üretir."""

import hashlib
import os
import sys

from PyQt6.QtCore import QObject, QProcess, QStandardPaths, QTimer, pyqtSignal


THUMBNAIL_TIMEOUT_MS = 12_000
VIDEO_EXTENSIONS = {
    ".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".mpeg", ".mpg", ".m4v",
}


def default_cache_dir():
    """Onbellegin SABIT yazma yolu.

    OLCULEN REGRESYON: burasi `QStandardPaths.CacheLocation` kullaniyordu
    ve o yol `applicationName`/`organizationName` degerlerine BAGLIDIR.
    Uygulamaya `MLC Player` kimligi verilince yol degisti, mevcut kayitlar
    oksuz kaldi ve her playlist satiri icin yeniden worker acildi (kullanici
    "cift EXE" gordu, yazilimsal decode atlamalari geciktirdi).

    Yol artik uygulama kimliginden, frozen olup olmamaktan ve calistirma
    biciminden BAGIMSIZDIR; gelistirme ile kurulu surum ayni onbellegi
    paylasir.
    """
    root = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(root, "MLCPlayer", "cache", "thumbnails")


def legacy_cache_dirs():
    """YALNIZ OKUNAN eski dizinler; oraya asla yazilmaz.

    Kimlik degisiminden once uretilmis kareler kaybolmasin diye taninir.
    Qt turevli yol kimlige gore degistigi icin burada calisma anindaki
    degeri okunur; okunamazsa sessizce atlanir.
    """
    found = []
    try:
        root = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.CacheLocation)
    except Exception:
        root = ""
    if root:
        found.append(os.path.join(root, "thumbnails"))
    local = os.environ.get("LOCALAPPDATA")
    if local:
        # Kimlik ayarlanmadan once Qt yolu calistirilabilir dosyadan
        # turetiyordu (kaynaktan calistirmada `python`).
        found.append(os.path.join(local, "python", "cache", "thumbnails"))
    current = default_cache_dir()
    return tuple(path for path in found
                 if os.path.normcase(path) != os.path.normcase(current))


def find_cached_thumbnail(media_path, cache_dir):
    """Hazir kareyi once YENI, sonra eski dizinlerde arar.

    Bulunan eski kare oldugu yerde KULLANILIR; kopyalanmaz, tasinmaz.
    """
    try:
        name = os.path.basename(thumbnail_cache_path(media_path, cache_dir))
    except OSError:
        return None
    candidates = [os.path.join(cache_dir, name)]
    candidates.extend(os.path.join(old, name) for old in legacy_cache_dirs())
    for candidate in candidates:
        try:
            if os.path.isfile(candidate) and os.path.getsize(candidate) > 0:
                return candidate
        except OSError:
            continue
    return None


def thumbnail_cache_path(media_path, cache_dir=None):
    """Dosya değiştiğinde eski kareyi kullanmayan kararlı cache yolu."""
    absolute = os.path.normcase(os.path.abspath(media_path))
    stat = os.stat(absolute)
    identity = f"{absolute}\0{stat.st_size}\0{stat.st_mtime_ns}"
    digest = hashlib.sha256(identity.encode("utf-8", "surrogatepass")).hexdigest()
    return os.path.join(cache_dir or default_cache_dir(), f"{digest}.jpg")


def build_worker_command(media_path, output_path):
    """Kaynak çalıştırmada main.py'yi, frozen pakette aynı EXE'yi kullanır."""
    args = ["--thumbnail-worker", media_path, output_path]
    if getattr(sys, "frozen", False):
        return sys.executable, args
    main_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
    return sys.executable, [main_path, *args]


class ThumbnailService(QObject):
    thumbnail_ready = pyqtSignal(str, str)
    # Worker sifir olmayan exit dondurdugunde SESSIZ kalinmaz: panel satiri
    # `loading` durumundan cikarilabilsin diye acik bir basarisizlik sinyali
    # yayinlanir.
    thumbnail_failed = pyqtSignal(str)

    def __init__(self, parent=None, cache_dir=None):
        super().__init__(parent)
        self.cache_dir = cache_dir or default_cache_dir()
        self._queue = []
        self._queued = set()
        # Ayni oturumda BASARISIZ dosya tekrar tekrar kuyruga alinmaz.
        self._failed = set()
        self._current = None
        self._process = QProcess(self)
        self._process.finished.connect(self._finished)
        self._timeout = QTimer(self)
        self._timeout.setSingleShot(True)
        self._timeout.setInterval(THUMBNAIL_TIMEOUT_MS)
        self._timeout.timeout.connect(self._timed_out)

    @property
    def pending_paths(self):
        paths = ([self._current[0]] if self._current else [])
        return tuple(paths + [entry[0] for entry in self._queue])

    def request(self, media_path):
        if (not media_path or "://" in media_path
                or os.path.splitext(media_path)[1].lower() not in VIDEO_EXTENSIONS
                or not os.path.isfile(media_path)):
            return None
        try:
            output = thumbnail_cache_path(media_path, self.cache_dir)
        except OSError:
            return None
        # Eski kimlikle uretilmis kare varsa YENIDEN URETILMEZ.
        ready = find_cached_thumbnail(media_path, self.cache_dir)
        if ready:
            return ready
        # Basarisizlik kimligi CACHE kimligidir (yol + boyut + mtime).
        # Boylece dosya ayni yolda degistiginde yeni surum yeniden denenir.
        if output in self._failed:
            return None
        key = os.path.normcase(os.path.abspath(media_path))
        if key not in self._queued:
            self._queued.add(key)
            self._queue.append((media_path, output, key))
            self._start_next()
        return None

    def status(self, media_path):
        """Bir medyanin thumbnail DURUMU: `ready` | `failed` | `loading` |
        `empty`.

        `request()` donusundeki `None` uc ayri anlama geliyordu (kuyrukta,
        basarisiz, uygun degil) ve arayuz bunlari ayiramiyordu. Durum
        sorgusu bu yuzden ayri ve aciktir; arayuz servisin ic alanlarina
        erismez.
        """
        if (not media_path or "://" in media_path
                or os.path.splitext(media_path)[1].lower() not in VIDEO_EXTENSIONS
                or not os.path.isfile(media_path)):
            return "empty"
        try:
            output = thumbnail_cache_path(media_path, self.cache_dir)
        except OSError:
            return "empty"
        # Hazir cache HER ZAMAN oncelikli: kare sonradan gercekten
        # olustuysa eski basarisizlik kaydi satiri kilitlemez. Eski
        # kimlikle uretilmis kare de hazir sayilir.
        if find_cached_thumbnail(media_path, self.cache_dir):
            return "ready"
        if output in self._failed:
            return "failed"
        key = os.path.normcase(os.path.abspath(media_path))
        if key in self._queued:
            return "loading"
        return "loading"

    def is_failed(self, media_path):
        return self.status(media_path) == "failed"

    def _start_next(self):
        if self._current is not None or not self._queue:
            return
        self._current = self._queue.pop(0)
        media_path, output, _ = self._current
        os.makedirs(os.path.dirname(output), exist_ok=True)
        program, args = build_worker_command(media_path, output)
        self._process.start(program, args)
        self._timeout.start()

    def _finished(self, exit_code, _exit_status):
        self._timeout.stop()
        current = self._current
        self._current = None
        if current is not None:
            media_path, output, key = current
            self._queued.discard(key)
            if exit_code == 0 and os.path.isfile(output) and os.path.getsize(output) > 0:
                self.thumbnail_ready.emit(media_path, output)
            else:
                # Basarisizlik: satir `loading` kalmasin, ayni dosya
                # sinirsiz yeniden denenmesin.
                self._failed.add(output)
                self.thumbnail_failed.emit(media_path)
        self._start_next()

    def _timed_out(self):
        if self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.kill()

    def close(self):
        self._timeout.stop()
        self._queue.clear()
        self._queued.clear()
        self._current = None
        if self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.kill()
            self._process.waitForFinished(1000)
