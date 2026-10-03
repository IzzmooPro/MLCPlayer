# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Doğal bitişte sıradaki öğe yüklenemezse hata BİR KEZ gösterilmeli.

`handle_natural_end()` 100 ms'lik `update_ui` timer'ından çağrılır.
`play_from_playlist()` başarısız yüklemede durumu (sonda, çekirdek boşta)
geri alır ve SONRA modal hata penceresini açar; modal döngüde timer
çalışmaya devam ettiği için her tik aynı yüklemeyi yeniden deneyip yeni
bir pencere açıyordu.
"""

from types import SimpleNamespace

from app import media_controls


def _player():
    def command_async(*args):
        if args and args[0] == "loadfile":
            raise RuntimeError("load rejected")

    return SimpleNamespace(
        playlist=["a.mkv", "b.mkv"], current_playlist_index=0,
        current_file="a.mkv", duration=100.0, position=100.0,
        _core_idle=True, _eof_rewound=False, loop_file=False,
        loop_playlist=False, shuffle=False, is_paused=False,
        settings=None, title_bar=None, play_icon="play", pause_icon="pause",
        play_button=SimpleNamespace(setIcon=lambda _i: None),
        video_frame=SimpleNamespace(control_overlay=None),
        mpv_player=SimpleNamespace(command_async=command_async, pause=False,
                                   sub_delay=0.0, sub_visibility=False),
        set_title=lambda: None)


def test_failed_next_item_shows_one_error_and_rewinds(monkeypatch):
    player = _player()
    shown = []

    def modal_error(*_args, **_kwargs):
        shown.append(True)
        if len(shown) < 5:
            # Modal döngü içindeki timer tikini taklit eder.
            media_controls.handle_natural_end(player)

    monkeypatch.setattr(media_controls, "show_user_error", modal_error)

    media_controls.handle_natural_end(player)

    assert len(shown) == 1
    # Sıradaki yüklenemedi: mevcut öğe başa sarılıp duraklatılır.
    assert player._eof_rewound is True
    assert player.is_paused is True
    assert player.current_playlist_index == 0
