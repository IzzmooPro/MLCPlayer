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

    class ShutdownError(Exception):
        pass

    class MPV:
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError(
                "native libmpv is disabled in hosted CI; use a test double")

    module.ShutdownError = ShutdownError
    module.MPV = MPV
    sys.modules["mpv"] = module
    return module
