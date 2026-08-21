# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Kurulum sihirbazı markalıdır ve depoyu gösterir.

ÖLÇÜLEN EKSİK (kullanıcı bildirimi): kurulum sihirbazının sol tarafı boş
gri duruyordu ve programın bir adresi yoktu. Referans olarak bakılan VLC
kurulumunda hem markalı şerit hem de "web sitesine git" seçeneği var.

Görseller `packaging/make_wizard_images.py` ile ürünün kendi ikonundan
üretilir; bu testler üretimin ve `.iss` bağının kopmasını engeller.
"""

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ISS = ROOT / "packaging" / "MLCPlayer.iss"
WIZARD_DIR = ROOT / "packaging" / "wizard"
REPO_URL = "https://github.com/IzzmooPro/MLCPlayer"


def _iss():
    return ISS.read_text(encoding="utf-8-sig")


def _generator():
    path = ROOT / "packaging" / "make_wizard_images.py"
    spec = importlib.util.spec_from_file_location("mlc_wizard_images", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_wizard_images_referenced_by_the_installer_exist():
    """`.iss` var olmayan bir görsel gösterirse derleme sessizce bozulur."""
    text = _iss()
    for key in ("WizardImageFile", "WizardSmallImageFile"):
        match = re.search(rf"^{key}=(.+)$", text, re.MULTILINE)
        assert match, f"{key} tanımlı değil"
        for relative in match.group(1).split(","):
            path = ISS.parent / relative.strip().replace("\\", "/")
            assert path.is_file(), f"eksik görsel: {path}"


def test_wizard_images_are_24_bit_bmp():
    """Inno PNG kabul etmez; yanlış biçim derlemede hata verir."""
    for path in WIZARD_DIR.glob("*.bmp"):
        header = path.read_bytes()[:2]
        assert header == b"BM", f"{path.name} BMP değil"


def test_wizard_images_use_the_product_identity():
    """Görseller ikondan ÖLÇÜLEN marka renklerini taşır."""
    generator = _generator()
    image = generator.large_image(164, 314)
    assert image.getpixel((2, 2)) == generator.BACKGROUND
    # Alt şerit vurgu rengidir.
    assert image.getpixel((2, 313)) == generator.ACCENT


def test_inner_pages_have_no_second_logo():
    """KULLANICI KARARI: sağ üstteki küçük logo KALDIRILDI.

    Inno'da küçük görseli kapatan anahtar yoktur; verilmezse Inno KENDİ
    varsayılan görselini koyar. Bu yüzden başlık zeminiyle aynı renkte düz
    bir görsel verilir — dosya var olmalı ama üzerinde logo OLMAMALIDIR.
    """
    generator = _generator()
    image = generator.small_image(55, 55)
    colours = image.getcolors(maxcolors=16)
    assert colours == [(55 * 55, generator.HEADER_BACKGROUND)], (
        f"küçük görsel düz değil: {colours}")


def test_windows_gets_the_friendly_name_explicitly():
    """ÖLÇÜLEN KUSUR: sürüm kaynağı doğruyken bile liste ".exe" gösterdi.

    Kurulu exe'nin `FileDescription` alanı 'MLC Player' idi, buna rağmen
    Explorer "Birlikte aç" listesinde dosya adını gösterdi (önbellek +
    çıkarım). Ad artık AÇIKÇA kaydedilir.
    """
    text = _iss()
    assert "[Registry]" in text, "kayıt bölümü yok"
    assert re.search(
        r'ValueName: "FriendlyAppName"; ValueData: "\{#MyAppName\}"', text), (
        "FriendlyAppName açıkça yazılmıyor")


def test_registry_entries_are_removed_on_uninstall():
    """Kaldırma kabulünün ölçütü: geride kayıt KALMAZ."""
    for line in _iss().splitlines():
        if line.startswith("Root: HK") and "FriendlyAppName" in line:
            assert "uninsdeletekey" in line, line


def test_legacy_per_user_open_with_tree_is_removed_but_never_created():
    """Eski HKCU kaydı yalnız varsa temizlenir; kurulum onu üretmez."""
    expected = (
        'Root: HKCU; Subkey: "Software\\Classes\\Applications\\'
        '{#MyAppExeName}"; Flags: dontcreatekey uninsdeletekey'
    )
    lines = [line.strip() for line in _iss().splitlines()
             if line.strip() and not line.lstrip().startswith(";")]

    assert expected in lines, (
        "ürüne ait eski HKCU Birlikte Aç ağacı fail-closed temizlenmiyor")
    assert not any(
        line.startswith('Root: HKCU; Subkey: "Software\\Classes\\Applications"')
        for line in lines
    ), "Applications üst ağacı gibi paylaşılan bir kayıt hedeflenemez"


def test_installer_points_at_the_repository():
    text = _iss()
    for key in ("AppPublisherURL", "AppSupportURL", "AppUpdatesURL"):
        match = re.search(rf"^{key}=(.+)$", text, re.MULTILINE)
        assert match, f"{key} yok"
    assert f'#define MyAppUrl "{REPO_URL}"' in text
    assert "mailto:" not in text, "e-posta adresi kurulumda görünmemeli"


def test_the_branded_panel_page_is_enabled():
    """Boydan boya sol panel YALNIZ hoş geldiniz/son sayfada çizilir.

    Inno 6 modern stilde hoş geldiniz sayfası VARSAYILAN KAPALIDIR; kapalıyken
    büyük görsel hiç görünmüyordu (ölçüldü: kullanıcı yalnız sağ üstteki
    küçük logoyu gördü).
    """
    assert re.search(r"^DisableWelcomePage=no\s*$", _iss(), re.MULTILINE)


def test_no_license_acceptance_page():
    """GPL bir EULA DEĞİLDİR; onay sayfası gereksiz sürtünmedir.

    GPLv3 madde 9: programı almak veya çalıştırmak için lisansı kabul etmek
    gerekmez. Yükümlülük metnin kullanıcıya ULAŞMASIDIR — o da [Files]
    bölümünde LICENSE kopyalanarak karşılanır.
    """
    text = _iss()
    assert not re.search(r"^LicenseFile=", text, re.MULTILINE), (
        "lisans onay sayfası geri gelmiş")
    assert re.search(r'Source: "\.\.\\LICENSE"', text), (
        "LICENSE artık kuruluma girmiyor; GPLv3 yükümlülüğü kalkar")


def test_finish_page_offers_the_repository_without_forcing_it():
    """Tarayıcı KENDİLİĞİNDEN açılmaz; seçenek işaretsiz gelir."""
    # Adres `.iss` içinde TEK kaynaktan (`{#MyAppUrl}`) gelir; düz URL
    # aranmaz, aksi hâlde test tek kaynak kuralını cezalandırırdı.
    run_lines = [line for line in _iss().splitlines()
                 if line.startswith("Filename:") and "{#MyAppUrl}" in line]
    assert run_lines, "GitHub seçeneği yok"
    assert "unchecked" in run_lines[0], "seçenek varsayılan işaretli olmamalı"
    assert "shellexec" in run_lines[0]
