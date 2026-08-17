# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Canonical stil değerlerinin GERÇEK libmpv tarafından kabul edilmesi.

Offscreen birim testleri MPV'nin biçimi gerçekten anlayıp anlamadığını
kanıtlamaz. Bu kapı, aynı değerleri gerçek bir mpv nesnesine yazar ve
geri okur (`vo=null`, `ao=null`; ekran ve hoparlör kullanılmaz).

Opt-in: `MLC_NATIVE_SMOKE=1`. Piksel karşılaştırması burada YAPILMAZ.
"""
import json
import os
import subprocess
import sys

import pytest

from app.subtitle_style import (ASS_OVERRIDE_FORCE, BACKGROUND_BOX,
                                BACKGROUND_BOX_SHADOW_OFFSET)

CHILD = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "subtitle_style_property_smoke_child.py")

pytestmark = pytest.mark.skipif(
    os.environ.get("MLC_NATIVE_SMOKE") != "1",
    reason="gercek libmpv kapisi: MLC_NATIVE_SMOKE=1 gerekir")


@pytest.fixture(scope="module")
def readback():
    proc = subprocess.run([sys.executable, CHILD], capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          timeout=120, env={**os.environ,
                                            "MLC_NATIVE_SMOKE": "1"})
    line = next((l for l in (proc.stdout or "").splitlines()
                 if l.startswith("STYLE_JSON ")), "")
    assert line, f"child ciktisi yok: exit={proc.returncode}"
    return json.loads(line[len("STYLE_JSON "):])


def test_real_mpv_accepts_every_style_property(readback):
    assert readback["errors"] == {}, "gercek MPV bir property'yi reddetti"


def test_real_mpv_reads_back_the_canonical_colours(readback):
    values = readback["readback"]
    assert values["sub_color"] == "#FFF26A3D", "turuncu MPV'de degisti"
    assert values["sub_back_color"] == "#FF000000"
    assert values["sub_border_color"] == "#FF000000"


def test_real_mpv_keeps_the_background_box_contract(readback):
    values = readback["readback"]
    assert values["sub_border_style"] == BACKGROUND_BOX
    assert float(values["sub_shadow_offset"]) == BACKGROUND_BOX_SHADOW_OFFSET


def test_real_mpv_keeps_ass_override_forced(readback):
    assert readback["readback"]["sub_ass_override"] == ASS_OVERRIDE_FORCE


def test_real_mpv_keeps_the_numeric_settings(readback):
    values = readback["readback"]
    assert float(values["sub_delay"]) == pytest.approx(1.5)
    assert float(values["sub_scale"]) == pytest.approx(1.4, abs=1e-4)
    assert float(values["sub_pos"]) == pytest.approx(95.0)
    assert float(values["sub_border_size"]) == pytest.approx(3.5)
