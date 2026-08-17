# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""MLC Player TEK gorsel kimlik: uygulama ikonu her yerde ayni.

URUN KARARI: kullanicinin sectigi tek logo EXE, gorev cubugu, Alt+Tab, ana
pencere, ozel TitleBar, butun QDialog'lar ve QMessageBox baslik cubuklarinda
kullanilir. Python, PyInstaller, Qt varsayilani veya standart DVD ikonu
HICBIR yerde gorunmez ve bilincli fallback olarak ATANMAZ.

Bu dosya PyInstaller build, dist veya setup URETMEZ; yalniz kaynak asset ve
ikon sozlesmesini kilitler.
"""
import hashlib
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QApplication, QDialog, QLabel, QMainWindow,
                             QMessageBox, QPushButton, QWidget)

#: Logonun üstünde ve altında bırakılması gereken EN AZ boşluk (px).
#: Taşma sınırı buradan ve `TITLE_BAR_HEIGHT`ten türetilir; sabit bir
#: logo ölçüsü şart koşulmaz.
MIN_LOGO_BREATHING = 6

import app.app_icon as app_icon

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(PROJECT, "assets")
PNG = os.path.join(ASSETS, "mlc-player-icon.png")
ICO = os.path.join(ASSETS, "mlc-player-icon.ico")
# Uygulama SEFFAF surumu kullanir (masaustu kisayolunda koyu plaka
# gorunuyordu); plakali sanat kurulum sihirbazinda kalir.
APP_ICO = os.path.join(ASSETS, "mlc-player-icon-transparent.ico")
MANIFEST = os.path.join(ASSETS, "ICON_MANIFEST.txt")
SPEC = os.path.join(PROJECT, "MLCPlayer.spec")

REQUIRED_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)
SOURCE_SIZE = (1254, 1254)


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def sha256_of(path):
    sha = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest().lower()


@pytest.fixture(scope="module")
def qt_app():
    application = QApplication.instance() or QApplication([])
    # Urunun KENDI kurulum yolu; test kendi ikonunu uydurmaz.
    app_icon.install_application_identity(application)
    return application


# =====================================================================
# 1. Kaynak asset
# =====================================================================

def test_the_source_png_is_the_untouched_square_rgba_logo():
    assert os.path.isfile(PNG), "kalıcı PNG yok"
    with Image.open(PNG) as image:
        assert image.size == SOURCE_SIZE
        assert image.mode == "RGBA"


def test_the_four_corners_are_really_transparent():
    with Image.open(PNG) as image:
        rgba = image.convert("RGBA")
    width, height = rgba.size
    corners = ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1))

    assert [rgba.getpixel(point)[3] for point in corners] == [0, 0, 0, 0]


def test_the_manifest_records_the_source_and_both_assets():
    text = read(MANIFEST)

    assert "1254" in text
    assert "RGBA" in text.upper()
    assert "mlc-player-icon.png" in text
    assert "mlc-player-icon.ico" in text
    # Kullanicinin gecici pano yolu URUNE/BELGEYE kalici yazilmaz.
    assert "codex-clipboard" not in text
    assert "AppData" not in text and "Temp" not in text


@pytest.mark.parametrize("name, path", (("mlc-player-icon.png", PNG),
                                        ("mlc-player-icon.ico", ICO)))
def test_the_manifest_hash_matches_the_file(name, path):
    expected = ""
    for line in read(MANIFEST).splitlines():
        parts = [part.strip() for part in line.split("|")]
        if len(parts) >= 3 and parts[0] == name:
            expected = parts[-1].lower()
            break

    assert expected, f"manifestte satır yok: {name}"
    assert sha256_of(path) == expected


# =====================================================================
# 2. Windows ICO
# =====================================================================

def test_the_ico_carries_every_required_resolution():
    assert os.path.isfile(ICO), "ICO yok"
    with Image.open(ICO) as image:
        sizes = {size[0] for size in image.info.get("sizes", ())}

    for needed in REQUIRED_SIZES:
        assert needed in sizes, f"ICO'da {needed}px yok: {sorted(sizes)}"


def test_every_ico_frame_is_square_and_keeps_its_alpha():
    with Image.open(ICO) as image:
        for size in REQUIRED_SIZES:
            image.size = (size, size)
            frame = image.convert("RGBA")
            assert frame.size == (size, size)
            corner = frame.getpixel((0, 0))
            # LANCZOS yumusak kenarda 0 yerine 1 birakabilir; olcut
            # "opak degil"dir, birebir sifir degil.
            assert corner[3] <= 8, f"{size}px köşesi opak: {corner}"


# =====================================================================
# 3. Tek runtime asset yolu
# =====================================================================

def test_the_icon_path_points_at_the_project_assets_in_development():
    assert app_icon.icon_path() == APP_ICO


def test_a_frozen_build_reads_the_bundled_assets(monkeypatch, tmp_path):
    monkeypatch.setattr(app_icon.sys, "_MEIPASS", str(tmp_path), raising=False)

    expected = os.path.join(str(tmp_path), "assets",
                            "mlc-player-icon-transparent.ico")
    assert app_icon.icon_path() == expected


def test_a_missing_asset_never_crashes_and_never_falls_back(monkeypatch,
                                                            tmp_path, qt_app):
    monkeypatch.setattr(app_icon.sys, "_MEIPASS", str(tmp_path), raising=False)
    app_icon.reset_icon_cache()
    try:
        icon = app_icon.application_icon()

        assert icon.isNull(), "eksik asset yerine varsayılan ikon atandı"
        assert app_icon.icon_status() == app_icon.ICON_MISSING_CODE
        assert "\\" not in app_icon.ICON_MISSING_CODE
    finally:
        app_icon.reset_icon_cache()


def test_the_icon_is_loaded_from_disk_only_once(qt_app, monkeypatch):
    app_icon.reset_icon_cache()
    loads = []
    real = app_icon._load_icon
    monkeypatch.setattr(app_icon, "_load_icon",
                        lambda: (loads.append(1), real())[1])

    first = app_icon.application_icon()
    for _ in range(50):
        app_icon.application_icon()

    assert len(loads) == 1, f"ikon {len(loads)} kez diskten okundu"
    assert app_icon.application_icon() is first


# =====================================================================
# 4. QApplication kimligi
# =====================================================================

def test_the_application_identity_is_mlc_player(qt_app):
    assert qt_app.applicationName() == "MLC Player"
    assert qt_app.windowIcon().isNull() is False


def test_the_app_user_model_id_is_stable():
    assert app_icon.APP_USER_MODEL_ID == "MLCPlayer.MLCPlayer"


def test_main_sets_the_icon_before_any_window_is_built():
    source = read(os.path.join(PROJECT, "main.py"))

    identity = source.index("install_application_identity")
    application = source.index("QApplication(sys.argv)")
    player = source.index("MPVPlayer()")
    assert application < identity < player, (
        "ikon kimliği QApplication'dan sonra ve pencereden ÖNCE kurulmuyor")


def test_the_model_id_is_windows_only_and_never_writes_the_registry():
    import inspect

    source = inspect.getsource(app_icon.install_application_identity)
    module = read(os.path.join(PROJECT, "app", "app_icon.py"))

    assert "win32" in source or "nt" in source, "Windows koşulu yok"
    for forbidden in ("winreg", "HKEY_", "setx"):
        assert forbidden not in module, f"sistem ayarı yazımı: {forbidden}"


# =====================================================================
# 5. Eski DVD/varsayilan ikon
# =====================================================================

def test_no_production_code_uses_a_standard_or_default_icon():
    for relative in ("app/player.py", "app/title_bar.py", "main.py",
                     "app/media_info_dialog.py", "app/app_icon.py"):
        source = read(os.path.join(PROJECT, relative))
        for forbidden in ("SP_DriveDVDIcon", "SP_ComputerIcon",
                          "SP_MediaPlay", "standardIcon"):
            assert forbidden not in source, f"{relative}: {forbidden}"


# =====================================================================
# 6. Gercek pencereler ortak ikonu aliyor
# =====================================================================

def test_the_real_main_window_uses_the_shared_icon(qt_app):
    import inspect

    from app.player import MPVPlayer

    source = inspect.getsource(MPVPlayer.__init__)
    assert "setWindowIcon" not in source or "application_icon" in source, (
        "ana pencere kendi ikonunu uyduruyor")


def test_a_parented_dialog_inherits_the_application_icon(qt_app):
    parent = QMainWindow()
    dialog = QDialog(parent)
    app_icon.apply_window_icon(dialog)

    assert dialog.windowIcon().isNull() is False
    dialog.close()
    parent.close()


def test_a_parentless_message_box_inherits_the_application_icon(qt_app):
    box = QMessageBox()
    app_icon.apply_window_icon(box)

    assert box.windowIcon().isNull() is False
    # Uyarı/hata SEMBOLÜ kaldırılmaz; yalnız pencere kimliği MLC Player olur.
    box.setIcon(QMessageBox.Icon.Warning)
    assert box.icon() == QMessageBox.Icon.Warning
    box.close()


def test_a_plain_dialog_inherits_without_any_per_file_call(qt_app):
    """GERCEK sozlesme: QApplication ikonu TUM ust seviye pencerelere
    kendiliginden miras kalir. Her dialoga ayri dosya yolu KOPYALANMAZ."""
    parent = QMainWindow()
    dialog = QDialog(parent)        # apply_window_icon CAGRILMADI
    dialog.show()
    qt_app.processEvents()

    assert dialog.windowIcon().isNull() is False
    assert QApplication.windowIcon().isNull() is False
    dialog.close()
    parent.close()


def test_no_dialog_module_hardcodes_its_own_icon_path():
    for relative in ("app/subtitle_center.py", "app/log_management_dialog.py",
                     "app/error_details_dialog.py",
                     "app/subtitle_appearance_dialog.py",
                     "app/media_info_dialog.py",
                     "app/subtitle_center_settings_dialog.py",
                     "app/menu_actions.py"):
        source = read(os.path.join(PROJECT, relative))
        assert "mlc-player-icon" not in source, (
            f"{relative}: ikon yolu kopyalanmis")
        assert "standardIcon" not in source, f"{relative}: varsayilan ikon"


def test_the_floating_overlay_never_gets_its_own_taskbar_entry():
    """Video ustundeki Tool yuzeyleri gorev cubugunda GORUNMEMELI."""
    source = read(os.path.join(PROJECT, "app", "video_frame.py"))

    assert "Qt.WindowType.Tool" in source
    assert "setWindowIcon" not in source


def test_apply_window_icon_is_safe_without_an_icon(qt_app, monkeypatch,
                                                   tmp_path):
    monkeypatch.setattr(app_icon.sys, "_MEIPASS", str(tmp_path), raising=False)
    app_icon.reset_icon_cache()
    try:
        widget = QWidget()
        app_icon.apply_window_icon(widget)   # ham hata ÇIKMAMALI
        widget.close()
    finally:
        app_icon.reset_icon_cache()


# =====================================================================
# 7. Ozel TitleBar
# =====================================================================

@pytest.fixture
def title_bar(qt_app):
    from PyQt6.QtWidgets import QVBoxLayout

    from app.title_bar import TitleBar

    window = QMainWindow()
    for name in ("open_file", "show_playlist"):
        setattr(window, name, lambda: None)
    for label in ("Ortam", "Görünüm"):
        window.menuBar().addMenu(label)
    window.menuBar().hide()
    # Urundeki gibi layout'a EKLENIR; aksi halde pencere yeniden
    # boyutlandiginda cubuk genislemez ve olcum anlamsiz olur.
    central = QWidget(window)
    window.setCentralWidget(central)
    layout = QVBoxLayout(central)
    layout.setContentsMargins(0, 0, 0, 0)
    bar = TitleBar(window)
    layout.addWidget(bar)
    layout.addWidget(QWidget(window), 1)
    window.resize(1280, 720)
    window.show()
    qt_app.processEvents()
    yield bar
    window.close()
    qt_app.processEvents()


def test_the_custom_title_bar_shows_exactly_one_logo(title_bar):
    logos = [child for child in title_bar.findChildren(QLabel)
             if child.objectName() == "titleLogo"]

    assert len(logos) == 1
    logo = logos[0]
    assert logo.accessibleName() == "MLC Player simgesi"
    assert logo.pixmap() is not None and not logo.pixmap().isNull()
    assert logo.width() == logo.height(), "logo kare değil"
    assert logo.width() > 0


def test_the_logo_is_large_enough_to_read(title_bar):
    """Kullanıcı isteği (17 Ağustos 2026): logo BÜYÜTÜLSÜN.

    Eski sözleşme `logo.width() <= 24` diyordu. Bu ÖLÇÜLMÜŞ bir tavan
    değildi; logo 20 px'ken konmuş keyfi bir sınırdı ve kullanıcının
    "biraz daha büyütelim" isteğini engelliyordu. Gevşetilmedi, GERÇEK
    kısıta dönüştürüldü: taşma sınırı aşağıdaki testte çubuğun ve en
    yüksek kontrolün ölçüsünden TÜRETİLİR.
    """
    from app.title_bar import TITLE_LOGO_SIZE

    logo = title_bar.findChild(QLabel, "titleLogo")

    assert TITLE_LOGO_SIZE >= 26, "logo buyutulmedi"
    assert logo.width() == TITLE_LOGO_SIZE


def test_the_logo_does_not_overflow_the_title_bar(title_bar):
    """TAŞMA SINIRI: sabit sayı değil, çubuğun kendi ölçüsünden türer.

    İki kısıt birlikte tutulur:
    1. Logo çubuğun içinde kalır ve altına/üstüne nefes payı bırakır.
    2. Logo, çubuktaki EN YÜKSEK kontrolden (düğmeler) daha uzun olmaz;
       aksi hâlde çubuk logonun etrafında büyümeye zorlanır.
    """
    from app.title_bar import TITLE_BAR_HEIGHT

    logo = title_bar.findChild(QLabel, "titleLogo")
    buttons = [child for child in title_bar.findChildren(QPushButton)
               if child.isVisible()]
    tallest = max((button.height() for button in buttons), default=0)

    assert logo.height() <= tallest, (
        f"logo {logo.height()} px, en yuksek dugme {tallest} px")
    assert logo.height() + 2 * MIN_LOGO_BREATHING <= TITLE_BAR_HEIGHT, (
        f"logo {logo.height()} px, cubuk {TITLE_BAR_HEIGHT} px: nefes payi yok")
    # Gerçek yerleşimde de içeride mi?
    assert logo.geometry().top() >= 0
    assert logo.geometry().bottom() <= title_bar.height()


def test_the_logo_sits_left_of_the_title_text(title_bar):
    logo = title_bar.findChild(QLabel, "titleLogo")

    assert logo.x() < title_bar.title_label.x()


def test_the_logo_never_blocks_dragging_or_the_buttons(title_bar):
    logo = title_bar.findChild(QLabel, "titleLogo")

    assert logo.testAttribute(
        Qt.WidgetAttribute.WA_TransparentForMouseEvents) is True
    assert title_bar._child_at(logo.geometry().center()) is None


def test_the_title_bar_height_did_not_grow(title_bar):
    from app.title_bar import TITLE_BAR_HEIGHT

    assert TITLE_BAR_HEIGHT == 48
    assert title_bar.height() == TITLE_BAR_HEIGHT


def test_the_window_buttons_are_not_clipped_in_a_narrow_window(title_bar,
                                                               qt_app):
    title_bar.window().resize(520, 400)
    qt_app.processEvents()

    for name in ("minimize_button", "maximize_button", "close_button"):
        button = getattr(title_bar, name)
        assert button.width() == 34, f"{name} kırpıldı"
        assert button.x() + button.width() <= title_bar.width()


# =====================================================================
# 8. PyInstaller spec hazirligi
# =====================================================================

def test_the_spec_carries_the_exe_icon():
    spec = read(SPEC)

    # EXE ikonu ŞEFFAF sürümdür; Windows kısayolunda görünen budur.
    assert "icon='assets/mlc-player-icon-transparent.ico'" in spec or \
        'icon="assets/mlc-player-icon-transparent.ico"' in spec


def test_the_spec_ships_the_runtime_assets():
    spec = read(SPEC)

    assert "'assets'" in spec or '"assets"' in spec
    assert "assets/mlc-player-icon.ico" in spec


def test_the_existing_packaging_contract_is_untouched():
    spec = read(SPEC)

    # NOT: `yt-dlp.exe`, `deno.exe` ve onların lisans metinleri 17 Ağustos
    # 2026'da BİLEREK ana paketten çıkarıldı (birlikte 110,3 MB) ve ayrı
    # "İnternet Videosu" ek paketine taşındı; bkz.
    # tests/test_internet_video_addon_regressions.py. Buradaki sözleşme
    # ONEDIR + UPX kapalı + `_internal` + mpv çekirdeğidir.
    for needed in ("exclude_binaries=True", "COLLECT(", "upx=False",
                   "contents_directory='_internal'", "bin/mpv-2.dll"):
        assert needed in spec, f"paketleme sözleşmesi bozuldu: {needed}"
    assert "libmpv.dll.a" not in spec


def test_the_plan_records_the_setup_icon_decision():
    plan = read(os.path.join(PROJECT, "docs", "PACKAGING_PLAN.md"))

    assert "SetupIconFile" in plan
    assert "UninstallDisplayIcon" in plan
