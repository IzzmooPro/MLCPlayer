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
        # Calisma zamani ikilileri `_internal\bin` altinda toplanir.
        ('bin/mpv-2.dll', 'bin'),                  # mpv + ffmpeg runtime DLL
        ('bin/yt-dlp.exe', 'bin'),                 # resmi site cikarimi
        ('bin/deno.exe', 'bin'),                   # resmi JS calisma zamani
        # Resmi lisans metinleri `_internal\licenses` altinda tasinir.
        ('licenses/yt-dlp-LICENSE.txt', 'licenses'),
        ('licenses/yt-dlp-THIRD_PARTY_LICENSES.txt', 'licenses'),
        ('licenses/deno-LICENSE.txt', 'licenses'),
        # Qt calisma zamani ikonu `_internal\assets` altindan okunur.
        ('assets/mlc-player-icon.ico', 'assets'),
    ],
    hiddenimports=[
        'mpv',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # URUNDE HIC KULLANILMAYAN paketler (kaynak taramasiyla dogrulandi):
    # `numpy` ve `PIL` app/ ve main.py icinde import EDILMIYOR; PyInstaller
    # onlari gecisli olarak topluyordu (~38 MB).
    excludes=['pytest', 'tkinter', 'numpy', 'PIL', 'Pillow',
              'scipy', 'matplotlib'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# --- Kullanilmayan Qt bilesenlerini paketten cikar ---------------------
# `opengl32sw.dll`: Qt'nin YAZILIMSAL OpenGL yedegi (~20 MB). Arayuz saf
# QtWidgets (raster) oldugu icin gerekmiyor; video ise mpv `vo=gpu` ile
# ciziliyor ve bu DLL'i kullanmiyor. OpenGL'in calismadigi ortamda (RDP,
# surucusuz kurulum) video zaten acilmaz.
# `Qt6Pdf.dll` (~5 MB) ve Qt cevirileri (~6,6 MB): urunde kullanilmiyor.
_DROP_BINARIES = ('opengl32sw.dll', 'qt6pdf.dll')


def _keep_binary(entry):
    name = entry[0].replace(chr(92), '/').rsplit('/', 1)[-1].lower()
    return name not in _DROP_BINARIES


def _keep_data(entry):
    path = entry[0].replace(chr(92), '/').lower()
    return '/qt6/translations/' not in f'/{path}'


a.binaries = [entry for entry in a.binaries if _keep_binary(entry)]
a.datas = [entry for entry in a.datas if _keep_data(entry)]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ONEDIR: `exclude_binaries=True` + `COLLECT`. `onefile` KULLANILMAZ.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MLC Player',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX bu turda ZORLA acilmaz; karar gercek antivirus/baslatma
    # kabulunden sonra verilir (bkz. docs/PACKAGING_PLAN.md).
    upx=False,
    upx_exclude=[],
    # Destek dosyalari klasoru ACIKCA sabitlenir; PyInstaller surum
    # varsayimina birakilmaz.
    contents_directory='_internal',
    icon='assets/mlc-player-icon.ico',
    console=False,                # GUI uygulaması - konsol penceresi açmasın
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='MLC Player',
)
