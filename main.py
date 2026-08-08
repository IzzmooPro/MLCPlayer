import os
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

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


# DLL yükleme ve bağımlılık kontrolü
def check_dependencies():
    global _dll_dir_handle
    # MPV DLL konumunu (bin/) PATH'e ekle
    bin_dir = get_bin_dir()
    os.environ["PATH"] = bin_dir + os.pathsep + os.environ["PATH"]

    # Python 3.8+ için DLL dizinini doğrudan ekle
    try:
        # Handle saklanmazsa Python DLL arama yolu bazı sistemlerde erken kapanabilir.
        _dll_dir_handle = os.add_dll_directory(bin_dir)
        print(f"DLL dizini eklendi: {bin_dir}")
    except Exception as e:
        print(f"DLL dizini ekleme hatası (devam ediliyor): {e}")

    # DLL dosyalarının varlığını kontrol et
    # Not: DLL'leri burada ctypes ile manuel yüklemeyin. python-mpv,
    # mpv-2.dll -> libmpv-2.dll -> mpv-1.dll sırasıyla kendisi yükler.
    # Projede mpv-2.dll yeterlidir (diğer ikisi yedekti ve kaldırıldı).
    required_dlls = ["mpv-2.dll"]
    found_dlls = [dll for dll in required_dlls if os.path.exists(os.path.join(bin_dir, dll))]
    if not found_dlls:
        print(f"Error: None of the required DLLs (mpv-1.dll, mpv-2.dll, libmpv-2.dll) were found in {bin_dir}.")
        return False

    print(f"Bulunan MPV DLL dosyaları: {', '.join(found_dlls)}")

    # MPV modülünü içe aktar
    try:
        import mpv  # noqa: F401 - importun kendisi yükleme kontrolüdür
        print("MPV modülü başarıyla içe aktarıldı.")
        return True
    except Exception as e:
        print(f"MPV modülü yükleme hatası: {e}")
        print("Python-MPV paketinin kurulu olduğundan emin olun: pip install python-mpv")
        return False

if __name__ == "__main__":
    app = QApplication(sys.argv)
    from app.errors import install_exception_handler, show_error, log
    install_exception_handler()

    if check_dependencies():
        from app.player import MPVPlayer
        player = MPVPlayer()
        player.show()
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
        log("DLL bulunamadı - program kapatılıyor", 'ERROR')
        show_error(
            "MPV Bileşeni Bulunamadı",
            "Program çalıştırılamadı: gerekli MPV bileşeni (mpv-2.dll) bulunamadı.\n\n"
            "Çözüm: Programın yanındaki 'bin' klasörünün eksiksiz olduğundan emin olun. "
            "Programı kurulum klasöründen başlatın.\n\n"
            "Bu klasör silinmiş veya program başka bir yere taşınmış olabilir."
        )
        sys.exit(1)
