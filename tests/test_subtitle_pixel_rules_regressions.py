# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""`tests/subtitle_pixel_rules.py` için regresyon testleri.

Gerçek MPV görüntüsünde alınan kararlar (altyazı gerçekten göründü mü,
kutu gerçekten dolu mu, kenarlık yazıdan ayrı bir küme mi) burada
sentetik karelerle ölçülür. Qt, MPV veya dosya sistemi kullanılmaz.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest  # noqa: E402

from subtitle_pixel_rules import (bbox_centre, bbox_size,  # noqa: E402
                                  contains, fill_ratio,
                                  growth_ratio,
                                  horizontal_centre_offset, intersection,
                                  make_frame, matches, overlap_ratio,
                                  padding, padding_problems, pixel,
                                  scan_changed, scan_changed_color,
                                  scan_color)


def build(width, height, background=(10, 10, 10)):
    return bytearray(bytes(background) * (width * height))


def put(data, width, x, y, rgb):
    index = (y * width + x) * 3
    data[index], data[index + 1], data[index + 2] = rgb


def frame_with(width, height, cells, background=(10, 10, 10)):
    data = build(width, height, background)
    for (x, y), rgb in cells.items():
        put(data, width, x, y, rgb)
    return make_frame(width, height, bytes(data))


def test_make_frame_rejects_wrong_payload_size():
    with pytest.raises(ValueError):
        make_frame(2, 2, b"\x00" * 11)


def test_make_frame_rejects_empty_geometry():
    with pytest.raises(ValueError):
        make_frame(0, 4, b"")


def test_pixel_reads_rgb_in_order():
    frame = frame_with(3, 2, {(1, 1): (200, 100, 50)})
    assert pixel(frame, 1, 1) == (200, 100, 50)
    assert pixel(frame, 0, 0) == (10, 10, 10)


def test_matches_uses_explicit_per_channel_tolerance():
    assert matches((100, 100, 100), (108, 92, 100), 8)
    assert not matches((100, 100, 100), (109, 100, 100), 8)


def test_scan_color_reports_count_and_bbox():
    cells = {(2, 3): (240, 100, 60), (5, 7): (242, 106, 61)}
    frame = frame_with(10, 10, cells)
    stats = scan_color(frame, (242, 106, 61), 10)
    assert stats["count"] == 2
    assert stats["bbox"] == (2, 3, 5, 7)
    assert stats["centre"] == (3, 5)


def test_scan_color_missing_mask_is_not_pass_material():
    frame = frame_with(6, 6, {})
    stats = scan_color(frame, (242, 106, 61), 4)
    assert stats["count"] == 0
    assert stats["bbox"] is None
    assert stats["centre"] is None


def test_scan_color_honours_region():
    frame = frame_with(10, 10, {(1, 1): (255, 255, 255),
                                (8, 8): (255, 255, 255)})
    stats = scan_color(frame, (255, 255, 255), 4, region=(5, 5, 9, 9))
    assert stats["count"] == 1
    assert stats["bbox"] == (8, 8, 8, 8)


def test_scan_changed_finds_only_changed_pixels():
    before = frame_with(8, 8, {})
    after = frame_with(8, 8, {(3, 4): (255, 255, 255)})
    stats = scan_changed(before, after, 12)
    assert stats["count"] == 1
    assert stats["bbox"] == (3, 4, 3, 4)


def test_scan_changed_ignores_noise_below_threshold():
    before = frame_with(4, 4, {(1, 1): (100, 100, 100)})
    after = frame_with(4, 4, {(1, 1): (104, 96, 100)})
    assert scan_changed(before, after, 8)["count"] == 0


def test_scan_changed_rejects_geometry_mismatch():
    with pytest.raises(ValueError):
        scan_changed(frame_with(4, 4, {}), frame_with(5, 4, {}), 4)


def test_scan_changed_color_requires_both_change_and_colour():
    # Video karesinde ZATEN turuncu olan piksel kanıt sayılmamalı.
    before = frame_with(8, 8, {(1, 1): (242, 106, 61)})
    after = frame_with(8, 8, {(1, 1): (242, 106, 61),
                              (5, 5): (242, 106, 61)})
    stats = scan_changed_color(before, after, 12, (242, 106, 61), 12)
    assert stats["count"] == 1
    assert stats["bbox"] == (5, 5, 5, 5)


def test_scan_changed_color_ignores_change_in_other_colour():
    before = frame_with(8, 8, {})
    after = frame_with(8, 8, {(4, 4): (0, 32, 160)})
    assert scan_changed_color(before, after, 12, (242, 106, 61), 12)["count"] == 0


def solid_rows(width, height, rows, rgb, background=(10, 10, 10)):
    data = build(width, height, background)
    for y, (x0, x1) in rows.items():
        for x in range(x0, x1 + 1):
            put(data, width, x, y, rgb)
    return make_frame(width, height, bytes(data))


