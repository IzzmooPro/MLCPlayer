# -*- mode: python ; coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only

import os

# The spec lives in packaging/; resolve repository paths from the root.
_project_root = os.path.dirname(os.path.abspath(SPECPATH))

a = Analysis(
    [os.path.join(_project_root, 'app', 'user_cleanup_main.py')],
    pathex=[_project_root], binaries=[], datas=[],
    hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['PyQt6', 'mpv', 'pytest', 'numpy', 'PIL'], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [], name='MLCUserCleanup',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False,
    icon=os.path.join(_project_root, 'assets',
                      'mlc-player-icon-transparent.ico'),
)
