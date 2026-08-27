# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Bounded cleanup for nested physical-acceptance QMenu event loops.

This helper never selects an action.  Normal cleanup uses the caller's
physical Escape sender.  Direct ``QMenu.close()`` is a last-resort harness
cleanup only and is reported through ``forced=True`` so acceptance fails
closed.
"""
from PyQt6.QtCore import QTimer


def popup_completion_decision(*, pending, timed_out, closed, forced,
                              root_closed):
    """Return the only acceptance decision allowed after popup cleanup.

    Keeping this policy pure makes every fail-closed branch testable without
    a native window.  ``pending`` is ``(kind, reason, checked)`` where kind is
    click, inspect or abort.
    """
    if timed_out:
        return {"reason": "menu_sequence_timeout", "delivered": False,
                "checked": False}
    if forced or not closed:
        return {"reason": "popup_chain_not_closed", "delivered": False,
                "checked": False}
    if not isinstance(pending, tuple) or len(pending) != 3:
        return {"reason": "menu_sequence_incomplete", "delivered": False,
                "checked": False}

    kind, reason, checked = pending
    if kind in ("click", "inspect"):
        if not root_closed:
            return {"reason": "root_popup_not_closed", "delivered": False,
                    "checked": False}
        return {"reason": reason, "delivered": True,
                "checked": bool(checked)}
    if kind == "abort":
        return {"reason": reason, "delivered": False, "checked": False}
    return {"reason": "menu_sequence_incomplete", "delivered": False,
            "checked": False}


class PopupChainWatchdog:
    """Unwind a nested popup chain without trusting an outer polling loop."""

    def __init__(self, *, active_popup, send_escape, close_visible, marker,
                 timeout_ms=4000, escape_interval_ms=90, max_escapes=5):
        self._active_popup = active_popup
        self._send_escape = send_escape
        self._close_visible = close_visible
        self._marker = marker
        self._timeout_ms = int(timeout_ms)
        self._escape_interval_ms = int(escape_interval_ms)
        self._max_escapes = int(max_escapes)
        self._generation = 0
        self._armed = False
        self._completed = False
        self._dismissing = False
        self._popup_seen = False
        self._escape_count = 0
        self._on_timeout = None
        self._on_complete = None

    def arm(self, on_timeout, on_complete):
        """Arm before input which may enter ``QMenu.exec()``."""
        self._generation += 1
        generation = self._generation
        self._armed = True
        self._completed = False
        self._dismissing = False
        self._popup_seen = False
        self._escape_count = 0
        self._on_timeout = on_timeout
        self._on_complete = on_complete
        self._marker("watchdog_armed", timeout_ms=self._timeout_ms)
        QTimer.singleShot(
            self._timeout_ms,
            lambda: self._deadline(generation))

    def note_popup_seen(self):
        self._popup_seen = True

    def dismiss(self, on_complete=None):
        """Begin bounded physical Escape cleanup from inside the nested loop."""
        if on_complete is not None:
            self._on_complete = on_complete
        if not self._armed or self._completed or self._dismissing:
            return
        self._dismissing = True
        self._marker("popup_cleanup_started")
        self._escape_step(self._generation)

    def cancel(self):
        self._generation += 1
        self._armed = False
        self._completed = True

    def _deadline(self, generation):
        if not self._current(generation):
            return
        popup = self._active_popup()
        if self._popup_seen and popup is None:
            self._finish(True, False)
            return
        self._marker("watchdog_timeout", popup_seen=self._popup_seen)
        if self._on_timeout is not None:
            self._on_timeout()
        self.dismiss()

    def _escape_step(self, generation):
        if not self._current(generation):
            return
        if self._active_popup() is None:
            self._finish(True, False)
            return
        if self._escape_count < self._max_escapes:
            self._escape_count += 1
            self._marker("popup_escape_sent", count=self._escape_count)
            self._send_escape()
            QTimer.singleShot(
                self._escape_interval_ms,
                lambda: self._escape_step(generation))
            return

        closed_count = int(self._close_visible() or 0)
        self._marker("popup_cleanup_forced", closed=closed_count)
        QTimer.singleShot(
            self._escape_interval_ms,
            lambda: self._finish(
                self._active_popup() is None, True, generation))

    def _current(self, generation):
        return (self._armed and not self._completed
                and generation == self._generation)

    def _finish(self, closed, forced, generation=None):
        if generation is not None and not self._current(generation):
            return
        if self._completed:
            return
        self._completed = True
        self._armed = False
        self._marker("popup_chain_closed", closed=bool(closed),
                     forced=bool(forced), escapes=self._escape_count)
        if self._on_complete is not None:
            self._on_complete(bool(closed), bool(forced))
