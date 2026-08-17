# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Adı "video" olan matris senaryosu sessizce no-video testine dönüşmemeli.

Gerçek koşumla kanıtlandı: `--video` verilmeden

    python tests/run_native_overlay_matrix.py --only default_cinematic_video_nofocus

çıktısı `SKIP_PLAY no-video`, `RESULTS: ... video=False` ve buna rağmen
`MATRIX_EXIT=0 failed_cases=-` üretiyordu. Yani video gerektiren senaryo
video oynatmadan BAŞARILI sayılıyordu.

Bu dosya iki şeyi bağlar:
1. Video gerektiren senaryolar açıkça işaretlenir (`requires_video`).
2. Video kanıtı (gerçekten oynatılan süre) olmadan bu senaryolar geçemez.
"""
import importlib.util
import os

import pytest

MATRIX = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "run_native_overlay_matrix.py")
SMOKE_CHILD = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "native_overlay_smoke_child.py")


@pytest.fixture(scope="module")
def matrix():
    spec = importlib.util.spec_from_file_location("matrix_video_mod", MATRIX)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- 1. Video gerektiren senaryolar açıkça işaretlenmeli ---

def test_video_named_cases_declare_that_they_require_video(matrix):
    cases = matrix.base_matrix("real.mkv")
    video_cases = [case for case in cases
                   if "video" in case["name"] and "novideo" not in case["name"]]
    assert video_cases, "adı video olan senaryo bulunamadı"
    for case in video_cases:
        assert case.get("requires_video") is True, (
            f"{case['name']} video gerektirdiğini bildirmiyor")


def test_novideo_cases_do_not_require_video(matrix):
    cases = matrix.base_matrix("real.mkv")
    for case in cases:
        if "novideo" in case["name"]:
            assert not case.get("requires_video"), (
                f"{case['name']} yanlışlıkla video gerektiriyor")


# --- 2. Video yolu yokken sessiz geçiş olmamalı ---

def test_video_case_without_a_path_is_not_silently_accepted(matrix):
    """Yol verilmemişse senaryo açık bir sonuç üretmeli, geçmiş sayılmamalı."""
    case = next(c for c in matrix.base_matrix("")
                if c["name"] == "default_cinematic_video_nofocus")
    assert case.get("requires_video") is True

    fields = {"ui": "cinematic", "video": False}
    failures = matrix.evaluate_behavior(case, fields)

    assert any("video" in reason for reason in failures), (
        f"videosuz çalışan video senaryosu geçti: failures={failures}")


def test_video_case_needs_real_playback_evidence(matrix):
    """`video=True` yetmez; gerçekten oynatıldığına dair kanıt gerekir."""
    case = next(c for c in matrix.base_matrix("real.mkv")
                if c["name"] == "default_cinematic_video_nofocus")

    without_evidence = matrix.evaluate_behavior(
        case, {"ui": "cinematic", "video": True})
    assert any("playback" in reason for reason in without_evidence), (
        f"oynatma kanıtı olmadan geçti: {without_evidence}")

    with_evidence = matrix.evaluate_behavior(
        case, {"ui": "cinematic", "video": True,
               "playback_duration": "6376.0", "playback_time_pos": "4.5"})
    assert not [reason for reason in with_evidence if "video" in reason
                or "playback" in reason], (
        f"geçerli oynatma kanıtı reddedildi: {with_evidence}")


def test_zero_time_pos_is_not_accepted_as_playback(matrix):
    case = next(c for c in matrix.base_matrix("real.mkv")
                if c["name"] == "default_cinematic_video_nofocus")

    failures = matrix.evaluate_behavior(
        case, {"ui": "cinematic", "video": True,
               "playback_duration": "6376.0", "playback_time_pos": "0"})

    assert any("playback" in reason for reason in failures), (
        f"time_pos=0 oynatma sayıldı: {failures}")


# --- 3. Child gerçekten oynatma kanıtı raporlamalı ---

def test_smoke_child_reports_playback_evidence_fields():
    source = open(SMOKE_CHILD, encoding="utf-8").read()
    assert 'results["playback_duration"]' in source, (
        "child RESULTS'a oynatma süresi kanıtı yazmıyor")
    assert 'results["playback_time_pos"]' in source, (
        "child RESULTS'a time_pos kanıtı yazmıyor")


def test_skip_play_marker_is_still_visible_for_diagnosis():
    """SKIP_PLAY marker'ı kalmalı; ama artık sessiz geçişe yol açmamalı."""
    source = open(SMOKE_CHILD, encoding="utf-8").read()
    assert "SKIP_PLAY no-video" in source
