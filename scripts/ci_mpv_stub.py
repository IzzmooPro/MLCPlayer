# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Minimal import boundary for hosted tests that deliberately lack libmpv."""

import os
import sys
import types
import importlib.util


def install_ci_mpv_stub():
    existing = sys.modules.get("mpv")
    if os.environ.get("MLC_CI") != "1":
        return existing

    real_spec = importlib.util.find_spec("mpv")
    if real_spec is None or not real_spec.origin:
        raise RuntimeError("python-mpv is missing from the locked CI environment")

    module = types.ModuleType("mpv")
    module.__spec__ = real_spec
    module.__file__ = real_spec.origin
    module.__loader__ = real_spec.loader
    module.MLC_CI_STUB = True

    class ShutdownError(Exception):
        pass

    class MPV:
        """Inert player for UI child processes; it never decodes media."""

        def __init__(self, *_args, **_kwargs):
            self.time_pos = 0.0
            self.track_list = []
            self.chapter_list = []
            self.audio_device_list = []
            self._observers = []

        def observe_property(self, name, callback):
            self._observers.append((name, callback))

        def unobserve_property(self, name, callback):
            pair = (name, callback)
            if pair in self._observers:
                self._observers.remove(pair)

        def seek(self, value, reference="absolute"):
            if reference == "relative":
                self.time_pos += float(value)
            else:
                self.time_pos = float(value)

        def check_core_alive(self):
            return None

        def command(self, *_args):
            return None

        def command_async(self, *_args):
            return None

        def play(self, *_args):
            return None

        def stop(self):
            return None

        def terminate(self):
            return None

        def sub_add(self, *_args, **_kwargs):
            return None

        def screenshot_to_file(self, *_args, **_kwargs):
            return None

    module.ShutdownError = ShutdownError
    module.MPV = MPV
    sys.modules["mpv"] = module
    return module
