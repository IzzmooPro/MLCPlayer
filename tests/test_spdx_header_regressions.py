# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Her Python kaynağı SPDX telif ve lisans kimliği taşır.

KIRMIZI KANIT (17 Ağustos 2026). Depoda telif iddiası YALNIZ kök `LICENSE`
dosyasında ve README bölümündeydi. Tek bir dosya bağlamından koparılıp
kopyalandığında hangi lisansa tabi olduğu dosyanın kendisinden
ANLAŞILMIYORDU.

GPLv3'ün kendi "How to Apply These Terms" bölümü bildirimlerin her kaynak
dosyanın başına iliştirilmesini önerir. VLC de bunu yapar (depoda
görüldü): her dosyada amaç satırı, telif, yazar listesi ve tam GPL/LGPL
paragrafı vardır.

BİÇİM VLC'DEN AYRILIR, BİLEREK. VLC'nin 20 satırlık bloğunun iki işlevi
var ve ikisi de bizde YOK: (1) VLC iki lisanslıdır (`src/libvlc.c`
LGPLv2.1+, `open.cpp` GPLv2+) ve hangi dosyanın hangi lisansa tabi
olduğunu o başlıkla takip eder, (2) yüzlerce katkıcının yazar listesini
taşır. Bizde tek lisans ve tek telif sahibi var. Aynı bloğu 179 dosyaya
kopyalamak 3500 satır ölü metin olurdu.

Bu yüzden SPDX KISA BİÇİMİ kullanılır — aynı hukuki işlev, iki satır.
Linux çekirdeği de bu sebeple uzun bloklardan SPDX'e geçti; makine
tarafından okunabilir ve denetim araçları tanır.

KİMLİK `GPL-3.0-only` (kullanıcı kararı): README ve Hakkında penceresi
"GNU GPL sürüm 3 koşullarıyla" diyor, "veya sonrası" demiyor. Telif
sahibi tek kişi olduğu için sonradan `or-later`'a geçilebilir; ters yön
zordur.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

COPYRIGHT_LINE = "# SPDX-FileCopyrightText: {year} MLC Player contributors"
LICENCE_LINE = "# SPDX-License-Identifier: GPL-3.0-only"

#: Taranan ağaçlar. `build/`, `dist/` ve `bin/` bizim kaynağımız değildir.
SOURCE_TREES = ("app", "tests", "packaging")
SOURCE_FILES = ("main.py", "second_launch.py", "MLCPlayer.spec")


def python_sources():
    paths = [ROOT / name for name in SOURCE_FILES]
    for tree in SOURCE_TREES:
        paths.extend(sorted((ROOT / tree).rglob("*.py")))
    return [p for p in paths
            if p.is_file() and "__pycache__" not in p.parts]


def header_of(path):
    """Dosyanın ilk iki anlamlı satırı (kodlama satırı atlanır)."""
    lines = path.read_text(encoding="utf-8").splitlines()
    while lines and (lines[0].startswith("#!")
                     or "coding" in lines[0][:40]):
        lines = lines[1:]
    return lines[:2]


def test_there_is_something_to_check():
    """Tarama boş dönerse test hiçbir şey ölçmeden yeşil geçerdi."""
    assert len(python_sources()) > 100


@pytest.mark.parametrize("path", python_sources(),
                         ids=lambda p: str(p.relative_to(ROOT)))
def test_every_python_source_carries_the_spdx_header(path):
    from app.config import COPYRIGHT_YEAR

    head = header_of(path)
    expected = [COPYRIGHT_LINE.format(year=COPYRIGHT_YEAR), LICENCE_LINE]
    assert head == expected, f"{path.relative_to(ROOT)} -> {head}"


