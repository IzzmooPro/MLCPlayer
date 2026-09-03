# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Güncelleme denetimi — GitHub release'lerinden sürüm kontrolü ve kurulum.

Davranış (kullanıcı kararı, 16 Ağustos 2026):
- Açılışta arka planda sessiz kontrol. Güncelleme yoksa HİÇBİR ŞEY gösterilmez.
- `Yardım → Güncellemeleri Denetle` ile kullanıcı da tetikleyebilir; orada
  "günceldesiniz" ve hata mesajları GÖSTERİLİR.

GÜVEN ZİNCİRİ (referans projeden taşındı, gerekçeleriyle):
- Release'ten YALNIZ beklenen ada birebir uyan TEK asset kabul edilir.
  "İlk .exe'yi indir" davranışı, release'e ikinci bir exe girdiğinde yanlış
  dosyanın yönetici hakkıyla çalıştırılmasına yol açıyordu.
- İndirme URL'i şema + host + `repo/releases/download/<tag>/<ad>` yoluna
  birebir uymalıdır; redirect SONRASI son host da izinli kümede olmalıdır
  (tam hostname eşleşmesi; suffix/prefix hilesi kabul edilmez).
- İndirilen dosya API'nin bildirdiği `size` ve `sha256` ile doğrulanır.
  Doğrulanamayan dosya SİLİNİR ve kurulum BAŞLATILMAZ (fail-closed).
- Kullanıcıya giden metinler SABİTTİR; ham istisna, URL ve dosya yolu
  yalnız `app/errors.py` günlüğüne gider.

SINIR: digest de release metadata'sından gelir. Bozuk/eksik indirmeyi ve
yanlış asset seçimini engeller; ele geçirilmiş release metadata'sına karşı
bağımsız güven kökü DEĞİLDİR (bunun için kod imzası gerekir).

BU ÜRÜNE UYARLANANLAR (referanstan bilerek AYRILAN noktalar):
- Referans, kurulumu başlatınca süreci `os._exit(0)` ile öldürür. Burada
  YAPILMAZ: mpv ve Altyazı Merkezi worker'ları kooperatif kapanışa bağlıdır
  (ürün değişmezi). Kapanış `player.close()` üzerinden ürünün kendi sırasından
  geçer; pencere gerçekten kapanmadıysa kurulum BAŞLATILMAZ.
