"""Fiziksel slider hedef secimi regresyonlari.

Kanitlanan sahte FAIL: ses araligi 0-175, mevcut deger 44 iken harness
sabit `%25` noktasina tikliyordu; `%25 * 175 ~= 44` oldugu icin sonuc
`44->44` cikiyor ve "deger degismedi" diye FAIL yaziliyordu. Urun hatasi
DEGILDI.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest

from physical_targets import (HIGH_RATIO, LOW_RATIO, candidate_values,
                              pick_far_target, target_x_for_value,
                              value_tolerance_for_width)

VOLUME_MIN, VOLUME_MAX = 0, 175


# =====================================================================
# 1. Sabit %25 hatasi
# =====================================================================

def test_fixed_quarter_target_would_collide_with_current_value():
    """Eski davranisin acigi: %25 hedefi mevcut 44 ile ayni degere duser."""
    quarter = int(round(VOLUME_MAX * 0.25))

    assert abs(quarter - 44) <= 1, quarter


def test_target_is_never_the_current_value():
    for current in range(VOLUME_MIN, VOLUME_MAX + 1, 5):
        target = pick_far_target(VOLUME_MIN, VOLUME_MAX, current)
        assert target != current, current


def test_current_44_does_not_produce_44():
    assert pick_far_target(VOLUME_MIN, VOLUME_MAX, 44) != 44


# =====================================================================
# 2. Uzak aday secimi
# =====================================================================

def test_low_current_picks_the_high_candidate():
    target = pick_far_target(VOLUME_MIN, VOLUME_MAX, 44)

    assert target == int(round(VOLUME_MAX * HIGH_RATIO))
    assert target == 140


def test_high_current_picks_the_low_candidate():
    target = pick_far_target(VOLUME_MIN, VOLUME_MAX, 140)

    assert target == int(round(VOLUME_MAX * LOW_RATIO))
    assert target == 35


def test_tie_is_deterministic_and_picks_the_high_candidate():
    low, high = candidate_values(VOLUME_MIN, VOLUME_MAX)
    middle = (low + high) // 2

    assert pick_far_target(VOLUME_MIN, VOLUME_MAX, middle) == high


@pytest.mark.parametrize("current", [VOLUME_MIN, 1, 87, 174, VOLUME_MAX])
def test_target_stays_inside_the_range(current):
    target = pick_far_target(VOLUME_MIN, VOLUME_MAX, current)

    assert VOLUME_MIN <= target <= VOLUME_MAX


@pytest.mark.parametrize("current", [VOLUME_MIN, 20, 44, 87, 140, VOLUME_MAX])
def test_target_is_far_enough_from_current(current):
    target = pick_far_target(VOLUME_MIN, VOLUME_MAX, current)
    span = VOLUME_MAX - VOLUME_MIN

    assert abs(target - current) >= span * 0.25, (current, target)


def test_out_of_range_current_is_clamped():
    assert pick_far_target(VOLUME_MIN, VOLUME_MAX, -50) == 140
    assert pick_far_target(VOLUME_MIN, VOLUME_MAX, 999) == 35


# =====================================================================
# 3. Piksel eslemesi ClickableSlider ile uyumlu
# =====================================================================

def test_target_x_matches_the_product_value_mapping():
    """`target_x_for_value` -> `_value_at` gidis-donusu ayni degeri verir."""
    from app.ui_components import ClickableSlider
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    slider = ClickableSlider(Qt.Orientation.Horizontal)
    slider.setRange(VOLUME_MIN, VOLUME_MAX)
    slider.resize(300, 20)
    app.processEvents()

    for value in (35, 44, 87, 140):
        x = target_x_for_value(value, VOLUME_MIN, VOLUME_MAX, slider.width())
        assert abs(slider._value_at(x) - value) <= value_tolerance_for_width(
            VOLUME_MIN, VOLUME_MAX, slider.width()), (value, x)


def test_value_tolerance_is_narrow_not_twenty():
    """Piksel yuvarlamasi disinda genis tolerans KULLANILMAZ."""
    tolerance = value_tolerance_for_width(VOLUME_MIN, VOLUME_MAX, 300)

    assert tolerance < 5, tolerance
    assert value_tolerance_for_width(VOLUME_MIN, VOLUME_MAX, 60) < 20
