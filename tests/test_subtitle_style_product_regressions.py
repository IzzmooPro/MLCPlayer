# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Altyazı stil sözleşmesinin ÜRÜN yolundaki karşılığı.

- `restore_subtitle_settings()` eski `#RRGGBBAA` kaydını bir kez migrate
  eder ve arka plan kutusunu kaydedilmiş alfadan TÜRETİR.
- Dialog uygulaması atomiktir; başarısızlıkta dialog kapanmaz.
"""
from types import SimpleNamespace

import pytest
from PyQt6.QtGui import QColor

from app import menu_actions
from app.config import SUBTITLE_DEFAULTS
from app.player import MPVPlayer
from app.subtitle_style import (ASS_OVERRIDE_FORCE, BACKGROUND_BOX,
                                BACKGROUND_BOX_SHADOW_OFFSET, OUTLINE_AND_SHADOW,
                                SCHEMA_KEY, STYLE_SCHEMA_VERSION)


class FakeSettings:
    def __init__(self, values=None):
        self.values = dict(values or {})

    def value(self, key, default=None):
        return self.values.get(key, default)

    def setValue(self, key, value):
        self.values[key] = value

    def contains(self, key):
        return key in self.values

    def remove(self, key):
        self.values.pop(key, None)

    def sync(self):
        pass


class FakeMPV:
    def __init__(self):
        self.props = {}

    def __setattr__(self, name, value):
        if name == "props":
            object.__setattr__(self, name, value)
            return
        self.props[name] = value

    def __getattr__(self, name):
        try:
            return object.__getattribute__(self, "props")[name]
        except KeyError:
            raise AttributeError(name)


def restore(values):
    player = SimpleNamespace(settings=FakeSettings(values), mpv_player=FakeMPV())
    MPVPlayer.restore_subtitle_settings(player)
    return player


# --- Oturum geri yukleme ---

def test_defaults_reach_mpv_in_canonical_form():
    player = restore({})

    assert player.mpv_player.props["sub_color"] == "#FFFFFFFF"
    assert player.mpv_player.props["sub_border_color"] == "#FF000000"
    assert player.mpv_player.props["sub_ass_override"] == ASS_OVERRIDE_FORCE


def test_legacy_rgba_settings_are_migrated_once_on_startup():
    player = restore({"subtitle/sub_color": "#F26A3DFF",
                      "subtitle/sub_back_color": "#000000FF",
                      "subtitle/sub_ass_override": True})

    assert player.mpv_player.props["sub_color"] == "#FFF26A3D"
    assert player.mpv_player.props["sub_back_color"] == "#FF000000"
    assert player.mpv_player.props["sub_ass_override"] == ASS_OVERRIDE_FORCE
    assert player.settings.value(SCHEMA_KEY) == STYLE_SCHEMA_VERSION


def test_a_second_startup_does_not_convert_the_colour_again():
    first = restore({"subtitle/sub_color": "#F26A3DFF"})
    second = restore(dict(first.settings.values))

    assert second.mpv_player.props["sub_color"] == "#FFF26A3D"


def test_opaque_background_turns_on_the_real_background_box():
    player = restore({"subtitle/sub_back_color": "#FF000000",
                      SCHEMA_KEY: STYLE_SCHEMA_VERSION})

    assert player.mpv_player.props["sub_border_style"] == BACKGROUND_BOX
    assert player.mpv_player.props["sub_shadow_offset"] == \
        BACKGROUND_BOX_SHADOW_OFFSET


def test_transparent_background_keeps_outline_and_shadow():
    player = restore({SCHEMA_KEY: STYLE_SCHEMA_VERSION})

    assert player.mpv_player.props["sub_border_style"] == OUTLINE_AND_SHADOW


def test_a_broken_setting_does_not_stop_the_other_properties():
    class PickyMPV(FakeMPV):
        def __setattr__(self, name, value):
            if name == "sub_scale":
                raise RuntimeError("rejected")
            super().__setattr__(name, value)

    player = SimpleNamespace(settings=FakeSettings({}), mpv_player=PickyMPV())
    MPVPlayer.restore_subtitle_settings(player)

    assert player.mpv_player.props["sub_color"] == "#FFFFFFFF"
    assert player.mpv_player.props["sub_border_style"] == OUTLINE_AND_SHADOW


# --- Dialog yardimcilari canonical bicim kullanir ---

def test_dialog_helpers_use_the_canonical_argb_contract():
    assert menu_actions._qcolor_to_mpv(QColor(242, 106, 61, 255)) == "#FFF26A3D"
    color = menu_actions._mpv_color_to_qcolor("#FFF26A3D", "#FF000000")
    assert (color.red(), color.green(), color.blue(), color.alpha()) == \
        (242, 106, 61, 255)


def test_reset_defaults_are_readable_by_the_canonical_parser():
    for key in ("sub_color", "sub_back_color", "sub_border_color"):
        color = menu_actions._mpv_color_to_qcolor(SUBTITLE_DEFAULTS[key],
                                                  "#00000000")
        assert menu_actions._qcolor_to_mpv(color) == SUBTITLE_DEFAULTS[key]