- Yeni timer eklenmez; `terminate()` çağrılmaz.
"""

import hashlib
import json
import os
import re
import stat
import tempfile
from collections import namedtuple
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote, urlsplit
from app.i18n import tr, tr_mark, translate_marked

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (QDialog, QFrame, QGraphicsDropShadowEffect,
                             QHBoxLayout, QLabel, QMessageBox, QProgressBar,
                             QPushButton, QSizePolicy, QVBoxLayout, QWidget)

from app.app_icon import application_icon
from app import release_signature as signing
from app.config import (APP_VERSION, UI_ACCENT, UI_ACCENT_HOVER,
                        UI_ACCENT_PRESSED, UI_FONT_FAMILY)
from app.errors import log

GITHUB_REPO = "IzzmooPro/MLCPlayer"
GITHUB_URL = f"https://github.com/{GITHUB_REPO}"

#: Açılış kontrolünün ağ zaman aşımı (saniye). Kısa tutulur: kullanıcı
#: güncelleme için değil, video açmak için programı başlatmıştır.
STARTUP_CHECK_TIMEOUT = 3
#: Kullanıcının tetiklediği kontrol biraz daha sabırlı olabilir.
MANUAL_CHECK_TIMEOUT = 8

#: Kurulum dosyası adı `packaging/MLCPlayer.iss` içindeki
#: `OutputBaseFilename=MLCPlayer_Setup_{#MyAppVersion}` ile AYNI olmalıdır;
#: `tests/test_updater_regressions.py` bu bağı korur.
ASSET_NAME_TEMPLATE = "MLCPlayer_Setup_{tag}.exe"

_RELEASE_HOST = "github.com"
_ALLOWED_DOWNLOAD_HOSTS = frozenset({
    _RELEASE_HOST,
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
})

_DIGEST_RE = re.compile(r"^sha256:([0-9a-fA-F]{64})$")

# Kullanıcıya gösterilen SABİT metinler.
#
# Bunlar modül düzeyindedir; import anında çevirmen HENÜZ YOKTUR. Bu yüzden
# yalnız `tr_mark()` ile işaretlenir ve çeviri GÖSTERİM yerinde yapılır:
# `UpdateDialog.show_error()` ile `check_for_updates._failed()` aldıkları
# metni `translate_marked()`ten geçirir. Sözleşme: bu iki giriş noktasına
# her zaman İŞARETLENMİŞ metin verilir.
VERIFY_FAILED_MESSAGE = tr_mark(
    "Güncelleme dosyası doğrulanamadı. Kurulum başlatılmadı.")
DOWNLOAD_FAILED_MESSAGE = tr_mark("Güncelleme indirilemedi.")
ASSET_VERIFY_FAILED_MESSAGE = tr_mark(
    "Güncelleme bilgisi doğrulanamadı. Otomatik güncelleme başlatılmadı.")
CHECK_FAILED_MESSAGE = tr_mark("Güncelleme kontrol edilemedi.")
BUSY_MESSAGE = tr_mark("Program şu anda kapanamıyor (süren bir işlem var). "
                       "İşlem bitince güncellemeyi yeniden başlatın.")

UPDATE_DIALOG_SIZE = (520, 310)
UPDATE_BRAND_WIDTH = 165

UPDATE_DIALOG_STYLE = """
QDialog#updateDialog { background: transparent; }
QFrame#updateCard {
    background: #15191E;
    border: 1px solid #424950;
    border-radius: 12px;
}
QFrame#updateBrandPanel {
    background: qlineargradient(x1:0, y1:0, x2:0.9, y2:1,
                                stop:0 #4A2115, stop:0.55 #291B19,
                                stop:1 #17191D);
    border: none;
    border-right: 1px solid #34383D;
    border-top-left-radius: 11px;
    border-bottom-left-radius: 11px;
}
QWidget#updateContentPanel { background: transparent; border: none; }
QLabel {
    background: transparent; border: none; color: #E9EDF1;
    font-family: __UI_FONT_FAMILY__;
}
QLabel#updateHeading { font-size: 19px; font-weight: 700; }
QLabel#updateDescription { font-size: 14px; color: #E9EDF1; }
QLabel#updateSupportingText { font-size: 12px; color: #929AA3; }
QLabel#updateVersion { font-size: 17px; font-weight: 600; }
QLabel#updateStatus { font-size: 11px; color: #A8AFB7; }
QPushButton {
    min-height: 38px;
    padding: 0 18px;
    border-radius: 7px;
    font-size: 13px;
    font-family: __UI_FONT_FAMILY__;
}
QPushButton#updateClose {
    min-width: 30px; max-width: 30px;
    min-height: 30px; max-height: 30px;
    padding: 0;
    color: #AEB4BB;
    background: transparent;
    border: none;
    border-radius: 6px;
    font-size: 22px;
    font-weight: 300;
}
QPushButton#updateClose:hover { color: #FFFFFF; background: __UI_ACCENT__; }
QPushButton#updateReleaseNotes {
    min-height: 28px;
    padding: 0;
    color: __UI_ACCENT__;
    background: transparent;
    border: none;
    font-size: 13px;
    text-align: left;
}
QPushButton#updateReleaseNotes:hover { color: __UI_ACCENT_HOVER__; }
QPushButton#updateLater {
    min-width: 106px;
    color: #DDE2E7;
    background: transparent;
    border: 1px solid #4A5159;
}
QPushButton#updateLater:hover { background: rgba(255,255,255,12); }
QPushButton#updatePrimary {
    min-width: 114px;
    color: #FFFFFF;
    background: __UI_ACCENT__;
    border: none;
    font-weight: 600;
}
QPushButton#updatePrimary:hover { background: __UI_ACCENT_HOVER__; }
QPushButton#updatePrimary:pressed { background: __UI_ACCENT_PRESSED__; }
QPushButton:disabled { color: #717982; background: #25292E; }
QProgressBar#updateProgress {
    min-height: 5px; max-height: 5px;
    color: transparent;
    background: #30353B;
    border: none;
    border-radius: 2px;
}
QProgressBar#updateProgress::chunk {
    background: __UI_ACCENT__;
    border-radius: 2px;
}
""".replace("__UI_ACCENT__", UI_ACCENT).replace(
    "__UI_ACCENT_HOVER__", UI_ACCENT_HOVER).replace(
    "__UI_ACCENT_PRESSED__", UI_ACCENT_PRESSED).replace(
    "__UI_FONT_FAMILY__", UI_FONT_FAMILY)

#: Doğrulanmış güncelleme asset'i. `signature_url`, yayıncı imzasının
#: (`<kurulum>.sig`) adresidir; imza katmanı açıkken ZORUNLUDUR.
UpdateAsset = namedtuple("UpdateAsset", "name url sha256 size signature_url")


class VerificationError(Exception):
    """İçerik/metadata doğrulaması başarısız — kullanıcıya ayrıntı verilmez."""


# ── Sürüm karşılaştırma ──────────────────────────────────────────────────

def _version_parts(value):
    numbers = [int(part) for part in re.findall(r"\d+", value or "")]
    while len(numbers) < 3:
        numbers.append(0)
    return tuple(numbers)


def is_newer_version(latest, current=None):
    return _version_parts(latest) > _version_parts(current or APP_VERSION)


# ── Asset seçimi ve URL doğrulaması (Qt'den bağımsız, saf) ───────────────

def expected_asset_name(tag):
    return ASSET_NAME_TEMPLATE.format(tag=(tag or "").strip())


def _parts(url):
    """(scheme, hostname, port, path) — ayrıştırılamazsa hepsi None."""
    if not isinstance(url, str) or not url:
        return (None, None, None, None)
    try:
        parsed = urlsplit(url)
        return (parsed.scheme, parsed.hostname, parsed.port, parsed.path)
    except ValueError:
        return (None, None, None, None)


def is_allowed_download_host(url):
    """Redirect sonrası son URL: HTTPS + tam hostname eşleşmesi."""
    scheme, host, port, _ = _parts(url)
    if scheme != "https" or host is None:
        return False
    if port not in (None, 443):
        return False
    return host.lower() in _ALLOWED_DOWNLOAD_HOSTS


def is_release_download_url(url, tag, name=None):
    """API'den gelen indirme URL'i: şema, host, repo/tag yolu ve dosya adı.

    `name` verilmezse kurulum dosyası beklenir; imza dosyası için
    `<kurulum>.sig` adı geçirilir.
    """
    if not (tag or "").strip():
        return False
    scheme, host, port, path = _parts(url)
    if scheme != "https" or host is None or port not in (None, 443):
        return False
    if host.lower() != _RELEASE_HOST:
        return False
    expected = (f"/{GITHUB_REPO}/releases/download/"
                f"{tag.strip()}/{name or expected_asset_name(tag)}")
    return path == expected


def _digest_hex(value):
    if not isinstance(value, str):
        return None
    match = _DIGEST_RE.match(value.strip())
    return match.group(1).lower() if match else None


def _positive_size(value):
    # bool int'in alt sınıfıdır; True/False boyut sayılmaz.
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def select_update_asset(data):
    """Release JSON'undan doğrulanmış TEK asset'i seçer.

    Dönüş: `(UpdateAsset, "")` veya `(None, reddetme_nedeni)`. Neden yalnız
    günlük içindir; kullanıcıya gösterilmez.
    """
    tag = str((data or {}).get("tag_name", "") or "").strip()
    if not tag:
        return None, "tag_name boş"

    expected = expected_asset_name(tag)
    assets = (data or {}).get("assets") or []
    if not isinstance(assets, list):
        return None, "assets listesi okunamadı"

    matching = [a for a in assets
                if isinstance(a, dict) and a.get("name") == expected]
    if not matching:
        return None, f"beklenen asset yok: {expected}"
    if len(matching) > 1:
        return None, f"aynı adlı {len(matching)} asset var: {expected}"

    record = matching[0]
    url = record.get("browser_download_url")
    if not is_release_download_url(url, tag):
        return None, "indirme URL'i beklenen release yoluna uymuyor"

    digest = _digest_hex(record.get("digest"))
    if digest is None:
        return None, "digest alanı sha256:<64 hex> biçiminde değil"

    size = _positive_size(record.get("size"))
    if size is None:
        return None, "size alanı pozitif tam sayı değil"

    signature_url = ""
    if signing.signing_enabled():
        # İmza katmanı açıkken imzasız release KABUL EDİLMEZ (fail-closed):
        # aksi hâlde saldırgan imzayı silerek korumayı devre dışı bırakırdı.
        wanted = signing.signature_asset_name(expected)
        matching_signature = [a for a in assets
                              if isinstance(a, dict) and a.get("name") == wanted]
        if not matching_signature:
            return None, f"yayıncı imzası yok: {wanted}"
        if len(matching_signature) > 1:
            return None, f"aynı adlı {len(matching_signature)} imza var"
        signature_url = matching_signature[0].get("browser_download_url")
        if not is_release_download_url(signature_url, tag, wanted):
            return None, "imza URL'i beklenen release yoluna uymuyor"

    return UpdateAsset(expected, url, digest, size, signature_url), ""


def _verified_asset(data, source):
    """Ortak yol: seçim + fail-closed günlükleme."""
    choice, reason = select_update_asset(data)
    if choice is None:
        log(f"{source}: the update asset could not be verified ({reason}); "
            f"no automatic update is offered.", level="WARNING")
    return choice


def fetch_latest_release(timeout):
    """GitHub API'sinden son release JSON'unu okur."""
    import urllib.request
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    request = urllib.request.Request(
        url, headers={"User-Agent": f"MLCPlayer/{APP_VERSION}"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


# ── Kontrol (arka plan thread) ───────────────────────────────────────────

class UpdateChecker(QThread):
    """GitHub API'sini sorgular; sonucu sinyalle bildirir.

    Asset doğrulanamazsa `no_update` DEĞİL `check_failed` yayılır: yeni sürüm
    varken "günceldesiniz" demek yanlış olur.
    """

    update_available = pyqtSignal(str, str, str, int, str)
    no_update = pyqtSignal()
    check_failed = pyqtSignal(str)

    def __init__(self, parent=None, timeout=MANUAL_CHECK_TIMEOUT, silent=False):
        super().__init__(parent)
        self._timeout = timeout
        #: Açılış kontrolü sessizdir: başarısızlık kullanıcıya gösterilmez.
        self.silent = silent

    def run(self):
        try:
            data = fetch_latest_release(self._timeout)
            tag = str(data.get("tag_name", "") or "").strip()
            if not tag:
                self.no_update.emit()
                return
            if not is_newer_version(tag):
                self.no_update.emit()
                return
            choice = _verified_asset(data, type(self).__name__)
            if choice is None:
                self.check_failed.emit(ASSET_VERIFY_FAILED_MESSAGE)
                return
            self.update_available.emit(tag, choice.url, choice.sha256,
                                       choice.size, choice.signature_url)
        except Exception as exc:
            # Ham istisna metni (URL, yol, backend ayrıntısı) kullanıcıya
            # gösterilmez; yalnız günlüğe yazılır (orada da maskelenir).
            log(f"Update check failed: {exc}", level="WARNING")
            self.check_failed.emit(CHECK_FAILED_MESSAGE)


# ── İndirici (arka plan thread) ──────────────────────────────────────────

class UpdateDownloader(QThread):
    """Kurulum dosyasını indirir ve DOĞRULAR.

    `download_finished` yalnız şu koşulların TAMAMI sağlanınca yayılır:
    redirect sonrası host izinli ve HTTPS · yazılan bayt = API `size` ·
    varsa `Content-Length` aynı değer · SHA-256 beklenen digest ile aynı.
    Aksi hâlde yarım dosya silinir ve `failed` yayılır.
    """

    # QThread'in yerleşik `finished` sinyali GÖLGELENMEZ.
    progress = pyqtSignal(int)
    download_finished = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, url, dest, expected_sha256, expected_size, parent=None,
                 signature_url=""):
        super().__init__(parent)
        self._url = url
        self._dest = dest
        self._expected_sha256 = (expected_sha256 or "").lower()
        self._expected_size = expected_size
        self._signature_url = signature_url

    def run(self):
        try:
            self._download_and_verify()
        except VerificationError as exc:
            log(f"Update verification failed: {exc}", level="WARNING")
            self._remove_partial_file()
            self.failed.emit(VERIFY_FAILED_MESSAGE)
        except Exception as exc:
            log(f"Update download failed: {exc}", level="WARNING")
            self._remove_partial_file()
            self.failed.emit(DOWNLOAD_FAILED_MESSAGE)
        else:
            self.download_finished.emit(self._dest)

    def _download_and_verify(self):
        import urllib.request
        expected = _positive_size(self._expected_size)
        if expected is None or not _DIGEST_RE.match(
                f"sha256:{self._expected_sha256}"):
            raise VerificationError("beklenen boyut/özet eksik veya bozuk")

        digest = hashlib.sha256()
        written = 0
        with urllib.request.urlopen(self._url, timeout=60) as response:
            # Redirect zincirinin SONUNDAKİ gerçek hedef denetlenir.
            if not is_allowed_download_host(response.geturl()):
                raise VerificationError(
                    "indirme beklenmeyen hedefe yönlendirildi")
            reported = response.headers.get("Content-Length")
            if reported is not None:
                try:
                    if int(reported) != expected:
                        raise VerificationError(
                            "Content-Length beklenen boyuta uymuyor")
                except (TypeError, ValueError):
                    raise VerificationError("Content-Length okunamadı")
            with open(self._dest, "wb") as handle:
                while True:
                    chunk = response.read(8192)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > expected:
                        raise VerificationError("beklenenden fazla veri geldi")
                    digest.update(chunk)
                    handle.write(chunk)
                    self.progress.emit(int(written * 100 / expected))

        if written != expected:
            raise VerificationError(f"eksik indirme: {written}/{expected} bayt")
        if digest.hexdigest() != self._expected_sha256:
            raise VerificationError("SHA-256 beklenen değerle uyuşmuyor")
        self._verify_publisher_signature(digest.hexdigest())

    def _verify_publisher_signature(self, sha256_hex):
        """BAĞIMSIZ güven kökü: özeti yayıncı mı imzalamış?

        SHA-256 tek başına yetmez; o özet de release metadata'sından gelir.
        İmza, depoya erişimin TEK BAŞINA geçerli güncelleme üretmeye
        yetmemesini sağlar.
        """
        if not signing.signing_enabled():
            return
        if not self._signature_url:
            raise VerificationError("yayıncı imzası adresi yok")

        import urllib.request
        with urllib.request.urlopen(self._signature_url, timeout=30) as response:
            if not is_allowed_download_host(response.geturl()):
                raise VerificationError("imza beklenmeyen hedeften geldi")
            # İmza dosyası küçüktür; büyük yanıt kabul edilmez.
            body = response.read(4096)
        try:
            signing.verify(sha256_hex, body.decode("ascii", "replace").strip())
        except signing.SignatureError as exc:
            raise VerificationError(f"yayıncı imzası geçersiz: {exc}")

    def _remove_partial_file(self):
        """Doğrulanmamış dosyayı kaldırır.

        YALNIZCA indirilen dosya silinir; özyinelemeli klasör silme YOKTUR.
        Üst klasör ancak TAMAMEN boşsa kaldırılır, böylece kullanıcının
        TEMP içindeki başka dosyaları korunur.
        """
        remove_downloaded_installer(self._dest)


def remove_downloaded_installer(path):
    """Kullanılmayacak kurulum dosyasını ve boş kalan klasörünü kaldırır."""
    target = Path(path)
    try:
        target.unlink(missing_ok=True)
    except OSError as exc:
        log(f"Could not delete the installer: {exc}", level="WARNING")
        return
    try:
        target.parent.rmdir()      # yalnız klasör TAMAMEN boşsa başarılı
    except OSError:
        pass


def create_update_directory():
    """Create a private per-download directory in the user's local profile.

    ``tempfile.mkdtemp`` creates the leaf with mode ``0o700``. Supported
    Windows Python versions translate that mode to an ACL limited to the
    current user and administrators. The leaf must remain a real directory;
    a reparse-point substitution is rejected before any installer is written.
    """
    base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    folder = Path(tempfile.mkdtemp(prefix="MLCPlayerUpdate_", dir=base))
    attributes = getattr(folder.lstat(), "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if folder.is_symlink() or attributes & reparse_flag:
        try:
            folder.rmdir()
        except OSError:
            pass
        raise VerificationError("güncelleme klasörü reparse noktası")
    return str(folder)


def _open_installer_read_locked(path):
    """Open for reading while denying replacement on Windows.

    ``FILE_SHARE_READ`` lets ShellExecute/CreateProcess read the image but
    denies concurrent write and delete access until the launcher call returns.
    """
    if os.name != "nt":
        return open(path, "rb")

    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = (
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    )
    create_file.restype = wintypes.HANDLE
    handle = create_file(
        str(path), 0x80000000, 0x00000001, None, 3, 0x00000080, None)
    invalid = ctypes.c_void_p(-1).value
    if handle == invalid:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY)
    except Exception:
        kernel32.CloseHandle(handle)
        raise
    return os.fdopen(descriptor, "rb")


@contextmanager
def verified_installer_for_launch(path, expected_sha256, expected_size):
    """Reverify one stable regular file and keep it locked through launch."""
    expected = _positive_size(expected_size)
    digest_text = (expected_sha256 or "").lower()
    if expected is None or not _DIGEST_RE.match(f"sha256:{digest_text}"):
        raise VerificationError("çalıştırma doğrulama verisi eksik veya bozuk")

    target = Path(path)
    try:
        target_lstat = target.lstat()
        parent_lstat = target.parent.lstat()
    except OSError as exc:
        raise VerificationError("kurulum dosyası okunamıyor") from exc
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    for measured in (target_lstat, parent_lstat):
        if getattr(measured, "st_file_attributes", 0) & reparse_flag:
            raise VerificationError("kurulum yolu reparse noktası")
    if target.is_symlink() or target.parent.is_symlink():
        raise VerificationError("kurulum yolu sembolik bağlantı")

    with _open_installer_read_locked(target) as handle:
        before = os.fstat(handle.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise VerificationError("kurulum adayı normal dosya değil")
        digest = hashlib.sha256()
        measured_size = 0
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            measured_size += len(chunk)
            if measured_size > expected:
                raise VerificationError("kurulum adayı beklenenden büyük")
            digest.update(chunk)
        after = os.fstat(handle.fileno())
        try:
            path_state = os.stat(target, follow_symlinks=False)
        except OSError as exc:
            raise VerificationError("kurulum yolu doğrulama sırasında değişti") from exc
        if (not os.path.samestat(before, after)
                or not os.path.samestat(after, path_state)):
            raise VerificationError("kurulum dosyası doğrulama sırasında değişti")
        if measured_size != expected or digest.hexdigest() != digest_text:
            raise VerificationError("kurulum dosyası yeniden doğrulanamadı")
        yield


# ── Kurulumun uygulanması (kooperatif kapanış) ───────────────────────────

def apply_update(installer_path, player, frozen=None, start_installer=None,
                 quit_application=None, expected_sha256="", expected_size=0):
    """Kurulumu başlatır; ÖNCE ürünün kendi kapanış sırası çalışır.

    Referans proje burada `os._exit(0)` çağırıyor. MLC Player'da bu YASAK:
    mpv ve Altyazı Merkezi worker'ları kooperatif kapanışa bağlıdır. Sıra:

    1. `player.close()` — ürünün `closeEvent` sözleşmesi çalışır. Altyazı
       Merkezi'nde süren iş varsa kapanış ERTELENİR ve `close()` False döner.
    2. Pencere gerçekten kapandıysa kurulum başlatılır (`os.startfile`,
       ShellExecute "open" → Inno'nun yönetici manifesti UAC'yi tetikler).
    3. Kapanmadıysa kurulum BAŞLATILMAZ ve neden döndürülür; kullanıcı
       işlem bitince yeniden dener.

    Kaynak (frozen olmayan) modda kurulum çalıştırılmaz; çağıran tarafa
    "source" döner ve release sayfası kullanıcı seçimiyle açılır.

    Dönüş: `("started", "")` · `("busy", mesaj)` · `("source", "")`
    """
    import sys
    is_frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    if not is_frozen:
        return "source", ""

    launching = False
    try:
        with verified_installer_for_launch(
                installer_path, expected_sha256, expected_size):
            if not player.close():
                # Ürün kapanışı erteledi (süren indirme/arama/apply var).
                log("Update: the program could not close, the installer was not started.",
                    level="WARNING")
                return "busy", BUSY_MESSAGE

            launcher = start_installer or os.startfile
            launching = True
            launcher(installer_path)
    except (OSError, VerificationError) as exc:
        if launching:
            raise
        log(f"Update launch verification failed: {exc}", level="WARNING")
        return "verification", VERIFY_FAILED_MESSAGE
    log("Update installer started; the program is closing.")
    quit_app = quit_application
    if quit_app is None:
        from PyQt6.QtWidgets import QApplication
        quit_app = QApplication.quit
    quit_app()
    return "started", ""


# ── Diyalog ──────────────────────────────────────────────────────────────

class UpdateDialog(QDialog):
    """Marka diliyle uyumlu, kompakt güncelleme penceresi."""

    def __init__(self, version, download_url, parent=None, *,
                 expected_sha256="", expected_size=0, signature_url=""):
        super().__init__(parent)
        self._version = version
        self._download_url = download_url
        self._expected_sha256 = expected_sha256
        self._expected_size = expected_size
        self._signature_url = signature_url
        self._downloader = None
        #: Kullanıcı indirme sürerken kapatmak istedi mi? `download_finished`
        #: run() İÇİNDE gelir, yerleşik `finished` ise SONRA; bu bayrak
        #: olmadan kullanıcı kapatmak istese bile kurulum başlardı.
        self._close_requested = False
        self._close_after_download_connected = False
        self._drag_offset = None

        self.setWindowTitle(tr("Güncelleme Mevcut"))
        self.setObjectName("updateDialog")
        self.setWindowFlags(
            (self.windowFlags() | Qt.WindowType.FramelessWindowHint)
            & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(*UPDATE_DIALOG_SIZE)
        self.setStyleSheet(UPDATE_DIALOG_STYLE)
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)

        card = QFrame(self)
        card.setObjectName("updateCard")
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 8)
        shadow.setColor(Qt.GlobalColor.black)
        card.setGraphicsEffect(shadow)
        outer.addWidget(card)

        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        brand = QFrame(card)
        brand.setObjectName("updateBrandPanel")
        brand.setFixedWidth(UPDATE_BRAND_WIDTH)
        brand_layout = QVBoxLayout(brand)
        brand_layout.setContentsMargins(20, 20, 20, 20)
        brand_layout.setSpacing(12)
        brand_layout.addStretch(1)

        icon_label = QLabel(brand)
        icon_label.setObjectName("updateIcon")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setFixedSize(96, 96)
        icon = application_icon()
        if not icon.isNull():
            icon_label.setPixmap(icon.pixmap(88, 88))
        brand_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignHCenter)

        current = self._display_version(APP_VERSION)
        latest = self._display_version(self._version)
        version = QLabel(
            f'<span style="color:#AEB4BB">{current}</span>'
            f'<span style="color:#C7CCD2">  →  </span>'
            f'<span style="color:#F26A3D">{latest}</span>', brand)
        version.setObjectName("updateVersion")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_layout.addWidget(version, 0, Qt.AlignmentFlag.AlignHCenter)
        brand_layout.addStretch(1)
        card_layout.addWidget(brand)

        content = QWidget(card)
        content.setObjectName("updateContentPanel")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 16, 16, 16)
        content_layout.setSpacing(0)

        heading_row = QHBoxLayout()
        heading_row.setContentsMargins(0, 0, 0, 0)
        heading = QLabel(tr("Yeni sürüm kullanıma hazır"), content)
        heading.setObjectName("updateHeading")
        heading_row.addWidget(heading, 1)

        self._close_button = QPushButton("×", content)
        self._close_button.setObjectName("updateClose")
        self._close_button.setAccessibleName(tr("Kapat"))
        self._close_button.setAutoDefault(False)
        self._close_button.setDefault(False)
        self._close_button.clicked.connect(self.reject)
        heading_row.addWidget(self._close_button, 0,
                              Qt.AlignmentFlag.AlignTop)
        content_layout.addLayout(heading_row)
        content_layout.addSpacing(22)

        description = QLabel(
            tr("MLC Player {version} indirilmeye hazır.").format(
                version=latest), content)
        description.setObjectName("updateDescription")
        content_layout.addWidget(description)
        content_layout.addSpacing(12)

        supporting = QLabel(
            tr("Değişiklikleri sürüm notlarında inceleyebilirsiniz."),
            content)
        supporting.setObjectName("updateSupportingText")
        supporting.setWordWrap(True)
        content_layout.addWidget(supporting)
        content_layout.addSpacing(8)

        self._release_notes_button = QPushButton(
            tr("Sürüm notları →"), content)
        self._release_notes_button.setObjectName("updateReleaseNotes")
        self._release_notes_button.setCursor(
            Qt.CursorShape.PointingHandCursor)
        self._release_notes_button.setAutoDefault(False)
        self._release_notes_button.setDefault(False)
        self._release_notes_button.clicked.connect(self.open_release_notes)
        self._release_notes_button.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        content_layout.addWidget(self._release_notes_button, 0,
                                 Qt.AlignmentFlag.AlignLeft)
        content_layout.addStretch(1)

        self._progress = QProgressBar()
        self._progress.setObjectName("updateProgress")
        self._progress.setRange(0, 100)
        self._progress.setTextVisible(False)
        self._progress.setVisible(False)
        content_layout.addWidget(self._progress)

        self._status = QLabel("")
        self._status.setObjectName("updateStatus")
        self._status.setVisible(False)
        content_layout.addSpacing(7)
        content_layout.addWidget(self._status)
        content_layout.addSpacing(10)

        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch(1)
        self._later_button = QPushButton(tr("Daha sonra"))
        self._later_button.setObjectName("updateLater")
        self._later_button.setAutoDefault(False)
        self._later_button.setDefault(False)
        self._later_button.clicked.connect(self.reject)
        self._update_button = QPushButton(tr("Güncelle"))
        self._update_button.setObjectName("updatePrimary")
        self._update_button.setAutoDefault(False)
        self._update_button.setDefault(True)
        self._update_button.clicked.connect(self.start_update)
        row.addWidget(self._later_button)
        row.addWidget(self._update_button)
        content_layout.addLayout(row)
        card_layout.addWidget(content, 1)

    @staticmethod
    def _display_version(version):
        value = str(version or "").strip()
        return value[1:] if value[:1].lower() == "v" else value

    def release_notes_url(self):
        tag = quote(str(self._version or ""), safe="")
        return f"{GITHUB_URL}/releases/tag/{tag}"

    def open_release_notes(self):
        import webbrowser
        webbrowser.open(self.release_notes_url())

    def mousePressEvent(self, event):
        if (event.button() == Qt.MouseButton.LeftButton
                and (event.position().x() <= UPDATE_BRAND_WIDTH + 14
                     or event.position().y() <= 82)):
            child = self.childAt(event.position().toPoint())
            if not isinstance(child, QPushButton):
                self._drag_offset = (
                    event.globalPosition().toPoint()
                    - self.frameGeometry().topLeft())
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (self._drag_offset is not None
                and event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def start_update(self):
        if (not self._download_url or not self._expected_sha256
                or _positive_size(self._expected_size) is None):
            # Fail-closed: doğrulama verisi olmadan indirme YAPILMAZ ve
            # tarayıcı KENDİLİĞİNDEN açılmaz.
            log("Update verification data is missing; the download was not started.",
                level="WARNING")
            self.show_error(VERIFY_FAILED_MESSAGE)
            return

        self._update_button.setEnabled(False)
        self._later_button.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._status.setVisible(True)
        self._status.setText(tr("İndiriliyor…"))

        try:
            folder = create_update_directory()
        except (OSError, VerificationError) as exc:
            log(f"Update directory creation failed: {exc}", level="WARNING")
            self._restore_buttons()
            self.show_error(DOWNLOAD_FAILED_MESSAGE)
            return
        destination = os.path.join(folder, expected_asset_name(self._version))
        self._downloader = UpdateDownloader(self._download_url, destination,
                                            self._expected_sha256,
                                            self._expected_size, self,
                                            signature_url=self._signature_url)
        self._downloader.progress.connect(self._progress.setValue)
        self._downloader.download_finished.connect(self.on_downloaded)
        self._downloader.failed.connect(self.on_download_failed)
        self._downloader.start()

    def on_downloaded(self, installer_path):
        if self._close_requested:
            # Kullanıcı kapatmak istedi: kurulum BAŞLATILMAZ.
            log("The download finished but a close was requested; the installer is not started.")
            remove_downloaded_installer(installer_path)
            return
        self._status.setText(tr("Güncelleme uygulanıyor…"))
        outcome, message = apply_update(
            installer_path, self._update_target(),
            expected_sha256=self._expected_sha256,
            expected_size=self._expected_size)
        if outcome == "busy":
            self._restore_buttons()
            self.show_error(message)
            remove_downloaded_installer(installer_path)
            return
        if outcome == "source":
            # Kaynaktan çalışan geliştirme kopyası: kurulum uygulanmaz.
            self._restore_buttons()
            self.show_error(tr_mark(
                "Kaynak koddan çalışan kopya kurulumla güncellenmez."))
            remove_downloaded_installer(installer_path)
            return
        if outcome == "verification":
            self._restore_buttons()
            self.show_error(message)
            remove_downloaded_installer(installer_path)
            return
        self.accept()

    def _update_target(self):
        """Kapanacak ana pencere: diyalogun sahibi."""
        return self.parent() if self.parent() is not None else self

    def _restore_buttons(self):
        self._progress.setVisible(False)
        self._status.setVisible(False)
        self._update_button.setEnabled(True)
        self._later_button.setEnabled(True)

    def on_download_failed(self, message):
        if self._close_requested:
            log(f"Update download failed (a close was requested): {message}")
            return
        self._restore_buttons()
        self.show_error(message)

    def show_error(self, message):
        """Kısa hata + AYRI kullanıcı seçimi olarak release sayfası.

        Tarayıcı yalnız kullanıcı düğmeye basarsa açılır; doğrulama hatası
        hiçbir otomatik eylemi tetiklemez.
        """
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(tr("Güncelleme"))
        box.setText(translate_marked(message))
        box.setInformativeText(
            tr("İsterseniz güncellemeyi GitHub sayfasından elle "
               "indirebilirsiniz."))
        manual = box.addButton(tr("GitHub sayfasını aç"),
                               QMessageBox.ButtonRole.ActionRole)
        box.addButton(tr("Kapat"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is manual:
            open_releases_page()

    def closeEvent(self, event):
        """İndirme sürerken gelen kapatma isteğini ERTELER.

        Çalışan indirici bu diyalogun çocuğudur; iş bitmeden yok edilirse Qt
        süreci abort eder. UI thread'inde BEKLEME yapılmaz: thread'in
        yerleşik `finished` sinyaline tek seferlik bağlanılır.
        """
        if self._downloader is not None and self._downloader.isRunning():
            self._close_requested = True
            if not self._close_after_download_connected:
                self._downloader.finished.connect(self.close)
                self._close_after_download_connected = True
                self._status.setVisible(True)
                self._status.setText(
                    tr("İndirme tamamlanıyor — pencere işlem bitince "
                       "kapanacak."))
            event.ignore()
            return
        event.accept()

    def reject(self):
        """"Daha sonra" ve Esc de aynı güvenli kapanış yolunu kullanır."""
        if self._downloader is not None and self._downloader.isRunning():
            self.close()
            return
        super().reject()


def open_releases_page():
    import webbrowser
    webbrowser.open(f"{GITHUB_URL}/releases/latest")


# ── Giriş noktaları ──────────────────────────────────────────────────────

def start_startup_check(player):
    """Açılışta SESSİZ kontrol. Güncelleme yoksa hiçbir şey gösterilmez."""
    checker = UpdateChecker(player, timeout=STARTUP_CHECK_TIMEOUT, silent=True)

    def _show(version, url, sha256, size, signature_url):
        UpdateDialog(version, url, player, expected_sha256=sha256,
                     expected_size=size, signature_url=signature_url).exec()

    checker.update_available.connect(_show, Qt.ConnectionType.QueuedConnection)
    checker.start()
    return checker


def check_for_updates(player):
    """`Yardım → Güncellemeleri Denetle`: sonuç HER durumda bildirilir."""
    checker = UpdateChecker(player, timeout=MANUAL_CHECK_TIMEOUT)

    def _show(version, url, sha256, size, signature_url):
        UpdateDialog(version, url, player, expected_sha256=sha256,
                     expected_size=size, signature_url=signature_url).exec()

    def _up_to_date():
        QMessageBox.information(
            player, tr("Güncelleme"),
            f"{tr('En güncel sürümü kullanıyorsunuz')} ({APP_VERSION}).")

    def _failed(message):
        QMessageBox.warning(player, tr("Güncelleme"),
                            translate_marked(message))

    checker.update_available.connect(_show, Qt.ConnectionType.QueuedConnection)
    checker.no_update.connect(_up_to_date, Qt.ConnectionType.QueuedConnection)
    checker.check_failed.connect(_failed, Qt.ConnectionType.QueuedConnection)
    checker.start()
    return checker
