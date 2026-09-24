# -*- mode: python ; coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only

a = Analysis(
    ['user_cleanup_main.py'], pathex=[], binaries=[], datas=[],
    hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['PyQt6', 'mpv', 'pytest', 'numpy', 'PIL'], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [], name='MLCUserCleanup',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, icon='assets/mlc-player-icon-transparent.ico',
)
