# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Fiziksel kabul harness'i: NULL foreground (HWND=0) regresyonlari.

Kirmizi kanit (2026-08-14 tam matris): 11 grubun 6'si `exit=90` ile dustu.
Butun olcumler ve `product_shutdown_path` PASS'ti; cokme child'in teardown
`finally` blogundaydi:

    File native_physical_acceptance_child.py, line 295, in take_foreground
      fg = int(user32.GetForegroundWindow())
    TypeError: int() argument must be ... not 'NoneType'

Kok neden: URUN `app/video_frame.py` icinde `GetForegroundWindow` imzasini
pointer-safe tanimlar (`restype = wintypes.HWND`). `ctypes.windll.user32`
surec genelinde TEK nesnedir; child urunu import ettigi icin ayni imzayi
paylasir. `wintypes.HWND` NULL donusu Python'da `None`'dur. Urun penceresi
kapandiktan hemen sonra Windows'ta kisa sure foreground pencere OLMAYABILIR;
o anda `int(None)` patlar. Bu bir URUN kusuru DEGILDIR ve urun tarafindaki
restype tanimi DEGISTIRILMEZ; harness NULL'u 0'a normalize etmelidir.

Testler gercek Win32 cagrisi YAPMAZ: child modulunun `user32` baglantisi
sahte bir nesneyle degistirilir, boylece NULL foreground durumu makineden
bagimsiz ve tekrarlanabilir bicimde uretilir.
"""
import importlib.util
import os
import re
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHILD = os.path.join(ROOT, "tests", "native_physical_acceptance_child.py")

pytestmark = pytest.mark.skipif(os.name != "nt",
                                reason="fiziksel kabul harness'i yalniz Windows")


def read_child_source():
    with open(CHILD, encoding="utf-8", errors="replace") as handle:
        return handle.read()


@pytest.fixture(scope="module")
def child():
    """Child modulunu ICE AKTAR (opt-in kapisi yalniz bu import icin acilir)."""
    previous = os.environ.get("MLC_NATIVE_SMOKE")
    os.environ["MLC_NATIVE_SMOKE"] = "1"
    path_before = os.environ.get("PATH", "")
    sys_path_before = list(sys.path)
    try:
        spec = importlib.util.spec_from_file_location(
            "mlc_physical_child_under_test", CHILD)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        if previous is None:
            os.environ.pop("MLC_NATIVE_SMOKE", None)
        else:
            os.environ["MLC_NATIVE_SMOKE"] = previous
    yield module
    os.environ["PATH"] = path_before
    sys.path[:] = sys_path_before


class FakeUser32:
    """`user32` yerine gecen sayac: NULL foreground'i deterministik uretir."""

    def __init__(self, foreground_values):
        self.foreground_values = list(foreground_values)
        self.calls = []

    def GetForegroundWindow(self):
        self.calls.append("GetForegroundWindow")
        if len(self.foreground_values) > 1:
            return self.foreground_values.pop(0)
        return self.foreground_values[0]

    def __getattr__(self, name):
        def recorded(*args, **kwargs):
            self.calls.append(name)
            return None
        return recorded


class FakeApp:
    def processEvents(self):
        return None


@pytest.fixture
def null_foreground(child, monkeypatch):
    """Foreground penceresi YOK: her okuma `None` doner."""
    fake = FakeUser32([None])
    monkeypatch.setattr(child, "user32", fake)
    monkeypatch.setattr(child, "APP", FakeApp(), raising=False)
    return fake


# =====================================================================
# 1. Cokmeme sozlesmesi
# =====================================================================

def test_foreground_info_survives_a_null_foreground_window(child, null_foreground):
    """Foreground pencere yokken tani okumasi COKMEMELI."""
    hwnd, pid = child.foreground_info()

    assert hwnd == 0
    assert pid == 0


def test_foreground_info_does_not_query_a_null_window(child, null_foreground):
    """HWND=0 icin `GetWindowThreadProcessId` cagrisi ANLAMSIZDIR."""
    child.foreground_info()

    assert "GetWindowThreadProcessId" not in null_foreground.calls


def test_take_foreground_survives_a_null_foreground_window(child, null_foreground):
    """Teardown geri yukleme foreground yokken COKMEMELI, False donmeli."""
    assert child.take_foreground(4321, attempts=1) is False


def test_take_foreground_is_a_safe_no_op_for_a_null_target(child, null_foreground):
    """Hedef HWND=0 ise hicbir pencere API'si cagrilmamali."""
    assert child.take_foreground(0, attempts=3) is False

    for unsafe in ("ShowWindow", "BringWindowToTop", "SetForegroundWindow",
                   "SetFocus", "AttachThreadInput", "GetWindowThreadProcessId"):
        assert unsafe not in null_foreground.calls, null_foreground.calls


