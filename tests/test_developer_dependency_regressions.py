# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Depoyu klonlayan biri testleri ve yayın zincirini KOŞABİLMELİDİR.

KIRMIZI KANIT (17 Ağustos 2026, ölçüldü). `requirements.txt` yalnız
`PyQt6`, `python-mpv` ve `cryptography` beyan ediyor. Ama depo şunları
ADIYLA çağırıyor:

    pyside6-lrelease  ->  packaging/compile_translations.py
                          packaging/build_release.bat (ADIM 3/8)
                          5 test dosyası
    pytest            ->  bütün test paketi

`pyside6-lrelease` **PySide6** ile gelir. Ölçüldü: PyQt6 `pylupdate6`
sağlıyor ama `lrelease` SAĞLAMIYOR — yani bağımlılık gerçek, tesadüf
değil. Temiz bir kopyada `pip install -r requirements.txt` yapan biri
testleri koşamaz ve `build_release.bat` 3. adımda durur.

NEDEN `requirements.txt`E EKLENMEZ: o dosyayı `scripts/bootstrap.ps1`
SON KULLANICI için kuruyor. Programı kaynaktan çalıştırmak isteyen birine
ikinci bir Qt bağlaması indirtmek doğru değil. Geliştirici araçları ayrı
dosyada durur.

PAKETE DE GİRMEMELİDİR: ürün PyQt6 ile çalışır; PySide6 yalnız derleme
aracıdır ve `MLCPlayer.spec` `excludes` listesinde olmalıdır.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / "requirements.txt"
DEV = ROOT / "requirements-dev.txt"


def read(path):
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def declared(path):
    """Yorum ve boş satırlar dışındaki paket adları (küçük harf)."""
    names = set()
    for line in read(path).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        names.add(re.split(r"[<>=!\[]", line)[0].strip().lower())
    return names


# ── Geliştirici bağımlılıkları ───────────────────────────────────────────

def test_a_developer_requirements_file_exists():
    assert DEV.is_file(), (
        "testleri ve yayın zincirini koşmak için gereken araçlar beyan "
        "edilmemiş")


def test_the_translation_compiler_is_declared():
    """`pyside6-lrelease` PySide6 ile gelir; PyQt6 onu SAĞLAMAZ (ölçüldü)."""
    assert "pyside6" in declared(DEV)


def test_pytest_is_declared():
    assert "pytest" in declared(DEV)


def test_the_runtime_file_stays_lean():
    """Son kullanıcıya ikinci bir Qt bağlaması indirtilmez."""
    runtime = declared(RUNTIME)
    assert "pyqt6" in runtime
    assert "pyside6" not in runtime, (
        "PySide6 yalnız geliştirici aracıdır; bootstrap bu dosyayı son "
        "kullanıcı için kuruyor")
    assert "pytest" not in runtime


# ── Pakete sızmamalı ─────────────────────────────────────────────────────

def test_pyside6_is_excluded_from_the_package():
    """Ürün PyQt6 ile çalışır; PySide6 derleme aracıdır."""
    spec = (ROOT / "MLCPlayer.spec").read_text(encoding="utf-8")
    excludes = spec.split("excludes=", 1)[1].split("]", 1)[0]
    assert "PySide6" in excludes


# ── Çağrılan her araç beyan edilmiş olmalı ───────────────────────────────

def test_every_externally_invoked_tool_is_declared():
    """Adıyla çağırdığımız bir araç hiçbir yerde yazmıyorsa katkıcı çakılır."""
    all_declared = declared(RUNTIME) | declared(DEV)
    # Araç adı -> onu sağlayan paket.
    tools = {"pyside6-lrelease": "pyside6",
             "pyside6-linguist": "pyside6",
             "pytest": "pytest"}
    for tool, package in tools.items():
        assert package in all_declared, f"{tool} için {package} beyan edilmemiş"


# ── Çevirmen yolu belgeli olmalı ─────────────────────────────────────────

def test_the_readme_documents_the_translation_workflow():
    """`.ts` dosyaları hazır ama nasıl çevrileceği yazılı değildi."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    section = readme.split("## Contributing", 1)[1].split("\n## ", 1)[0]
    assert "requirements-dev.txt" in section
    assert "linguist" in section.lower()
    assert "translations/" in section


def test_the_readme_warns_against_the_wrong_extractor():
    """TUZAK: `pyside6-lupdate` bizim `tr()` sarmalayıcımızı GÖREMEZ ve
    `.ts` dosyalarını eksik yeniden yazar. Çıkarma bize aittir."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    section = readme.split("## Contributing", 1)[1].split("\n## ", 1)[0]
    assert "lupdate" in section, "yanlış araç uyarısı yok"
    assert "extract_translations.py" in section
