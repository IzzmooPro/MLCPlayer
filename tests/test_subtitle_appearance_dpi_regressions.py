"""Altyazı Ayarları penceresi %100, %125 ve %150 DPI'da sığmalı.

`QT_SCALE_FACTOR` süreç başlangıcında okunduğu için ölçüm ayrı child
süreçlerinde yapılır (bkz. `subtitle_appearance_layout_child.py`).
Kullanıcı ayarları kirletilmez: her koşum kendi geçici dizinini alır.
"""
import json
import os
import subprocess
import sys

import pytest

CHILD = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "subtitle_appearance_layout_child.py")
SCALES = ("1", "1.25", "1.5")


def run_child(tmp_path, scale="1", minimum=False, scenario="default",
              shot=""):
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["QT_SCALE_FACTOR"] = scale
    env["QT_ENABLE_HIGHDPI_SCALING"] = "0"
    command = [sys.executable, CHILD, "--settings", str(tmp_path),
               "--scenario", scenario]
    if minimum:
        command.append("--minimum")
    if shot:
        command += ["--shot", shot]
    proc = subprocess.run(command, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=180,
                          env=env)
    line = next((l for l in (proc.stdout or "").splitlines()
                 if l.startswith("LAYOUT_JSON ")), "")
    assert line, (f"child ciktisi yok: exit={proc.returncode} "
                  f"stderr={(proc.stderr or '')[-400:]}")
    return json.loads(line[len("LAYOUT_JSON "):])


@pytest.mark.parametrize("scale", SCALES)
def test_dialog_fits_a_1366x768_screen_at_every_dpi(tmp_path, scale):
    report = run_child(tmp_path, scale=scale)

    assert report["fits_target_screen"], (
        f"%{float(scale) * 100:.0f} DPI'da pencere {report['dialog']} "
        f"1366x768 ekrana sigmiyor")


@pytest.mark.parametrize("scale", SCALES)
def test_no_control_is_clipped_at_any_dpi(tmp_path, scale):
    report = run_child(tmp_path, scale=scale)

    assert report["clipped"] == [], (
        f"%{float(scale) * 100:.0f} DPI'da kirpilan kontrol: "
        f"{report['clipped']}")


# ESKIYEN TEST: `test_the_preview_stays_the_wider_half_at_any_dpi`
# YATAY yerlesimde sag panelin genislik payini (%55-70) olcuyordu. Yeni
# tasarim DIKEY: onizleme tam genislikte, ayarlarin ALTINDA. Ayni
# kullanici garantisi (onizleme buyuk ve okunabilir kalir) asagida
# yeniden olculur.

@pytest.mark.parametrize("scale", SCALES)
def test_the_preview_stays_below_the_settings_and_large_at_any_dpi(tmp_path,
                                                                   scale):
    report = run_child(tmp_path, scale=scale)

    assert report["settings_above_preview"], report["settings_rect"]
    assert not report["panels_overlap"]
    assert report["preview_width"] >= report["dialog"][0] - 60, report
    assert report["preview_height"] >= 150, report


@pytest.mark.parametrize("scale", SCALES)
def test_the_preset_combos_are_readable_at_any_dpi(tmp_path, scale):
    """Kapali kutuda deger kirpilmaz, acilir listede tam etiket sigar."""
    report = run_child(tmp_path, scale=scale, minimum=True)

    for name, data in report["combos"].items():
        assert data["short_fits"], f"{name}: {data}"
        assert data["popup_fits_full_label"], f"{name}: {data}"


@pytest.mark.parametrize("scenario, expected", [
    ("popup_delay", 41), ("popup_scale", 7), ("popup_border", 11)])
def test_every_popup_opens_below_its_combo_and_closes(tmp_path, scenario,
                                                      expected):
    report = run_child(tmp_path, scenario=scenario)
    popup = report["popup"]

    assert popup["visible"], popup
    assert popup["item_count"] == expected, popup
    assert popup["inside_screen"], popup
    assert popup["closed_after_selection"], popup
    assert popup["below_combo"], popup
    # Olculen kirmizi kanit: stylesheet uygulanan QComboBox'ta
    # `setMaxVisibleItems()` yok sayiliyor ve 41 ogeli senkron listesi
    # 800 px yuksekliginde aciliyordu. `combobox-popup: 0` sonrasi
    # 146 px. Ust sinir ekrana gore verilir.
    assert popup["rect"][3] <= 400, popup