def test_take_foreground_does_not_attach_to_a_null_foreground_thread(
        child, null_foreground):
    """Foreground yokken thread attach denenmemeli; pencere yine one alinmali."""
    child.take_foreground(4321, attempts=1)

    assert "AttachThreadInput" not in null_foreground.calls
    assert "GetWindowThreadProcessId" not in null_foreground.calls
    assert "SetForegroundWindow" in null_foreground.calls


def test_take_foreground_still_succeeds_when_the_window_comes_forward(
        child, monkeypatch):
    """Normal yol degismedi: hedef one gelince True doner."""
    fake = FakeUser32([None, 4321])
    monkeypatch.setattr(child, "user32", fake)
    monkeypatch.setattr(child, "APP", FakeApp(), raising=False)

    assert child.take_foreground(4321, attempts=2) is True


# =====================================================================
# 2. Tek normalize noktasi
# =====================================================================

def test_a_single_helper_normalises_the_foreground_handle(child, monkeypatch):
    """`foreground_hwnd()` NULL'u 0 yapar, gercek handle'i aynen gecirir."""
    fake = FakeUser32([None])
    monkeypatch.setattr(child, "user32", fake)
    assert child.foreground_hwnd() == 0

    fake = FakeUser32([98765])
    monkeypatch.setattr(child, "user32", fake)
    assert child.foreground_hwnd() == 98765


def test_no_unguarded_foreground_read_is_left_in_the_child():
    """Dosyada ciplak `int(user32.GetForegroundWindow())` KALMAMALI."""
    source = read_child_source()

    assert "int(user32.GetForegroundWindow())" not in source


def test_the_initial_foreground_record_is_normalised():
    """Baslangic foreground kaydi da ayni yardimciyi kullanmali."""
    source = read_child_source()

    assert "original_foreground = foreground_hwnd()" in source


# =====================================================================
# 3. Bozulmamasi gereken teardown sozlesmesi
# =====================================================================

def test_the_teardown_still_restores_and_marks_the_run():
    """`CHILD_RESTORED` geri yuklemeden SONRA, `MARK_DONE` tek kez yazilir."""
    source = read_child_source()
    restore = source.index("take_foreground(original_foreground, attempts=4)")
    restored = source.index('print(f"CHILD_RESTORED')

    assert restore < restored
    assert source.count("MARK_DONE group={GROUP}") == 1
    assert source.index('print(f"GROUP_SUMMARY') < source.index(
        'print(f"MARK_DONE group={GROUP}"')


# =====================================================================
# 4. Ayni sinif risk: URUNU import eden diger harness child'lari
# =====================================================================

# Bu dosyalar `app.player` (dolayisiyla `app.video_frame`) import ettigi icin
# `GetForegroundWindow.restype = wintypes.HWND` imzasini PAYLASIR ve ayni
# NULL -> None riskini tasir.
PRODUCT_IMPORTING_HARNESS = (
    "native_physical_acceptance_child.py",
    "subtitle_visual_acceptance_child.py",
    "native_composition_smoke_child.py",
    "native_overlay_smoke_child.py",
)

UNGUARDED = re.compile(
    r"int\(\s*(?:ctypes\.windll\.)?user32\.GetForegroundWindow\(\)\s*\)")


@pytest.mark.parametrize("name", PRODUCT_IMPORTING_HARNESS)
def test_product_importing_harness_files_normalise_the_handle(name):
    """Urun imzasini paylasan hicbir harness dosyasi ciplak okuma yapmamali."""
    path = os.path.join(ROOT, "tests", name)
    with open(path, encoding="utf-8", errors="replace") as handle:
        source = handle.read()

    assert UNGUARDED.search(source) is None, name


@pytest.mark.parametrize("name", PRODUCT_IMPORTING_HARNESS)
def test_product_importing_harness_files_really_import_the_product(name):
    """Envanterin gerekcesi olculur: bu dosyalar gercekten urunu import eder."""
    path = os.path.join(ROOT, "tests", name)
    with open(path, encoding="utf-8", errors="replace") as handle:
        source = handle.read()

    assert "from app.player import MPVPlayer" in source, name


def test_the_runner_does_not_share_the_product_signature():
    """Runner urunu import ETMEDIGI icin risk disidir; bu sinir korunmali."""
    with open(os.path.join(ROOT, "tests", "run_physical_acceptance.py"),
              encoding="utf-8", errors="replace") as handle:
        source = handle.read()

    assert "from app." not in source
    assert "import app" not in source


def test_the_product_signature_is_not_weakened():
    """Duzeltme harness tarafindadir; urun pointer-safe imzayi KORUR."""
    with open(os.path.join(ROOT, "app", "video_frame.py"),
              encoding="utf-8", errors="replace") as handle:
        product = handle.read()

    assert "_REAL_USER32.GetForegroundWindow.restype = wintypes.HWND" in product
