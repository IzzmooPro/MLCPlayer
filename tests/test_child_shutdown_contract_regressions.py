# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""libmpv yukleyen VARSAYILAN child'lar normal finalizasyona GIRMEMELI.

OLCULEN KIRMIZI KANIT (2026-08-15)
----------------------------------
`pytest -q tests` turlarinda araliklarla:

    subprocess.TimeoutExpired: '...main_entry_child.py' timed out after 180 s
    -> 1 error, tur suresi 234 sn (bunun 180 sn'si bu bekleme)

Ayni takilma iki farkli dosyada goruldu
(`test_default_cinematic_ui_regressions`, `test_classic_ui_removal_regressions`)
ve her seferinde child'in KENDISI saglikliydi: dogrudan calistirildiginda
11/11 kosumda 0,3-0,5 sn'de `exit=0`, pytest altinda 3/3 kosumda 1,4 sn.

KOK NEDEN (urunun kendi belgesi)
--------------------------------
`main.py` satir 130:

    # NOT: mpv DLL'leri bu yapida interpreter kapanisinda TAKILIYOR
    # (thread-safe olmayan DLL yikimi). Normal Python finalizasyonu
    # yerine os._exit ile sureci temiz kapat.
    os._exit(ret)

Urun bu tehlikeyi biliyor ve `os._exit()` ile kaciniyor; kullanici o faza
hic girmiyor. Ama olcum child'larinin bir kismi libmpv yukleyip
`raise SystemExit(...)` ile NORMAL finalizasyona giriyordu. Olcum (JSON)
kapanistan ONCE basildigi icin veri her zaman uretilmis oluyor; takilma
tamamen kapanis fazinda. Yarisa bagli oldugu icin talep uzerine
uretilemiyor, bu yuzden sozlesme KAYNAK duzeyinde kilitlenir.

KAPSAM
------
Yalniz opt-in kapisi OLMAYAN, yani `pytest -q tests` sirasinda gercekten
libmpv yukleyen child'lar. Native/fiziksel matris child'lari
(`MLC_NATIVE_SMOKE` kapili) bu turda DEGISTIRILMEDI.

BILINCLI ISTISNA
----------------
`startup_audio_device_scan_child.py` finalizasyona BILEREK girer: amaci o
fazdaki `0xC0000005` cokmesini yakalamaktir ve cagiran test `returncode == 0`
arar. `os._exit` eklenirse test gozlemek istedigi seyi goremez.
"""
import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

TESTS = os.path.dirname(os.path.abspath(__file__))

# Finalizasyon tehlikesini OLCMEK icin oraya bilerek giren child.
DELIBERATE_FINALISERS = {"startup_audio_device_scan_child.py"}

LOADS_LIBMPV = re.compile(r"MPVPlayer\(|from app\.player import|^import mpv\b",
                          re.MULTILINE)
OPT_IN_GATE = re.compile(r"MLC_NATIVE_SMOKE|OPT_IN_REQUIRED")


def read(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


def every_print_flushes(source):
    """Dosyadaki her `print(` cagrisi `flush=True` tasiyor mu?

    Tasiyorsa cikti zaten satir satir bosaltiliyordur ve `os._exit()`
    hicbir seyi tamponda birakmaz.
    """
    for match in re.finditer(r"\bprint\(", source):
        tail = source[match.end():match.end() + 300]
        if "flush=True" not in tail.split(")\n")[0] + ")":
            if "flush=True" not in tail[:200]:
                return False
    return True


def default_suite_libmpv_children():
    """Varsayilan pakette libmpv yukleyen child dosyalari."""
    found = []
    for name in sorted(os.listdir(TESTS)):
        if not name.endswith("_child.py"):
            continue
        source = read(os.path.join(TESTS, name))
        if not LOADS_LIBMPV.search(source):
            continue
        if OPT_IN_GATE.search(source):
            continue
        found.append(name)
    return found


def test_the_scan_actually_finds_the_children_it_is_meant_to_guard():
    """Kapsam bos kalirsa test sessizce anlamsizlasir."""
    names = default_suite_libmpv_children()
    assert len(names) >= 6, names
    for expected in ("default_ui_child.py", "main_entry_child.py",
                     "smoke_child.py", "timeline_child.py"):
        assert expected in names, (expected, names)


@pytest.mark.parametrize("name", default_suite_libmpv_children())
def test_a_libmpv_child_never_relies_on_normal_interpreter_finalisation(name):
    if name in DELIBERATE_FINALISERS:
        pytest.skip("bu child finalizasyon tehlikesini BILEREK olcuyor")
    source = read(os.path.join(TESTS, name))
    assert "os._exit(" in source, (
        f"{name} libmpv yukluyor ama `os._exit()` ile kapanmiyor; "
        "normal finalizasyon thread-safe olmayan DLL yikiminda takilabilir "
        "(bkz. main.py satir 130).")


@pytest.mark.parametrize("name", default_suite_libmpv_children())
def test_a_libmpv_child_flushes_before_the_hard_exit(name):
    """`os._exit()` tampon BOSALTMAZ; olcum kaybolmamali."""
    if name in DELIBERATE_FINALISERS:
        pytest.skip("bu child finalizasyon tehlikesini BILEREK olcuyor")
    source = read(os.path.join(TESTS, name))
    # NOT: ilk gecis ARAMAZ. Gerekce dizeleri `main.py -> os._exit(ret)`
    # seklinde yorum icinde de gecebiliyor; olculmesi gereken GERCEK cagri
    # en sondakidir.
    exit_at = source.rindex("os._exit(")
    window = source[max(0, exit_at - 400):exit_at]
    # Yorumda gecen "flush" kelimesi yeterli DEGILDIR; gercek cagri aranir.
    explicit = "flush()" in window or "flush=True" in window
    # Ikinci gecerli bicim: cikti zaten satir satir flush ediliyorsa
    # (`print(..., flush=True)` veya flush eden ortak yardimci) tamponda
    # bekleyen bir sey kalmaz. Bu durumda ayrica flush sart degildir.
    assert explicit or every_print_flushes(source), (
        f"{name}: `os._exit()` oncesinde flush garantisi yok; os._exit "
        "tamponlari bosaltmaz ve olcum kaybolabilir.")


def test_the_deliberate_finaliser_is_still_deliberate():
    """Istisna sessizce genislemesin: tek dosya ve gerekcesi kaynakta."""
    assert DELIBERATE_FINALISERS == {"startup_audio_device_scan_child.py"}
    source = read(os.path.join(TESTS, "startup_audio_device_scan_child.py"))
    assert "os._exit(" not in source
    assert "Yorumlayici cikisinda" in source or "finaliz" in source.lower()


def test_the_product_still_documents_and_uses_the_hard_exit():
    """Sozlesmenin kaynagi urundur; urun degisirse bu test uyarir."""
    main_py = read(os.path.join(os.path.dirname(TESTS), "main.py"))
    assert "os._exit(ret)" in main_py
    assert "takılıyor" in main_py or "takiliyor" in main_py
