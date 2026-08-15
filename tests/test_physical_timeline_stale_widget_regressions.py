"""Fiziksel kabul harness'i: silinmis timeline referansi regresyonlari.

Kirmizi kanit (2026-08-14, `timeline` grubu tekrar 3):

    File native_physical_acceptance_child.py, line 1126, in group_timeline
      follow, follow_detail = seek_to_ratio(0.50, name)
    File native_physical_acceptance_child.py, line 978, in seek_to_ratio
      return None, (f"start_value={timeline.value()}...
    RuntimeError: wrapped C/C++ object of type ClickableSlider has been deleted

Kaynak incelemesi (URUN DEGISTIRILMEDEN):

- `VideoFrame._create_control_overlay()` basinda `if self.control_overlay is
  not None: return` korumasi vardir ve yalniz `__init__` icinden cagrilir;
  urun katmani ve `overlay_timeline` calisma sirasinda YENIDEN URETILMEZ.
- `close_control_overlay()` yalniz `hide()`/`close()` yapar; hicbir yerde
  `WA_DeleteOnClose` kurulmaz.
- Widget'lari silen TEK yol `release_overlay_surfaces()`tir ve o da yalniz
  urun KAPANIS yolundan (`app/player.py`) cagrilir.

Yani silinme urunun mesru kapanisidir; kusur, harness'in `group_timeline()`
basinda BIR KEZ baglayip butun fazlar boyunca kullandigi eski referanstir.
Silinmis nesneye erisim ham `RuntimeError` ve `exit=90` uretiyor; bunun
yerine guncel referans alinmali, referans yoksa olcum BLOCKED sayilmalidir.

Testler urun penceresi ACMAZ: gercek bir Qt widget'i offscreen olusturulup
`sip.delete()` ile silinir, boylece "silinmis C++ nesnesi" durumu
deterministik uretilir.
"""
import importlib.util
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from PyQt6 import sip
from PyQt6.QtWidgets import QApplication, QSlider, QWidget

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHILD = os.path.join(ROOT, "tests", "native_physical_acceptance_child.py")

pytestmark = pytest.mark.skipif(os.name != "nt",
                                reason="fiziksel kabul harness'i yalniz Windows")


def read_child_source():
    with open(CHILD, encoding="utf-8", errors="replace") as handle:
        return handle.read()


@pytest.fixture(scope="module")
def child():
    previous = os.environ.get("MLC_NATIVE_SMOKE")
    os.environ["MLC_NATIVE_SMOKE"] = "1"
    path_before = os.environ.get("PATH", "")
    sys_path_before = list(sys.path)
    try:
        spec = importlib.util.spec_from_file_location(
            "mlc_physical_child_stale_widget", CHILD)
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


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


class FakeFrame:
    """Urun `VideoFrame`'inin yalniz referans tutma yuzeyi."""

    def __init__(self, timeline):
        self.overlay_timeline = timeline


# =====================================================================
# 1. Silinmis Qt nesnesi ham RuntimeError uretmemeli
# =====================================================================

def test_a_deleted_widget_is_reported_as_gone(child, qt_app):
    """Silinmis C++ nesnesi `RuntimeError` FIRLATMADAN "yok" sayilmali."""
    slider = QSlider()
    sip.delete(slider)

    assert child.widget_alive(slider) is False


def test_a_live_widget_is_reported_as_alive(child, qt_app):
    """Yasayan widget icin davranis degismemeli."""
    slider = QSlider()

    assert child.widget_alive(slider) is True


def test_a_missing_widget_is_reported_as_gone(child, qt_app):
    """Referans hic yoksa (None) da cokme olmamali."""
    assert child.widget_alive(None) is False


# =====================================================================
# 2. Her erisimde GUNCEL referans
# =====================================================================

def test_the_current_reference_is_read_from_the_frame(child, qt_app):
    """Yardimci, kareden o anki widget'i okur."""
    slider = QSlider()
    frame = FakeFrame(slider)

    assert child.live_overlay_widget(frame, "overlay_timeline") is slider


def test_a_deleted_child_reference_yields_none(child, qt_app):
    """Silinmis widget None doner; cagiran taraf BLOCKED verebilsin."""
    slider = QSlider()
    frame = FakeFrame(slider)
    sip.delete(slider)

    assert child.live_overlay_widget(frame, "overlay_timeline") is None


def test_a_replaced_child_reference_is_not_stale(child, qt_app):
    """Urun referansi degisirse ESKI nesne DONMEMELI."""
    old = QSlider()
    frame = FakeFrame(old)
    new = QSlider()
    frame.overlay_timeline = new

    assert child.live_overlay_widget(frame, "overlay_timeline") is new


def test_a_frame_without_the_attribute_yields_none(child, qt_app):
    """Kapanista referans `None`'a cekilir; bu da cokme uretmemeli."""
    frame = QWidget()

    assert child.live_overlay_widget(frame, "overlay_timeline") is None


# =====================================================================
# 3. `group_timeline()` sozlesmesi
# =====================================================================

def test_group_timeline_does_not_bind_the_timeline_only_once():
    """Referans grup basinda BIR KEZ baglanip fazlar boyunca kullanilmamali."""
    source = read_child_source()
    block = source[source.index("def group_timeline("):
                   source.index("def group_separator(")]

    assert "frame.overlay_timeline" not in block
    assert block.count("live_overlay_widget(frame, \"overlay_timeline\")") >= 2


def test_group_timeline_blocks_when_the_widget_is_gone():
    """Widget yoksa olcum BLOCKED olmali; ham istisna ile dusulmemeli."""
    source = read_child_source()
    block = source[source.index("def group_timeline("):
                   source.index("def group_separator(")]

    assert "BLOCKED: WIDGET_GONE" in block


def test_the_product_overlay_is_still_created_once_and_guarded():
    """Duzeltme harness tarafindadir; urun katmani sozlesmesi korunur."""
    with open(os.path.join(ROOT, "app", "video_frame.py"),
              encoding="utf-8", errors="replace") as handle:
        product = handle.read()
    block = product[product.index("def _create_control_overlay("):]

    assert "if self.control_overlay is not None:" in block[:200]
    assert product.count("self._create_control_overlay()") == 1
    assert "WA_DeleteOnClose" not in product