def test_the_palette_offers_no_colour_in_a_real_process(tmp_path):
    """ESKI AD: `test_the_transparent_button_clears_the_background_...`.

    Ayri "Seffaf" dugmesi kaldirildi; secenek arka plan PALETININ
    icindedir. Ayni kullanici garantisi gercek surecte olculur.
    """
    report = run_child(tmp_path, scenario="palette_open")
    palette = report["palette"]

    assert palette["visible"], palette
    assert palette["no_colour_visible"], palette
    assert palette["no_colour_text"] == palette["expected_text"]
    assert palette["no_colour_accessible"].strip() != ""
    assert palette["inside_screen"], palette


def test_choosing_no_colour_clears_the_background_in_a_real_process(tmp_path):
    report = run_child(tmp_path, scenario="palette_no_colour")

    assert report["palette"]["chosen_alpha"] == 0, report["palette"]
    assert report["palette"]["closed"], report["palette"]
    assert report["background_visible"] is False, report


def test_the_three_swatches_are_equal_and_adjacent_in_a_real_process(tmp_path):
    report = run_child(tmp_path)
    rects = [report["swatches"][key] for key in
             ("sub_color", "sub_back_color", "sub_border_color")]

    assert len({rect[2] for rect in rects}) == 1, rects
    assert len({rect[1] for rect in rects}) == 1, rects
    gaps = [second[0] - (first[0] + first[2])
            for first, second in zip(rects, rects[1:])]
    assert all(8 <= gap <= 12 for gap in gaps), gaps
    right_gap = report["dialog"][0] - (rects[-1][0] + rects[-1][2])
    assert right_gap >= 20, (right_gap, rects)


@pytest.mark.parametrize("scale", SCALES)
def test_nothing_is_clipped_at_the_minimum_size_at_any_dpi(tmp_path, scale):
    report = run_child(tmp_path, scale=scale, minimum=True)

    assert report["clipped"] == [], report["clipped"]
    assert report["fits_target_screen"]


def test_long_preview_text_never_leaves_the_surface(tmp_path):
    report = run_child(tmp_path, scenario="long_text")

    assert report["preview_text_inside"], (
        f"metin tasti: text={report['preview_text_rect']} "
        f"surface={report['preview_rect']}")


def test_a_failed_apply_keeps_the_window_open_in_a_real_process(tmp_path):
    report = run_child(tmp_path, scenario="apply_failure")

    assert report["visible"], "basarisiz uygulamada pencere kapandi"


def test_background_box_visibility_follows_the_alpha(tmp_path):
    assert run_child(tmp_path, scenario="orange_box")["background_visible"]
    assert not run_child(tmp_path,
                         scenario="clear_background")["background_visible"]


def test_bitmap_notice_only_appears_for_bitmap_tracks(tmp_path):
    assert run_child(tmp_path, scenario="bitmap")["bitmap_notice"]
    assert not run_child(tmp_path, scenario="default")["bitmap_notice"]


@pytest.mark.parametrize("scenario", ["bitmap", "long_text", "orange_box",
                                      "apply_failure", "clear_background",
                                      "large_text"])
def test_no_scenario_clips_a_control(tmp_path, scenario):
    """Bilgi satiri gorununce "Onizleme" etiketi kirpiliyordu."""
    report = run_child(tmp_path, scenario=scenario)

    assert report["clipped"] == [], report["clipped"]


@pytest.mark.parametrize("scale", SCALES)
def test_the_bitmap_notice_does_not_clip_anything_at_any_dpi(tmp_path, scale):
    report = run_child(tmp_path, scale=scale, scenario="bitmap",
                       minimum=True)

    assert report["clipped"] == [], report["clipped"]
