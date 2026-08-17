# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
import os
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

# Konsol cikisinin merkezi guvenli siniri (bkz. app/errors.py).
from app.errors import safe_console

_dll_dir_handle = None


def get_bin_dir():
    """bin/ dizinini exe-uyumlu şekilde bulur.

    Adım adım arar (ilk bulunan geçerli):
      1. PyInstaller paketlemesi  -> sys._MEIPASS/bin  (--add-data ile gömülü)
      2. EXE'nin yanındaki klasör -> <exe_dir>/bin     (exe ile birlikte taşınan)
      3. Geliştirme dizini        -> <main.py>/bin     (kaynak koddan çalıştırma)
    """
    candidates = []

    # 1. PyInstaller'ın çıkardığı geçici klasör
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        candidates.append(os.path.join(meipass, 'bin'))

    # 2. EXE'nin bulunduğu klasör (frozen ortam)
    if getattr(sys, 'frozen', False) and sys.executable:
        candidates.append(os.path.join(os.path.dirname(sys.executable), 'bin'))

    # 3. Kaynak koddan çalışırken main.py'nin yanı
    candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bin'))

    for candidate in candidates:
        if os.path.isdir(candidate):
            return candidate
    return candidates[-1]


def prepend_process_path(bin_dir):
    """`bin` dizinini YALNIZ bu surecin PATH'ine ve TEK KEZ ekler.

    Windows/kullanici PATH'i KALICI olarak degistirilmez; registry veya
    environment ayari YAZILMAZ. Ayni cagri PATH'i cogaltmaz.
    """
    current = os.environ.get("PATH", "")
    entries = [entry for entry in current.split(os.pathsep) if entry]
    if entries and entries[0] == bin_dir:
        return current
    entries = [entry for entry in entries if entry != bin_dir]
    updated = os.pathsep.join([bin_dir] + entries)
    os.environ["PATH"] = updated
    return updated


# DLL yükleme ve bağımlılık kontrolü
def check_dependencies():
    global _dll_dir_handle
    # MPV DLL ve paketlenen internet-video bileşenleri aynı `bin` dizininde.
    # Alt süreçler (mpv -> yt-dlp -> deno) bu SÜREÇ PATH'ini miras alır.
    bin_dir = get_bin_dir()
    prepend_process_path(bin_dir)

    # Python 3.8+ için DLL dizinini doğrudan ekle
    try:
        # Handle saklanmazsa Python DLL arama yolu bazı sistemlerde erken kapanabilir.
        _dll_dir_handle = os.add_dll_directory(bin_dir)
        safe_console(f"DLL dizini eklendi: {bin_dir}")
    except Exception as e:
        safe_console(f"DLL directory error (continuing): {e}")

    # DLL dosyalarının varlığını kontrol et
    # Not: DLL'leri burada ctypes ile manuel yüklemeyin. python-mpv,
    # mpv-2.dll -> libmpv-2.dll -> mpv-1.dll sırasıyla kendisi yükler.
    # Projede mpv-2.dll yeterlidir (diğer ikisi yedekti ve kaldırıldı).
    required_dlls = ["mpv-2.dll"]
    found_dlls = [dll for dll in required_dlls if os.path.exists(os.path.join(bin_dir, dll))]
    if not found_dlls:
        safe_console(f"Error: None of the required DLLs (mpv-1.dll, mpv-2.dll, libmpv-2.dll) were found in {bin_dir}.")
        return False

    safe_console(f"MPV DLL files found: {', '.join(found_dlls)}")

    # Internet videosu bilesenleri EKSIK olsa bile program acilir ve yerel
    # dosya oynatmaya devam eder. Yalniz guvenli durum kodu loglanir; yol
    # veya istisna YAZILMAZ.
    try:
        from app.runtime_binaries import internet_video_status
        safe_console(f"Internet video runtime: {internet_video_status(bin_dir)}")
    except Exception:
        pass

    # MPV modülünü içe aktar
    try:
        import mpv  # noqa: F401 - importun kendisi yükleme kontrolüdür
        safe_console("MPV module imported successfully.")
        return True
    except Exception as e:
        safe_console(f"MPV module import error: {e}")
        safe_console("Make sure the python-mpv package is installed: pip install python-mpv")
        return False

