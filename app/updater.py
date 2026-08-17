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
import tempfile
from collections import namedtuple
from pathlib import Path
from urllib.parse import urlsplit
from app.i18n import tr, tr_mark, translate_marked

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QMessageBox,
                             QProgressBar, QPushButton, QVBoxLayout)

from app import release_signature as signing
from app.config import APP_VERSION
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
        log(f"{source}: güncelleme asset'i doğrulanamadı ({reason}); "
            f"otomatik güncelleme sunulmuyor.", level="WARNING")
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
            log(f"Güncelleme kontrolü başarısız: {exc}", level="WARNING")
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
            log(f"Güncelleme doğrulaması başarısız: {exc}", level="WARNING")
            self._remove_partial_file()
            self.failed.emit(VERIFY_FAILED_MESSAGE)
        except Exception as exc:
            log(f"Güncelleme indirilemedi: {exc}", level="WARNING")
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
        log(f"Kurulum dosyası silinemedi: {exc}", level="WARNING")
        return
    try:
        target.parent.rmdir()      # yalnız klasör TAMAMEN boşsa başarılı
    except OSError:
        pass


# ── Kurulumun uygulanması (kooperatif kapanış) ───────────────────────────

def apply_update(installer_path, player, frozen=None, start_installer=None,
                 quit_application=None):
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

    if not player.close():
        # Ürün kapanışı erteledi (süren indirme/arama/apply var).
        log("Güncelleme: program kapanamadı, kurulum başlatılmadı.",
            level="WARNING")
        return "busy", BUSY_MESSAGE

    launcher = start_installer or os.startfile
    launcher(installer_path)
    log("Güncelleme kurulumu başlatıldı; program kapanıyor.")
    quit_app = quit_application
    if quit_app is None:
        from PyQt6.QtWidgets import QApplication
        quit_app = QApplication.quit
    quit_app()
    return "started", ""


# ── Diyalog ──────────────────────────────────────────────────────────────

class UpdateDialog(QDialog):
    """"Yeni bir sürüm bulundu." — Güncelle / Daha sonra."""

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

        self.setWindowTitle(tr("Güncelleme Mevcut"))
        self.setFixedWidth(400)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        message = QLabel(f"{tr('Yeni bir sürüm bulundu.')}\n\n"
                         f"{tr('Mevcut sürüm')} : {APP_VERSION}\n"
                         f"{tr('Yeni sürüm')}   : {self._version}")
        message.setWordWrap(True)
        layout.addWidget(message)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._status = QLabel("")
        self._status.setVisible(False)
        layout.addWidget(self._status)

        row = QHBoxLayout()
        self._later_button = QPushButton("Daha sonra")
        self._later_button.clicked.connect(self.reject)
        self._update_button = QPushButton(tr("Güncelle"))
        self._update_button.clicked.connect(self.start_update)
        row.addWidget(self._later_button)
        row.addStretch()
        row.addWidget(self._update_button)
        layout.addLayout(row)

    def start_update(self):
        if (not self._download_url or not self._expected_sha256
                or _positive_size(self._expected_size) is None):
            # Fail-closed: doğrulama verisi olmadan indirme YAPILMAZ ve
            # tarayıcı KENDİLİĞİNDEN açılmaz.
            log("Güncelleme doğrulama verisi eksik; indirme başlatılmadı.",
                level="WARNING")
            self.show_error(VERIFY_FAILED_MESSAGE)
            return

        self._update_button.setEnabled(False)
        self._later_button.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._status.setVisible(True)
        self._status.setText(tr("İndiriliyor…"))
        self.adjustSize()

        folder = tempfile.mkdtemp(prefix="MLCPlayerUpdate_")
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
            log("İndirme bitti ancak kapatma istendi; kurulum başlatılmıyor.")
            remove_downloaded_installer(installer_path)
            return
        self._status.setText(tr("Güncelleme uygulanıyor…"))
        outcome, message = apply_update(installer_path, self._update_target())
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
            log(f"Güncelleme indirmesi başarısız (kapanış istendi): {message}")
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
                self.adjustSize()
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