def test_the_identifier_matches_what_the_readme_declares():
    """Depo kendi içinde çelişmemeli: `only` ise README de öyle demeli."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "GNU GPL version 3" in readme
    # "or later" DEMİYORUZ; kimlik de `-only`.
    assert "GPL-3.0-only" in LICENCE_LINE
    assert "or later" not in readme.split("## Licence")[1]


def test_the_year_comes_from_the_single_source():
    """Telif yılı elle yazılmaz; `config.COPYRIGHT_YEAR` tek kaynaktır."""
    from app.config import COPYRIGHT_YEAR

    sample = ROOT / "app" / "config.py"
    assert COPYRIGHT_YEAR in "\n".join(header_of(sample))


def test_the_header_does_not_break_the_module_docstring():
    """SPDX satırları YORUMDUR; docstring hâlâ ilk ifade olmalıdır."""
    import ast

    for path in (ROOT / "app" / "i18n.py", ROOT / "app" / "errors.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        assert ast.get_docstring(tree), path.name


def test_no_source_carries_a_second_conflicting_identifier():
    """Kopyala-yapıştır ile ikinci bir kimlik girerse denetim yanılır.

    BU DOSYA hariç tutulur: kimliği hem kural olarak hem de arama deseni
    olarak metninde taşır, yani kendi kendini eşleştirir.
    """
    pattern = re.compile(r"SPDX-License-Identifier:\s*([\w.\-+]+)")
    for path in python_sources():
        if path.name == Path(__file__).name:
            continue
        found = set(pattern.findall(path.read_text(encoding="utf-8")))
        assert found <= {"GPL-3.0-only"}, f"{path.name}: {found}"

# ── Kimliğin dayandığı metin ─────────────────────────────────────────────

#: Resmî GPLv3 metninin SHA-256'sı. 17 Ağustos 2026'da
#: `https://www.gnu.org/licenses/gpl-3.0.txt` indirilip karşılaştırıldı:
#: 35149 bayt, BİREBİR aynı. GPLv3 dondurulmuş bir metindir; değişmez.
GPL3_SHA256 = ("3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986")


def test_the_licence_file_really_is_the_canonical_gpl3():
    """230 dosyadaki `GPL-3.0-only` iddiası BU metne dayanır.

    README "kanonik gnu.org metni, değiştirilmemiş" diyordu ama bunu hiçbir
    şey DOĞRULAMIYORDU. Dosya bir gün kırpılır ya da düzenlenirse
    kimliğimiz yalan olur; bu test onu yakalar.
    """
    import hashlib

    raw = (ROOT / "LICENSE").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == GPL3_SHA256, (
        "LICENSE artık resmî GPLv3 metni DEĞİL")
    assert len(raw) == 35149

# ── Python olmayan kaynaklar ─────────────────────────────────────────────

#: Yazdığımız çalıştırılabilir betikler. Yorum ÖN EKİ dosya türüne göre
#: değişir; yanlış ön ek betiği bozar (`.bat` `rem`, `.ps1` `#`, `.iss` `;`).
SCRIPT_SOURCES = {
    "Start.bat": "rem ",
    "packaging/build_release.bat": "rem ",
    "scripts/bootstrap.ps1": "# ",
    "packaging/MLCPlayer.iss": "; ",
    "packaging/MLCPlayer_InternetVideo.iss": "; ",
}


@pytest.mark.parametrize("name,prefix", sorted(SCRIPT_SOURCES.items()))
def test_every_script_source_carries_the_spdx_header(name, prefix):
    from app.config import COPYRIGHT_YEAR

    text = (ROOT / name).read_text(encoding="utf-8")
    assert f"{prefix}SPDX-FileCopyrightText: {COPYRIGHT_YEAR}" in text, name
    assert f"{prefix}SPDX-License-Identifier: GPL-3.0-only" in text, name


def test_the_batch_files_still_start_with_echo_off():
    """`@echo off` İLK SATIR kalmalı; öncesine yorum konursa komut ekrana
    basılır ve kullanıcı her açılışta çöp satır görür."""
    for name in ("Start.bat", "packaging/build_release.bat"):
        first = (ROOT / name).read_text(encoding="utf-8").splitlines()[0]
        assert first.lower().startswith("@echo off"), name