if __name__ == "__main__":
    # Thumbnail işi ayrı süreçte ve ana oynatıcı penceresi kurulmadan çalışır.
    # Frozen pakette ThumbnailService aynı EXE'yi bu özel argümanla yeniden
    # başlatır; böylece kullanıcıya FFmpeg/Python kurdurulmaz.
    if len(sys.argv) >= 2 and sys.argv[1] == "--thumbnail-worker":
        if len(sys.argv) != 4 or not check_dependencies():
            os._exit(64)
        from app.thumbnail_worker import generate_thumbnail
        os._exit(generate_thumbnail(sys.argv[2], sys.argv[3]))

    app = QApplication(sys.argv)

    # DİL: Windows'un dilinden seçilir; kullanıcı ayarlardan sabitleyebilir
    # (Araçlar → Dil). Çeviri dosyası yoksa program kaynak dilde (Türkçe)
    # açılır ve ÇÖKMEZ. Pencere kurulmadan ÖNCE yapılır ki menüler doğru
    # dille oluşsun.
    from app.i18n import apply_language
    _language, _translated = apply_language(app)
    safe_console(f"Interface language: {_language} (translation loaded: {_translated})")

    # TEK KOPYA: ikinci başlatma yeni pencere açmaz. Ağır kurulumdan ÖNCE
    # karar verilir; devreden süreç hemen kapanır. İşçi süreçler yukarıda
    # zaten dönmüştür, bu satıra hiç gelmezler.
    from app.single_instance import SingleInstanceGuard, activate_window
    instance_guard = SingleInstanceGuard()
    if not instance_guard.acquire(sys.argv[1] if len(sys.argv) > 1 else ""):
        sys.exit(0)

    # Ortak gorsel kimlik: ana pencere veya herhangi bir dialog
    # OLUSTURULMADAN once kurulur. Boylece butun ust seviye pencereler
    # ayni ikonu miras alir.
    from app.app_icon import install_application_identity
    safe_console(f"Uygulama ikonu: {install_application_identity(app)}")
    from app.errors import install_exception_handler, show_error, log
    install_exception_handler()

    if check_dependencies():
        from app.player import MPVPlayer
        player = MPVPlayer()
        player.show()
        # Başka bir başlatma isteği: pencere öne gelir, dosya BURAYA yüklenir.
        instance_guard.activation_requested.connect(
            lambda payload: activate_window(player, payload))
        # Açılışta SESSİZ güncelleme kontrolü: güncelleme yoksa hiçbir şey
        # gösterilmez. YALNIZ paketlenmiş kopyada çalışır — kaynaktan çalışan
        # kopya kurulumla güncellenemez ve her geliştirme koşumunda ağa
        # çıkmasının anlamı yoktur. `MLC_DISABLE_UPDATE_CHECK=1` kapatır.
        if (getattr(sys, "frozen", False)
                and os.environ.get("MLC_DISABLE_UPDATE_CHECK") != "1"):
            from app.updater import start_startup_check
            # Referans çöp toplayıcı tarafından alınmasın diye tutulur.
            player._update_checker = start_startup_check(player)
        # Komut satırından dosya/URL argümanı: python main.py video.mp4
        if len(sys.argv) > 1:
            QTimer.singleShot(0, lambda: player.open_path(sys.argv[1]))
        ret = app.exec()
        # NOT: mpv DLL'leri bu yapıda interpreter kapanışında takılıyor
        # (thread-safe olmayan DLL yıkımı). Normal Python finalizasyonu
        # yerine os._exit ile süreci temiz kapat (pencere zaten kapatıldı,
        # mpv zaten sonlandırıldı). Bu, bilinen bir Windows + libmpv davranışıdır.
        os._exit(ret)
    else:
        log("DLL not found - shutting down", 'ERROR')
        from app.i18n import tr
        show_error(
            tr("MPV Bileşeni Bulunamadı"),
            tr("Program çalıştırılamadı: gerekli MPV bileşeni (mpv-2.dll) "
               "bulunamadı.\n\nÇözüm: Programın yanındaki 'bin' klasörünün "
               "eksiksiz olduğundan emin olun. Programı kurulum klasöründen "
               "başlatın.\n\nBu klasör silinmiş veya program başka bir yere "
               "taşınmış olabilir.")
        )
        sys.exit(1)
