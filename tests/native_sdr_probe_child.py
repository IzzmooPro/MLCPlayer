# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Tek exact fixture icin opt-in gercek Windows/libmpv SDR child'i."""
import ctypes
import faulthandler
import json
import os
import sys
import time


if os.environ.get("MLC_NATIVE_SDR_ACCEPTANCE") != "1":
    print("SKIPPED: OPT_IN_REQUIRED", flush=True)
    raise SystemExit(0)

faulthandler.enable(file=sys.stderr, all_threads=True)
PROJECT_ROOT = os.environ.get(
    "MLC_NATIVE_PROJECT_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["PATH"] = os.path.join(PROJECT_ROOT, "bin") + os.pathsep + os.environ["PATH"]
os.environ.pop("QT_QPA_PLATFORM", None)

from native_media_contract import is_supported_media  # noqa: E402
from sdr_probe_contract import (PROFILES, classify_sdr_input,  # noqa: E402
                                sdr_probe_config)


VIDEO = os.environ.get("MLC_SDR_TEST_VIDEO", "")
PROFILE = os.environ.get("MLC_SDR_PROBE_PROFILE", "")
if not is_supported_media(VIDEO) or PROFILE not in PROFILES:
    print("HARNESS_FAILURE invalid SDR media or profile", flush=True)
    raise SystemExit(2)

from PyQt6.QtCore import QSettings, QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402
import app.player as player_module  # noqa: E402


player_module.MPV_CONFIG = sdr_probe_config(player_module.MPV_CONFIG, PROFILE)
MPVPlayer = player_module.MPVPlayer


START = time.time()
CALLS = []


class CursorPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def get_cursor_position():
    point = CursorPoint()
    if not ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
        return None
    return point.x, point.y


def restore_cursor_position(position):
    if position is None:
        return False
    if not ctypes.windll.user32.SetCursorPos(*position):
        return False
    return get_cursor_position() == position


def mark(name, detail=""):
    print(f"{name} t={time.time() - START:.2f} {detail}".rstrip(), flush=True)


def install_call_recorder():
    import mpv as mpv_module

    real_stop = mpv_module.MPV.stop
    real_terminate = mpv_module.MPV.terminate

    def recording_stop(self, *args, **kwargs):
        CALLS.append("stop")
        mark("MARK_STOP_CALLED", f"count={CALLS.count('stop')}")
        return real_stop(self, *args, **kwargs)

    def recording_terminate(self, *args, **kwargs):
        CALLS.append("terminate")
        mark("MARK_TERMINATE_CALLED", f"count={CALLS.count('terminate')}")
        return real_terminate(self, *args, **kwargs)

    mpv_module.MPV.stop = recording_stop
    mpv_module.MPV.terminate = recording_terminate


def get_property(mpv_player, name, default=None):
    try:
        value = mpv_player._get_property(name)
    except Exception:
        return default
    return default if value is None else value


def main():
    settings = os.environ.get("MLC_NATIVE_SETTINGS", "")
    if not settings or not os.path.isabs(settings):
        print("HARNESS_FAILURE absolute isolated settings path required", flush=True)
        return 2
    os.makedirs(settings, exist_ok=True)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      settings)

    initial_cursor = get_cursor_position()
    install_call_recorder()
    app = QApplication([sys.argv[0]])
    player = MPVPlayer()
    player.resize(1280, 720)
    player.show()
    app.processEvents()
    mark("MARK_PLAYER_CREATED", f"profile={PROFILE}")

    state = {
        "deadline": time.time() + 20,
        "captured": False,
        "input": {},
        "target": {},
        "duration": 0.0,
        "max_time_pos": 0.0,
        "frame_drops": {},
        "closed": False,
        "close_accepted": False,
    }

    def close_player():
        if state["closed"]:
            return
        state["closed"] = True
        mark("MARK_CLOSE_REQUESTED")
        accepted = bool(player.close())
        state["close_accepted"] = accepted
        mark("MARK_CLOSE_ACCEPTED", f"accepted={accepted} visible={player.isVisible()}")
        QTimer.singleShot(0, app.quit)

    def poll():
        mpv_player = getattr(player, "mpv_player", None)
        if mpv_player is None:
            timer.stop()
            close_player()
            return
        params = get_property(mpv_player, "video-params", {}) or {}
        target = get_property(mpv_player, "video-target-params", {}) or {}
        duration = float(getattr(mpv_player, "duration", 0) or 0)
        position = float(getattr(mpv_player, "time_pos", 0) or 0)
        state["max_time_pos"] = max(state["max_time_pos"], position)
        if duration > 0:
            state["duration"] = duration
        if params:
            state["input"] = params
        if target:
            state["target"] = target
        if (state["duration"] > 0 and state["max_time_pos"] > 0.5
                and state["input"] and state["target"]):
            state["captured"] = True
            state["frame_drops"] = {
                name: get_property(mpv_player, name)
                for name in ("decoder-frame-drop-count", "frame-drop-count")
            }
            mark("MARK_SDR_PROPERTIES",
                 f"input={classify_sdr_input(state['input'])} "
                 f"duration={state['duration']:.3f} "
                 f"time_pos={state['max_time_pos']:.3f} "
                 f"drops={state['frame_drops']}")
            timer.stop()
            QTimer.singleShot(250, close_player)
            return
        if time.time() >= state["deadline"]:
            timer.stop()
            mark("MARK_SDR_PROPERTIES", "TIMEOUT")
            close_player()

    player.open_path(VIDEO)
    mark("MARK_MEDIA_OPEN_REQUESTED")
    timer = QTimer()
    timer.timeout.connect(poll)
    timer.start(100)
    exec_code = app.exec()
    mark("MARK_APP_EXEC_RETURNED", f"code={exec_code}")
    cursor_restored = restore_cursor_position(initial_cursor)
    mark("MARK_CURSOR_RESTORED", f"restored={cursor_restored}")

    report = {
        "profile": PROFILE,
        "input_class": classify_sdr_input(state["input"]),
        "input": state["input"],
        "target": state["target"],
        "duration": state["duration"],
        "max_time_pos": state["max_time_pos"],
        "frame_drops": state["frame_drops"],
        "stop_calls": CALLS.count("stop"),
        "terminate_calls": CALLS.count("terminate"),
        "call_order": list(CALLS),
        "close_accepted": state["close_accepted"],
        "cursor_restored": cursor_restored,
        "captured": state["captured"],
    }
    exit_code = 0 if (state["captured"] and exec_code == 0) else 1
    print("SDR_REPORT_JSON=" + json.dumps(
        report, ensure_ascii=True, sort_keys=True), flush=True)
    mark("MARK_DONE", f"profile={PROFILE} code={exit_code}")
    return exit_code


if __name__ == "__main__":
    exit_code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code)
