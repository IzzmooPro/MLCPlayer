@echo off
rem SPDX-FileCopyrightText: 2026 MLC Player contributors
rem SPDX-License-Identifier: GPL-3.0-only
rem ============================================================
rem  MLC Player - one-click release build
rem
rem  In order:
rem    1. Pre-flight check (source files + runtime SHA-256)
rem    2. Translation compile (.ts -> .qm)
rem    3. PyInstaller (onedir -> dist\MLC Player\)
rem    4. Package check (are bin/licenses/assets complete)
rem    5. Inno Setup (-> installer_output\MLCPlayer_Setup_*.exe)
rem    6. Publisher signature
rem    7. Result report
rem
rem  If any step fails the CHAIN STOPS and prints the error. No manual
rem  intervention is needed.
rem ============================================================
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul 2>&1

rem Move to the project root (this file lives under packaging\).
cd /d "%~dp0.."
set "PROJECT=%CD%"
set "SPEC=MLCPlayer.spec"
set "ISS=packaging\MLCPlayer.iss"
set "VERIFY=packaging\verify_build.py"

echo.
echo ============================================================
echo   MLC Player release build
echo   Project: %PROJECT%
echo ============================================================
echo.

rem --- Guard against being run from the wrong folder ---
if not exist "%SPEC%" (
    echo ERROR: %SPEC% not found. This script must run from the project root.
    goto :fail
)

rem --- Python ---
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: python was not found on PATH.
    goto :fail
)

rem --- PyInstaller ---
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: PyInstaller is not installed.  Install it with: pip install pyinstaller
    goto :fail
)

rem --- Inno Setup compiler (6 or 7, both Program Files locations) ---
set "ISCC="
for %%P in (
    "%ProgramFiles%\Inno Setup 7\ISCC.exe"
    "%ProgramFiles%\Inno Setup 6\ISCC.exe"
    "%ProgramFiles(x86)%\Inno Setup 7\ISCC.exe"
    "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
) do if not defined ISCC if exist %%P set "ISCC=%%~P"
if not defined ISCC (
    echo ERROR: ISCC.exe not found.  Inno Setup must be installed.
    goto :fail
)

echo STEP 1/8  Pre-flight check
python "%VERIFY%" --pre
if errorlevel 1 goto :fail
rem Publishability: do not produce a version installed clients CANNOT SEE
rem (the comparison is numeric; with v0.31 out, v0.4 is invisible).
python "packaging\check_publishable.py"
if errorlevel 1 goto :fail
echo.

echo STEP 2/8  Cleaning previous output
if exist "build" rmdir /s /q "build"
if exist "dist"  rmdir /s /q "dist"
echo   OK  build\ and dist\ cleaned
echo.

echo STEP 3/8  Compiling translations (.ts -^> .qm)
rem `.qm` files are build output and are NOT kept in the repository;
rem MLCPlayer.spec collects them from translations\. Without this step a
rem clean checkout produces a package with NO translations and the user
rem silently gets Turkish only.
python "packaging\compile_translations.py"
if errorlevel 1 goto :fail
echo.

echo STEP 4/8  PyInstaller (onedir)  -  this can take a few minutes
python -m PyInstaller "%SPEC%" --noconfirm --clean --log-level WARN
if errorlevel 1 (
    echo ERROR: PyInstaller failed.
    goto :fail
)
python "%VERIFY%" --post
if errorlevel 1 goto :fail
echo.

echo STEP 5/8  Inno Setup installer
echo   Compiler: %ISCC%
"%ISCC%" /Q "%ISS%"
if errorlevel 1 (
    echo ERROR: the Inno Setup build failed.
    goto :fail
)
echo   OK  build finished
echo.

echo STEP 6/8  Internet Video add-on
rem yt-dlp + deno are NOT in the main package; they ship as a separate,
rem optional install.
for /f "usebackq delims=" %%V in (`python -c "import sys; sys.path.insert(0,'.'); from app.config import APP_VERSION, WINDOWS_VERSION; print(APP_VERSION + '|' + WINDOWS_VERSION)"`) do (
    for /f "tokens=1,2 delims=|" %%A in ("%%V") do (
        set "ADDON_VER=%%A"
        set "ADDON_NUM=%%B"
    )
)
"%ISCC%" /Q /DAddonVersion=!ADDON_VER! /DAddonNumericVersion=!ADDON_NUM! "packaging\MLCPlayer_InternetVideo.iss"
if errorlevel 1 (
    echo ERROR: the Internet Video add-on could not be built.
    goto :fail
)
echo   OK  add-on built
echo.

echo STEP 7/8  Publisher signature
rem IN THE CHAIN SO IT CANNOT BE FORGOTTEN: the updater REJECTS an
rem unsigned release (fail-closed) and the user cannot see why.
set "SETUP_TO_SIGN="
for %%F in ("installer_output\MLCPlayer_Setup_*.exe") do set "SETUP_TO_SIGN=installer_output\%%~nxF"
python "packaging\sign_release.py" "%SETUP_TO_SIGN%"
if errorlevel 1 (
    echo ERROR: the installer could not be signed. Without a private key,
    echo        run first: python packaging\sign_release.py --init
    goto :fail
)
rem The add-on is signed too: the user downloads it from GitHub as well.
set "ADDON_TO_SIGN="
for %%F in ("installer_output\MLCPlayer_InternetVideo_*.exe") do set "ADDON_TO_SIGN=installer_output\%%~nxF"
if defined ADDON_TO_SIGN (
    python "packaging\sign_release.py" "!ADDON_TO_SIGN!"
    if errorlevel 1 goto :fail
)
echo.

echo STEP 8/8  Result
set "SETUP="
for %%F in ("installer_output\MLCPlayer_Setup_*.exe") do set "SETUP=installer_output\%%~nxF"
if not defined SETUP (
    echo ERROR: no installer found in installer_output.
    goto :fail
)
python "%VERIFY%" --final "%SETUP%"
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo   DONE
echo.
echo   Folder   : dist\MLC Player\      (move the whole folder together)
echo   Installer: %SETUP%
echo   Signature: %SETUP%.sig   (MUST be uploaded to the release with it)
echo   Add-on   : !ADDON_TO_SIGN! (+ .sig)  - internet video components
echo.
echo   The file you SEND to someone else is the installer.
echo ============================================================
echo.
endlocal
exit /b 0

:fail
echo.
echo ============================================================
echo   FAILED - see the error above. No output was produced.
echo ============================================================
echo.
endlocal
exit /b 1
