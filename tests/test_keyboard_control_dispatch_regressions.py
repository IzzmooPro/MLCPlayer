# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Gerçek ana-pencere tuş yönlendirmesi ortak kontrol akışlarını kullanır."""

from types import SimpleNamespace

import pytest
from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeyEvent

from app.player import MPVPlayer


def _event(key, modifiers=Qt.KeyboardModifier.NoModifier):
    return QKeyEvent(QEvent.Type.KeyPress, key, modifiers)


def test_volume_keys_use_the_single_transactional_volume_flow(monkeypatch):
    calls = []
    monkeypatch.setattr("app.player.change_volume",
                        lambda _player, delta: calls.append(delta))
    player = SimpleNamespace()

    MPVPlayer.keyPressEvent(player, _event(Qt.Key.Key_Up))
    MPVPlayer.keyPressEvent(player, _event(Qt.Key.Key_Down))

    assert calls == [5, -5]


def test_modifier_seek_and_playlist_keys_are_not_swallowed(monkeypatch):
    calls = []
    monkeypatch.setattr("app.player.play_next",
                        lambda _player: calls.append(("next", None)))
    monkeypatch.setattr("app.player.seek_relative",
                        lambda _player, value: calls.append(("seek", value)))
    player = SimpleNamespace()

    MPVPlayer.keyPressEvent(
        player, _event(Qt.Key.Key_Right,
                       Qt.KeyboardModifier.ControlModifier))
    MPVPlayer.keyPressEvent(
        player, _event(Qt.Key.Key_Left,
                       Qt.KeyboardModifier.ShiftModifier))

    assert calls == [("next", None), ("seek", -30)]


@pytest.mark.parametrize(("key", "modifiers", "expected"), [
    (Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier, ("play_pause", None)),
    (Qt.Key.Key_O, Qt.KeyboardModifier.ControlModifier, ("open_file", None)),
    (Qt.Key.Key_P, Qt.KeyboardModifier.ControlModifier, ("playlist", None)),
    (Qt.Key.Key_U, Qt.KeyboardModifier.ControlModifier, ("open_url", None)),
    (Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier, ("screenshot", None)),
    (Qt.Key.Key_G, Qt.KeyboardModifier.ControlModifier, ("goto", None)),
    (Qt.Key.Key_Q, Qt.KeyboardModifier.ControlModifier, ("close", None)),
    (Qt.Key.Key_Right, Qt.KeyboardModifier.ControlModifier, ("next", None)),
    (Qt.Key.Key_Left, Qt.KeyboardModifier.ControlModifier, ("previous", None)),
    (Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier, ("seek", 30)),
    (Qt.Key.Key_Left, Qt.KeyboardModifier.ShiftModifier, ("seek", -30)),
    (Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier, ("seek", 5)),
    (Qt.Key.Key_Left, Qt.KeyboardModifier.NoModifier, ("seek", -5)),
    (Qt.Key.Key_M, Qt.KeyboardModifier.NoModifier, ("mute", None)),
    (Qt.Key.Key_F, Qt.KeyboardModifier.NoModifier, ("fullscreen", None)),
    (Qt.Key.Key_S, Qt.KeyboardModifier.NoModifier, ("subtitles", None)),
    (Qt.Key.Key_H, Qt.KeyboardModifier.AltModifier, ("subtitles", None)),
    (Qt.Key.Key_E, Qt.KeyboardModifier.AltModifier, ("open_subtitle", None)),
])
def test_every_documented_shortcut_dispatches_once(
        monkeypatch, key, modifiers, expected):
    calls = []
    targets = {
        "play_pause": "play_pause", "open_file": "open_file",
        "show_playlist": "playlist", "open_url": "open_url",
        "take_screenshot": "screenshot", "goto_time": "goto",
        "play_next": "next", "play_previous": "previous",
        "seek_relative": "seek",
        "toggle_mute": "mute", "toggle_subtitles": "subtitles",
        "open_subtitle": "open_subtitle",
    }
    for function, label in targets.items():
        monkeypatch.setattr(
            f"app.player.{function}",
            lambda _player, *args, label=label:
                calls.append((label, args[0] if args else None)))
    player = SimpleNamespace(
        close=lambda: calls.append(("close", None)),
        toggle_fullscreen=lambda: calls.append(("fullscreen", None)))

    MPVPlayer.keyPressEvent(player, _event(key, modifiers))

    assert calls == [expected]