def test_longest_run_separates_box_from_text():
    from subtitle_pixel_rules import longest_run
    blue = (0, 32, 160)
    # Gerçek kutu: satır boyunca kesintisiz.
    box = solid_rows(40, 6, {2: (0, 39), 3: (0, 39)}, blue)
    # Yalnız yazı: aynı satırda kısa parçalar.
    text = solid_rows(40, 6, {2: (0, 3), 3: (10, 12)}, blue)
    box_run = longest_run(box, blue, 8)
    text_run = longest_run(text, blue, 8)
    assert box_run["best"] == 40
    assert box_run["rows_over_half"] == 2
    assert text_run["best"] == 4
    assert text_run["rows_over_half"] == 0


def test_longest_run_reports_row_and_empty_mask():
    from subtitle_pixel_rules import longest_run
    frame = solid_rows(20, 5, {3: (4, 9)}, (255, 255, 255))
    stats = longest_run(frame, (255, 255, 255), 6)
    assert stats["best"] == 6 and stats["row"] == 3
    assert longest_run(frame, (0, 255, 0), 6) == {"best": 0, "row": None,
                                                  "rows_over_half": 0}


def test_changed_longest_run_uses_frame_difference():
    from subtitle_pixel_rules import changed_longest_run
    before = frame_with(30, 4, {})
    after = solid_rows(30, 4, {1: (0, 29)}, (200, 200, 200))
    stats = changed_longest_run(before, after, 12)
    assert stats["best"] == 30 and stats["rows_over_half"] == 1
    assert changed_longest_run(before, before, 12)["best"] == 0


def test_solid_box_ratio():
    from subtitle_pixel_rules import solid_box_ratio
    assert solid_box_ratio(700, (0, 0, 747, 122)) == pytest.approx(0.9358,
                                                                   abs=1e-3)
    assert solid_box_ratio(40, None) == 0.0


def test_bbox_size_and_centre():
    assert bbox_size((10, 20, 19, 29)) == (10, 10)
    assert bbox_size(None) == (0, 0)
    assert bbox_centre((10, 20, 19, 29)) == (14, 24)
    assert bbox_centre(None) is None


def test_fill_ratio_separates_text_from_solid_box():
    text = fill_ratio(120, (0, 0, 39, 19))
    box = fill_ratio(760, (0, 0, 39, 19))
    assert text < 0.2
    assert box > 0.9
    assert fill_ratio(0, None) == 0.0


def test_contains_and_slack():
    assert contains((0, 0, 99, 99), (10, 10, 20, 20))
    assert not contains((0, 0, 99, 99), (10, 10, 120, 20))
    assert contains((0, 0, 99, 99), (-2, 0, 99, 99), slack=2)
    assert not contains(None, (1, 1, 2, 2))


def test_padding_measures_four_sides():
    pads = padding(inner=(12, 14, 40, 30), outer=(8, 10, 46, 34))
    assert pads == {"left": 4, "top": 4, "right": 6, "bottom": 4}


def test_padding_negative_when_box_clips_text():
    pads = padding(inner=(8, 10, 46, 34), outer=(12, 14, 40, 30))
    assert pads["left"] == -4 and pads["right"] == -6


def test_padding_problems_flag_too_tight_and_too_wide():
    tight = padding_problems({"left": 0, "top": 3, "right": 3, "bottom": 3},
                             minimum=2, maximum=40)
    assert tight == ["left=0<2"]
    wide = padding_problems({"left": 90, "top": 3, "right": 3, "bottom": 3},
                            minimum=2, maximum=40)
    assert wide == ["left=90>40"]
    assert padding_problems(None, 2, 40) == ["padding_unmeasurable"]
    assert padding_problems({"left": 4, "top": 4, "right": 4, "bottom": 4},
                            2, 40) == []


def test_intersection_and_overlap_ratio():
    assert intersection((0, 0, 10, 10), (5, 5, 20, 20)) == (5, 5, 10, 10)
    assert intersection((0, 0, 10, 10), (50, 50, 60, 60)) is None
    assert overlap_ratio((0, 0, 9, 9), (0, 0, 4, 9)) == pytest.approx(0.5)
    assert overlap_ratio((0, 0, 9, 9), (50, 50, 60, 60)) == 0.0


def test_growth_ratio_never_invents_growth_from_zero():
    assert growth_ratio(100, 180) == pytest.approx(1.8)
    assert growth_ratio(0, 180) == 0.0
    assert growth_ratio(None, 180) == 0.0


def test_horizontal_centre_offset():
    assert horizontal_centre_offset((40, 0, 59, 9), (0, 0, 99, 99)) == 0
    assert horizontal_centre_offset((60, 0, 79, 9), (0, 0, 99, 99)) == 20
    assert horizontal_centre_offset(None, (0, 0, 99, 99)) is None
