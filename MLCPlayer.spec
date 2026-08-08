# PyInstaller spec dosyası - MLC Player
# Kullanım: pyinstaller MLCPlayer.spec
# Not: python-mpv mpv-2.dll'i dışarıdan yükler (add_dll_directory ile),
# bu yüzden DLL'i datalar ile birlikte paketlemek yeterlidir.

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('bin/mpv-2.dll', 'bin'),          # mpv + ffmpeg runtime DLL
        ('bin/libmpv.dll.a', 'bin'),       # yedek statik kütüphane (opsiyonel)
    ],
    hiddenimports=[
        'mpv',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest', 'tkinter'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MLC Player',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                # GUI uygulaması - konsol penceresi açmasın
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
