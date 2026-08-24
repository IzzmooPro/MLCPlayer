# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Saf fiziksel-buttons onkosul ve bounded modal sozlesmesi."""

BUTTONS_GROUP_TIMEOUT_SECONDS = 180
TIMELINE_GROUP_TIMEOUT_SECONDS = 300
WINDOW_RESIZE_GROUP_TIMEOUT_SECONDS = 180
FULLSCREEN_GROUP_TIMEOUT_SECONDS = 120
MODAL_DISMISS_DELAY_MS = 900


def has_subtitle_track(track_list):
    """MPV track-list icinde gercek bir altyazi parcasi var mi?"""
    return any(isinstance(track, dict) and track.get("type") == "sub"
               for track in (track_list or []))


def playlist_step_available(playlist_size, current_index, delta):
    """Olculebilir onceki/sonraki playlist hedefi var mi?

    Tek ogeli liste yeni dosya/index uretemez ve fiziksel yukleme olcumu
    yapamaz. Loop sinirindaki wrap bu lineer ``index +/-1`` kapisinin konusu
    degildir. Negatif indeks henuz baslatilmamis listeyi temsil eder; bu
    durumda yalnizca ilk ogeye dogru "sonraki" olculebilir.
    """
    try:
        size = int(playlist_size)
        index = int(current_index)
        step = int(delta)
    except (TypeError, ValueError):
        return False
    if size <= 0 or step not in (-1, 1):
        return False
    if index < 0:
        return step > 0
    return 0 <= index + step < size


def arm_modal_dismissal(schedule, dismiss):
    """Nested Qt modalini kisa ve tek bounded callback ile kapat."""
    schedule(MODAL_DISMISS_DELAY_MS, dismiss)
    return MODAL_DISMISS_DELAY_MS
