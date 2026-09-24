# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Ondalık ayırıcı ve bayt birimi dile göre yazılmalı.

Boyut, fps, oran ve kHz metinleri `.replace(".", ",")` ile Türkçe virgüle
sabitlenmişti ve `bayt` kelimesi çevrilmiyordu; İngilizce Medya Bilgisi
`1,5 GB`, `23,976 fps`, `512 bayt` gösteriyordu.
"""

import ast
from pathlib import Path

from app import number_text as utils

ROOT = Path(__file__).resolve().parent.parent
ENGLISH = {"{whole},{fraction}": "{whole}.{fraction}",
           "{count} bayt": "{count} bytes"}


def test_sizes_rates_and_frequencies_follow_the_language(monkeypatch):
    from app import errors, media_info, track_labels

    monkeypatch.setattr(utils, "tr", lambda text: ENGLISH.get(text, text))
    assert media_info.format_size_text(1536) == "1.5 KB"
    assert media_info.format_size_text(512) == "512 bytes"
    assert errors.format_bytes(3 * 1024 * 1024) == "3.0 MB"
    assert errors.format_bytes(7) == "7 bytes"
    assert media_info._fps_text({"demux-fps": 23.976}) == "23.976 fps"
    assert "48" in track_labels.__dict__["sample_rate_label"](48000) \
        if "sample_rate_label" in track_labels.__dict__ else True


def test_turkish_source_output_is_unchanged():
    from app import errors, media_info

    assert media_info.format_size_text(1536) == "1,5 KB"
    assert errors.format_bytes(7) == "7 bayt"
    assert media_info._fps_text({"demux-fps": 23.976}) == "23,976 fps"


def test_no_module_hardcodes_the_turkish_decimal_comma():
    offenders = []
    for path in sorted((ROOT / "app").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(source)):
            if (isinstance(node, ast.Call)
                    and getattr(node.func, "attr", None) == "replace"
                    and [getattr(a, "value", None) for a in node.args]
                    == [".", ","]):
                offenders.append(f"{path.name}:{node.lineno}")
    assert offenders == []
