# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
# PyInstaller spec dosyası - MLC Player
# Kullanım: pyinstaller MLCPlayer.spec
# Not: python-mpv mpv-2.dll'i dışarıdan yükler (add_dll_directory ile),
# bu yüzden DLL'i datalar ile birlikte paketlemek yeterlidir.

import importlib.util
import os
import sys

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# Windows sürüm kaynağı (VS_VERSION_INFO). Olmadığında Windows "Birlikte aç"
# listesinde programı DOSYA ADIYLA ("MLC Player.exe") gösteriyordu.
# Değerler app/config.py'deki tek sürüm kaynağından türer.
_project_root = os.path.abspath(os.getcwd())
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
from app.config import APP_VERSION, WINDOWS_VERSION      # noqa: E402

# `packaging` adı kurulu bir dağıtımla çakıştığı için yol üzerinden yüklenir.
_resource_spec = importlib.util.spec_from_file_location(
    'mlc_version_resource',
    os.path.join(_project_root, 'packaging', 'version_resource.py'))
version_resource = importlib.util.module_from_spec(_resource_spec)
_resource_spec.loader.exec_module(version_resource)

VERSION_FILE = os.path.join(_project_root, 'build', 'file_version_info.txt')
os.makedirs(os.path.dirname(VERSION_FILE), exist_ok=True)
version_resource.write(VERSION_FILE, APP_VERSION, WINDOWS_VERSION)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Calisma zamani ikilileri `_internal\bin` altinda toplanir.
        ('bin/mpv-2.dll', 'bin'),                  # mpv + ffmpeg runtime DLL
        # yt-dlp.exe ve deno.exe BILEREK YOK: birlikte 110 MB tutuyorlar
        # ve yalniz URL'den oynatmada gerekiyorlar. Ayri "Internet Videosu"
        # ek paketiyle dagitilirlar (packaging/MLCPlayer_InternetVideo.iss).
        # Urun eksikligi zaten guvenli bicimde ele aliyor
        # (app/runtime_binaries.py).
        # Resmi lisans metinleri `_internal\licenses` altinda tasinir.
        # Lisans metinleri ilgili ikililerle BIRLIKTE dagitilir: yt-dlp ve
        # deno ek pakette oldugu icin lisanslari da ORADA. mpv ise BU
        # pakette, bu yuzden kunyesi ve provenance manifesti burada.
        # GPLv3 karsilik gelen kaynak yukumlulugu icin kullaniciya
        # gosterilen tek yer depo olmamalidir; kurulu programin yaninda da
        # durur (tests/test_third_party_notice_regressions.py).
        ('licenses/mpv-NOTICE.txt', 'licenses'),
        # Kurulu paketin ucuncu taraf bildirimleri ve Qt'nin LGPLv3
        # degistirme yolu. Qt DLL'leri dinamik oldugu icin ayri uygulama
        # object dosyalari yerine kesin DLL/plugin yolu ve kaynaklar verilir.
        ('licenses/THIRD_PARTY_NOTICES.txt', 'licenses'),
        ('licenses/Qt-LGPL-3.0.txt', 'licenses'),
        ('licenses/Qt-RELINKING.txt', 'licenses'),
        ('licenses/Python-LICENSE.txt', 'licenses'),
        ('licenses/PyQt6_sip-LICENSE.txt', 'licenses'),
        ('licenses/cffi-LICENSE.txt', 'licenses'),
        ('licenses/cryptography-LICENSE.txt', 'licenses'),
        ('licenses/OpenSSL-LICENSE.txt', 'licenses'),
        ('licenses/pycparser-LICENSE.txt', 'licenses'),
        ('licenses/python-mpv-LICENSE-GPL.txt', 'licenses'),
        ('licenses/python-mpv-LICENSE-LGPL.txt', 'licenses'),
        ('bin/RUNTIME_MANIFEST.txt', 'bin'),
        # Qt calisma zamani ikonu `_internal\assets` altindan okunur.
        ('assets/mlc-player-icon.ico', 'assets'),
        ('assets/mlc-player-icon-transparent.ico', 'assets'),
        # MLC Player GPLv3'tur; lisans metni dagitima ESLIK ETMELIDIR.
        # `dist` agacinin kendisi de dagitilabilir bir bicimdir, bu yuzden
        # yalniz installer'a birakilmaz. Setup ayrica kok dizine kopyalar
        # ve kurulum ekraninda gosterir (bkz. packaging/MLCPlayer.iss).
        ('LICENSE', '.'),
        # Derlenmis ceviriler; kaynak `.ts` dosyalari PAKETE GIRMEZ.
        *[(f'translations/{name}', 'translations')
          for name in sorted(os.listdir(os.path.join(_project_root,
                                                     'translations')))
          if name.endswith('.qm')],
        ('README.md', '.'),
        ('README.tr.md', '.'),
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
    # `PySide6` YALNIZ gelistirici aracidir (ceviri derleyicisi ve
    # Linguist). Urun PyQt6 ile calisir; ikinci bir Qt baglamasi
    # pakete GIRMEZ (tests/test_developer_dependency_regressions.py).
    excludes=['pytest', 'setuptools', 'tkinter', 'numpy', 'PIL', 'Pillow',
              'scipy', 'matplotlib', 'PySide6', 'shiboken6'],
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
    icon='assets/mlc-player-icon-transparent.ico',
    # Windows'un gösterdiği ad ve sürüm alanları buradan gelir.
    version=VERSION_FILE,
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
