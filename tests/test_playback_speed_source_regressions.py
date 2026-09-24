# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Menü çubuğu ve video sağ-tık menüsü aynı hız listesini kullanmalı."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _float_list_literals(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.List, ast.Tuple)) and len(node.elts) >= 4 and all(
                isinstance(e, ast.Constant) and isinstance(e.value, float)
                for e in node.elts):
            found.append(node.lineno)
    return found


def test_speed_lists_have_a_single_source():
    # Ayrı ayrı yazılmış listeler zamanla ayrışır; iki menü farklı hız sunar.
    for name in ("menu_actions.py", "video_frame.py"):
        assert _float_list_literals(ROOT / "app" / name) == [], name
    from app.config import PLAYBACK_SPEEDS
    assert PLAYBACK_SPEEDS == (0.5, 0.75, 1.0, 1.25, 1.5, 2.0)
