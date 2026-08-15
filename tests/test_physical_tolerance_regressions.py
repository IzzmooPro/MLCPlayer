"""Fiziksel kabul TOLERANS formullerinin regresyonlari.

Genis tolerans sessizce yanlis sonucu PASS yapar. Onceki timeline
olcumu `duration * 0.015` kullaniyordu: ~3 saatlik videoda **±177 sn**.
Gercek olculen sapma bir saniyenin altindaydi, yani tolerans olcumun
anlamini yok ediyordu. Slider tarafinda da sabit ±20/1000 (%2) vardi.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest

from physical_tolerances import (MAX_TIME_TOLERANCE_S, seek_time_tolerance,
                                 slider_value_tolerance)

THREE_HOURS = 11828.9  # gercek kabul videosunun suresi (sn)


# =====================================================================
# 1. Slider degeri toleransi
# =====================================================================

def test_value_tolerance_is_derived_from_pixel_resolution():
    span, width = 1000, 1300
    step = math.ceil(span / width)

    assert slider_value_tolerance(span, width) == max(3, 2 * step)


def test_wide_timeline_does_not_use_the_old_constant():
    """1000 aralik + genis timeline'da tolerans 20 OLAMAZ."""
    assert slider_value_tolerance(1000, 1300) < 20
    assert slider_value_tolerance(1000, 900) < 20
    assert slider_value_tolerance(1000, 560) < 20


def test_narrow_timeline_scales_with_pixels():
    """Dar timeline'da bir piksel daha fazla birime denk gelir."""
    narrow = slider_value_tolerance(1000, 200)
    wide = slider_value_tolerance(1000, 1300)

    assert narrow > wide
    assert narrow == 2 * math.ceil(1000 / 200)


def test_value_tolerance_has_a_safe_floor():
    assert slider_value_tolerance(1000, 100000) == 3
    assert slider_value_tolerance(0, 0) >= 3


# =====================================================================
# 2. Seek zamani toleransi
# =====================================================================

def test_three_hour_video_tolerance_is_not_177_seconds():
    tolerance = seek_time_tolerance(THREE_HOURS)

    assert tolerance < 20, tolerance
    assert tolerance != pytest.approx(THREE_HOURS * 0.015, rel=0.01)


def test_time_tolerance_never_exceeds_the_hard_cap():
    for duration in (THREE_HOURS, 36000.0, 360000.0):
        assert seek_time_tolerance(duration) <= MAX_TIME_TOLERANCE_S


def test_short_video_keeps_a_usable_floor():
    assert seek_time_tolerance(10.0) == 3.0
    assert seek_time_tolerance(0.0) == 3.0


# =====================================================================
# 3. Kabul/ret davranisi
# =====================================================================

def accepted(expected_time, actual_time, duration=THREE_HOURS):
    return abs(actual_time - expected_time) <= seek_time_tolerance(duration)


def test_thirty_second_seek_error_is_rejected():
    """Hedeften 30 sn sapma FAIL olmali."""
    assert not accepted(1183.0, 1213.0)
    assert not accepted(1183.0, 1153.0)


def test_natural_playback_drift_of_about_one_second_is_accepted():
    """Gozlenen ~0.4-1 sn dogal ilerleme PASS olmali."""
    assert accepted(1182.9, 1183.2)
    assert accepted(1182.9, 1183.9)


def test_value_error_of_two_pixels_is_accepted_but_two_percent_is_not():
    span, width = 1000, 1300
    tolerance = slider_value_tolerance(span, width)
    two_pixels = 2 * math.ceil(span / width)

    assert two_pixels <= tolerance
    assert 20 > tolerance, "eski %2'lik sabit hala kabul ediliyor"
