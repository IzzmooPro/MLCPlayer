"""MLC Player'in TEK gorsel kimligi.

Ayni logo EXE, gorev cubugu, Alt+Tab, ana pencere, ozel TitleBar, butun
QDialog'lar ve QMessageBox baslik cubuklarinda kullanilir. Python,
PyInstaller, Qt varsayilani veya standart DVD ikonu HICBIR kosulda
kullanilmaz ve bilincli fallback olarak ATANMAZ: asset yoksa bos QIcon
donulur, program calismaya devam eder.

Asset TEK kaynaktan cozulur:
  - paketli (onedir): `sys._MEIPASS\\assets\\mlc-player-icon.ico`
  - gelistirme      : proje `assets\\mlc-player-icon.ico`

Registry veya sistem ayari YAZILMAZ.
"""
import os
import sys

from PyQt6.QtGui import QIcon

APP_NAME = "MLC Player"
# SEFFAF surum: masaustu kisayolunda ikonun arkasindaki koyu plaka
# gorunuyordu (kullanici bildirimi). Uretimi: packaging/make_app_icon.py.
# Kurulum sihirbazinin gorselleri BILEREK eski (plakali) sanati kullanir;
# onlar koyu panel uzerinde duruyor.
ICON_FILE_NAME = "mlc-player-icon-transparent.ico"
ASSETS_DIR_NAME = "assets"

# Windows gorev cubugu gruplamasi icin SABIT kimlik.
APP_USER_MODEL_ID = "MLCPlayer.MLCPlayer"

# Guvenli log kodlari: yol veya istisna TASIMAZ.
ICON_READY_CODE = "APP_ICON_READY"
ICON_MISSING_CODE = "APP_ICON_MISSING"

# Ayni QIcon her pencerede yeniden diskten okunmaz.
_cached_icon = None
_cache_filled = False


def assets_dir():
    """Paketli ve gelistirme ortaminda calisan TEK asset kokü."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return os.path.join(meipass, ASSETS_DIR_NAME)
    project = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(project, ASSETS_DIR_NAME)


def icon_path():
    """Uygulama ikonunun TAM yolu (dosya yoksa da beklenen yol)."""
    return os.path.join(assets_dir(), ICON_FILE_NAME)


def icon_status():
    """Loga yazilabilecek GUVENLI durum kodu; yol icermez."""
    try:
        return ICON_READY_CODE if os.path.isfile(icon_path()) \
            else ICON_MISSING_CODE
    except (OSError, ValueError):
        return ICON_MISSING_CODE


def _load_icon():
    """Diskten TEK okuma. Eksik asset bos QIcon uretir; fallback YOK."""
    path = icon_path()
    try:
        if not os.path.isfile(path):
            return QIcon()
    except (OSError, ValueError):
        return QIcon()
    try:
        return QIcon(path)
    except Exception:
        return QIcon()


def application_icon():
    """Ortak QIcon (onbellekli). Ayni nesne her yerde paylasilir."""
    global _cached_icon, _cache_filled
    if not _cache_filled:
        _cached_icon = _load_icon()
        _cache_filled = True
    return _cached_icon


def reset_icon_cache():
    """Yalniz test/yeniden yukleme icin onbellegi bosaltir."""
    global _cached_icon, _cache_filled
    _cached_icon = None
    _cache_filled = False


def install_application_identity(application):
    """QApplication kimligi + ortak ikon. Pencere olusturulmadan ONCE.

    Windows'ta gorev cubugu gruplamasi icin sabit AppUserModelID ayarlanir;
    bu cagri YALNIZ Windows'ta yapilir ve hatasi program baslangicini
    ENGELLEMEZ. Sistem ayari veya registry yazilmaz.
    """
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                APP_USER_MODEL_ID)
        except Exception:
            pass
    try:
        application.setApplicationName(APP_NAME)
        application.setApplicationDisplayName(APP_NAME)
        application.setOrganizationName(APP_NAME)
    except Exception:
        pass
    icon = application_icon()
    if not icon.isNull():
        try:
            application.setWindowIcon(icon)
        except Exception:
            pass
    return icon_status()


def apply_window_icon(widget):
    """Bir pencereye ORTAK ikonu uygular; her yerde ayni kaynak.

    Asset yoksa hicbir sey yapilmaz (varsayilan ikon ATANMAZ) ve ham hata
    kullaniciya cikmaz.
    """
    icon = application_icon()
    if icon.isNull() or widget is None:
        return False
    try:
        widget.setWindowIcon(icon)
    except (AttributeError, RuntimeError):
        return False
    return True
