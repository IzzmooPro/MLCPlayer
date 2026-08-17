# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Altyazı görünüm kabul runner'inin ayrıştırma ve sınıflandırma testleri.

Runner gerçek child başlatmadan test edilir: yalnız çıktı ayrıştırma ve
"test edilemedi ASLA başarılı değildir" sözleşmesi ölçülür.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from run_subtitle_visual_acceptance import (ASS_REPEAT_COUNT,  # noqa: E402
                                            SCENARIOS,
                                            classify_group,
                                            log_path_for_attempt,
                                            overall_exit_code, parse_rows,
                                            parse_shots, repeat_count_for)

CHILD_LOG = """CHILD_ISOLATION settings=X temp=Y qt_test_mode=True
SHOT baseline-nosub C:\\temp\\a-01-baseline-nosub.png
SHOT orange-text C:\\temp\\a-02-orange-text.png
MEASURE|a_orange_color|{"count": 12952}
RESULT|a_text_color|a_readback_orange|libmpv readback|#FFF26A3D|#FFF26A3D|PASS|
RESULT|a_text_color|a_orange_pixels|degisen VE turuncu|>=400|12952|PASS|kanit
MARK_DONE scenario=a_text_color
"""


def test_parse_rows_extracts_status_and_evidence():
    rows = parse_rows(CHILD_LOG)
    assert [row["test"] for row in rows] == ["a_readback_orange",
                                             "a_orange_pixels"]
    assert rows[0]["status"] == "PASS"
    assert rows[1]["evidence"] == "kanit"


def test_parse_rows_ignores_non_result_lines():
    assert parse_rows("MEASURE|x|{}\nSHOT a b\n") == []


def test_parse_shots_maps_name_to_path():
    shots = parse_shots(CHILD_LOG)
    assert shots["orange-text"].endswith("a-02-orange-text.png")
    assert len(shots) == 2


def test_missing_mark_done_is_not_pass():
    rows = parse_rows(CHILD_LOG)
    assert classify_group(rows, timed_out=False, mark_done=False,
                          exit_code=0) == "INCOMPLETE"


def test_timeout_is_not_pass():
    rows = parse_rows(CHILD_LOG)
    assert classify_group(rows, timed_out=True, mark_done=True,
                          exit_code=0) == "TIMEOUT"


def test_blocked_row_blocks_whole_scenario():
    rows = parse_rows(CHILD_LOG) + [{"status": "BLOCKED"}]
    assert classify_group(rows, timed_out=False, mark_done=True,
                          exit_code=0) == "BLOCKED"


def test_nonzero_exit_with_clean_rows_is_crash():
    rows = parse_rows(CHILD_LOG)
    assert classify_group(rows, timed_out=False, mark_done=True,
                          exit_code=3221225477) == "CRASH"


def test_clean_run_is_pass():
    rows = parse_rows(CHILD_LOG)
    assert classify_group(rows, timed_out=False, mark_done=True,
                          exit_code=0) == "PASS"


def test_overall_exit_requires_every_scenario_pass():
    assert overall_exit_code(["PASS", "PASS"]) == 0
    assert overall_exit_code(["PASS", "BLOCKED"]) == 1
    assert overall_exit_code([]) == 1


def test_scenario_table_covers_every_lettered_requirement():
    names = [entry[1] for entry in SCENARIOS]
    for prefix in "abcdefghijkl":
        assert any(name.startswith(f"{prefix}_") for name in names), prefix
    # Her senaryonun kendi timeout'u ve video anahtarı olmalı.
    # NOT: girdiler 5. alan olarak İSTEĞE BAĞLI ek ortam sözlüğü taşır
    # (`QT_SCALE_FACTOR` ile %150 DPI koşumu ayrı child sürecidir).
    for entry in SCENARIOS:
        order, name, timeout, video_key = entry[:4]
        assert timeout > 0 and video_key.startswith("MLC_")
        if len(entry) > 4:
            assert isinstance(entry[4], dict) and entry[4]


def test_the_dpi_runs_are_separate_child_processes():
    """`QT_SCALE_FACTOR` süreç başlamadan okunur; ayrı koşum şart."""
    scaled = [entry for entry in SCENARIOS
              if len(entry) > 4 and "QT_SCALE_FACTOR" in entry[4]]

    assert scaled, "%150 DPI koşumu tanımlı değil"
    for entry in scaled:
        assert entry[4]["QT_SCALE_FACTOR"] == "1.5"
        # Aynı senaryo %100 DPI ile de koşulmalı (karşılaştırma için).
        base = [other for other in SCENARIOS
                if other[1] == entry[1] and len(other) == 4]
        assert base, entry[1]


def test_ass_band_runs_repeat_five_times_at_each_dpi():
    assert ASS_REPEAT_COUNT >= 5
    assert repeat_count_for("P", "p_ass_band") == ASS_REPEAT_COUNT
    assert repeat_count_for("P150", "p_ass_band") == ASS_REPEAT_COUNT
    assert repeat_count_for("O", "o_band") == 1


def test_every_repeat_has_a_unique_log_name(tmp_path):
    paths = [log_path_for_attempt(str(tmp_path), "P", "p_ass_band",
                                  attempt, ASS_REPEAT_COUNT)
             for attempt in range(1, ASS_REPEAT_COUNT + 1)]

    assert len(set(paths)) == ASS_REPEAT_COUNT
    assert paths[0].endswith("P-r01-p_ass_band.log")
    assert paths[-1].endswith(
        f"P-r{ASS_REPEAT_COUNT:02d}-p_ass_band.log")
