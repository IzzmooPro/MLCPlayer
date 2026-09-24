# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Yüzde değerleri dile göre yazılmalı (Türkçe `%70`, İngilizce `70%`).

Ses, şeffaflık, altyazı konumu ve opaklık etiketleri `f"%{değer}"` ile
Türkçe sıraya sabitlenmişti; İngilizce arayüz `Transparency: %70`
gösteriyordu. Tek çevrilebilir biçimleyici kullanılır.
"""

import ast
from pathlib import Path

from app import number_text as utils

ROOT = Path(__file__).resolve().parent.parent


def test_percent_text_goes_through_the_translator(monkeypatch):
    monkeypatch.setattr(utils, "tr", lambda text: text.replace(
        "%{value}", "{value}%"))
    assert utils.percent_text(70) == "70%"
    assert utils.percent_text(70.6) == "71%"


def test_percent_text_defaults_to_turkish_order():
    assert utils.percent_text(5) == "%5"


def test_no_ui_string_hardcodes_the_turkish_percent_order():
    offenders = []
    for path in sorted((ROOT / "app").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.JoinedStr):
                continue
            for part, following in zip(node.values, node.values[1:]):
                if (isinstance(part, ast.Constant)
                        and str(part.value).endswith("%")
                        and isinstance(following, ast.FormattedValue)):
                    offenders.append(f"{path.name}:{node.lineno}")
    # Günlük/konsol satırları Türkçe kalabilir; yalnız arayüz metinleri.
    ui = [o for o in offenders if not o.startswith(("errors.py",))]
    assert ui == []
