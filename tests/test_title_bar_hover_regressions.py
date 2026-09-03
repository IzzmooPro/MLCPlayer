# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Başlık çubuğu düğmeleri fare üzerine gelince BELLİ ETMELİDİR.

KULLANICI RAPORU (17 Ağustos 2026, ekran fotoğrafıyla). Windows'un kendi
penceresinde kapatma düğmesinin üzerine TIKLAMADAN gelince düğme
renkleniyor ve ipucu çıkıyor; bizim başlık çubuğumuzda üstteki düğmelere
gelince bir şey olmuyor.

ÖLÇÜM SINIRI — DÜRÜST KAYIT. Qt'nin `:hover` durumu GERÇEK imleç
konumuna bağlıdır; offscreen platformda sentetik `QEnterEvent` göndermek
onu tetiklemez. Bu yüzden "hover çalışıyor mu" sorusu bu testlerle
ÖLÇÜLEMEZ ve öyleymiş gibi de yapılmaz. Burada kilitlenen şey STİL
SÖZLEŞMESİDİR: kuralın var olduğu, hangi rengi kullandığı ve ne kadar
görünür olduğu. Gerçek görünüm kullanıcı tarafından gerçek pencerede
onaylanır.

KULLANICI KARARI: kapatma düğmesi Windows kırmızısına (#E81123)
DÖNMEYECEK; ürünün kendi vurgu rengi kullanılacak. O renk overlay ve
altyazı pencerelerinde zaten `#F26A3D`tir.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

#: Ürünün vurgu rengi. `app/video_frame.py::OVERLAY_ACCENT` ve altyazı
#: pencereleriyle AYNI olmalıdır; başlık çubuğu ayrı bir kimlik kurmaz.
PRODUCT_ACCENT = "#F26A3D"

#: Windows'un kapatma kırmızısı. Bilerek KULLANILMAZ.
WINDOWS_CLOSE_RED = "#E81123"


@pytest.fixture(scope="module")
def title_bar_source():
    return (ROOT / "app" / "title_bar.py").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def rendered_stylesheet():
    """Qt'ye GERÇEKTEN verilen stil metni.

    Kaynak metni taramak yetmez: renk artık `TITLE_BAR_ACCENT` üzerinden
    f-string ile yerleştiriliyor, yani kaynakta düz altıgen kod yok.
    Ölçülmesi gereken şey widget'ın aldığı stildir.
    """
    from PyQt6.QtWidgets import QApplication, QMainWindow

    app = QApplication.instance() or QApplication([])

    class Player(QMainWindow):
        def __getattr__(self, name):
            if name.startswith("__"):
                raise AttributeError(name)
            return lambda *a, **k: None

    from app.title_bar import TitleBar

    window = Player()
    bar = TitleBar(window)
    sheet = bar.styleSheet()
    bar.deleteLater()
    window.deleteLater()
    return sheet


def hover_alpha(source, selector):
    """`selector:hover` kuralındaki `rgba(...)` alfasını döndürür."""
    pattern = re.compile(
        re.escape(selector) + r":hover\s*\{[^}]*rgba\([^)]*?,\s*(\d+)\s*\)")
    match = pattern.search(source)
    return int(match.group(1)) if match else None


# ── Renk kimliği ─────────────────────────────────────────────────────────

def test_the_close_button_does_not_use_the_windows_red(rendered_stylesheet):
    """Kullanıcı kararı: kırmızı değil, ürünün rengi.

    Ölçüm STİLDE yapılır; kaynaktaki gerekçe yorumunda rengin ADI geçebilir.
    """
    assert WINDOWS_CLOSE_RED.lower() not in rendered_stylesheet.lower()


def test_the_close_button_uses_the_product_accent(rendered_stylesheet):
    match = re.search(r"QPushButton#titleClose:hover\s*\{([^}]*)\}",
                      rendered_stylesheet)
    assert match, "kapatma düğmesinin hover kuralı yok"
    assert PRODUCT_ACCENT.lower() in match.group(1).lower()


def test_the_accent_matches_the_rest_of_the_product(title_bar_source):
    """Başlık çubuğu AYRI bir vurgu rengi icat etmez."""
    from app.title_bar import TITLE_BAR_ACCENT
    from app.video_frame import OVERLAY_ACCENT

    assert OVERLAY_ACCENT.lower() == PRODUCT_ACCENT.lower()
    assert TITLE_BAR_ACCENT.lower() == PRODUCT_ACCENT.lower()
    assert "TITLE_BAR_ACCENT = UI_ACCENT" in title_bar_source


# ── Görünürlük ───────────────────────────────────────────────────────────

def test_the_neutral_hover_is_visible_enough(rendered_stylesheet):
    """ÖLÇÜLEN SORUN: 26/255 (~%10) koyu çubukta fark edilmiyordu."""
    alpha = hover_alpha(rendered_stylesheet, "QPushButton")
    assert alpha is not None, "genel hover kuralı yok"
    assert alpha >= 45, f"hover katmanı hâlâ çok soluk: {alpha}/255"


def test_every_window_button_still_has_a_tooltip():
    """İpucu, rengin yanındaki ikinci ve erişilebilir işarettir."""
    source = (ROOT / "app" / "title_bar.py").read_text(encoding="utf-8")
    assert "setToolTip(label)" in source
    assert "setAccessibleName(label)" in source


# ── Mevcut davranış korunuyor ────────────────────────────────────────────

def test_the_more_button_dismissed_rule_survives(title_bar_source):
    """Menü kapandıktan sonra hover bastırma kuralı ÖLÇÜLMÜŞ bir düzeltmeydi
    (düğme seçiliymiş gibi gri kalıyordu); renk turu onu silmemeli."""
    assert "menuDismissed" in title_bar_source
    assert "menuOpen" in title_bar_source


def test_the_maximize_button_label_still_toggles(title_bar_source):
    """`Geri Yükle` / `Büyüt` değişimi hover turuyla bozulmamalı."""
    assert 'tr("Geri Yükle")' in title_bar_source
    assert 'tr("Büyüt")' in title_bar_source
