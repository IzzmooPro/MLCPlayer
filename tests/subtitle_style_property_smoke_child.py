# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""GERÇEK libmpv üzerinde altyazı stil property'lerini yaz ve geri oku.

- `vo=null`, `ao=null`: pencere açılmaz, hoparlörden ses ÇIKMAZ.
- Ekran/piksel karşılaştırması YAPILMAZ; bu tur yalnız property
  sözleşmesini ölçer.
- Opt-in: `MLC_NATIVE_SMOKE=1`.
- Sonuç tek satır JSON: `STYLE_JSON {...}`.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_BIN = os.path.join(ROOT, "bin")
os.environ["PATH"] = _BIN + os.pathsep + os.environ.get("PATH", "")
try:
    _dll_dir_handle = os.add_dll_directory(_BIN)
except Exception:
    _dll_dir_handle = None

from app.subtitle_style import (ASS_OVERRIDE_FORCE, BACKGROUND_BOX,  # noqa: E402
                                BACKGROUND_BOX_SHADOW_OFFSET, style_properties)

from PyQt6.QtGui import QColor  # noqa: E402

# Kullanicinin sectigi turuncu + opak siyah kutu.
VALUES = {
    "sub_delay": 1.5,
    "sub_scale": 1.4,
    "sub_pos": 95.0,
    "sub_border_size": 3.5,
    "sub_color": QColor(242, 106, 61, 255),
    "sub_back_color": QColor(0, 0, 0, 255),
    "sub_border_color": QColor(0, 0, 0, 255),
}


def main():
    if os.environ.get("MLC_NATIVE_SMOKE") != "1":
        print("SKIPPED: OPT_IN_REQUIRED", flush=True)
        return 0
    import mpv
    player = mpv.MPV(vo="null", ao="null", idle=True, terminal=False)
    result = {"written": {}, "readback": {}, "errors": {}}
    try:
        props = style_properties(VALUES)
        result["written"] = {k: v for k, v in props.items()}
        for name, value in props.items():
            try:
                setattr(player, name, value)
            except Exception as exc:
                result["errors"][name] = type(exc).__name__
        for name in props:
            try:
                result["readback"][name] = getattr(player, name)
            except Exception as exc:
                result["errors"][name] = type(exc).__name__
        result["expected_border_style"] = BACKGROUND_BOX
        result["expected_shadow_offset"] = BACKGROUND_BOX_SHADOW_OFFSET
        result["expected_ass_override"] = ASS_OVERRIDE_FORCE
        try:
            result["current_ao"] = player.current_ao
        except Exception:
            result["current_ao"] = None
    finally:
        try:
            player.stop()
        except Exception:
            pass
        try:
            player.terminate()
        except Exception:
            pass
    print("STYLE_JSON " + json.dumps(result, ensure_ascii=False, default=str),
          flush=True)
    return 0


if __name__ == "__main__":
    # Butun ciktilar flush edildikten SONRA cik (Qt+libmpv finalizasyon
    # riski bu kabulun parcasi degil).
    os._exit(main())
