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
rem    5. Inno Setup (-> installer_output\MLCPlayer_Setup_<APP_VERSION>.exe)
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
set "DEPENDENCY_VERIFY=packaging\verify_dependencies.py"
set "DEPENDENCY_LOCK=requirements-lock.txt"

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

rem --- Deterministic dependency gate (before any output is removed) ---
python "%DEPENDENCY_VERIFY%" "%DEPENDENCY_LOCK%"
if errorlevel 1 (
    echo ERROR: Install the locked build environment with:
    echo        python -m pip install -r %DEPENDENCY_LOCK%
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

rem --- Version: read ONCE, up front -------------------------------
rem MEASURED RISK: installer_output holds every build from v0.1 to v0.36
rem side by side. The chain used to pick the file to sign with a wildcard
rem (`MLCPlayer_Setup_*.exe`); `for` walks the matches and the LAST one
rem wins, and that order comes from the filesystem. The sharp failure is
rem not ordering though: if Inno does not produce the new EXE, a wildcard
rem quietly selects an OLD one, signs it, and reports it as the new
rem release. Every artifact path below is EXACT.
set "APP_VER="
set "APP_NUM="
for /f "usebackq delims=" %%V in (`python -c "import sys; sys.path.insert(0,'.'); from app.config import APP_VERSION, WINDOWS_VERSION; print(APP_VERSION + '|' + WINDOWS_VERSION)"`) do (
    for /f "tokens=1,2 delims=|" %%A in ("%%V") do (
        set "APP_VER=%%A"
        set "APP_NUM=%%B"
    )
)
if not defined APP_VER (
    echo ERROR: APP_VERSION could not be read from app\config.py.
    goto :fail
)
if not defined APP_NUM (
    echo ERROR: WINDOWS_VERSION could not be read from app\config.py.
    goto :fail
)
set "MAIN_SETUP=installer_output\MLCPlayer_Setup_!APP_VER!.exe"
set "ADDON_SETUP=installer_output\MLCPlayer_InternetVideo_!APP_VER!.exe"
echo   Version  : !APP_VER!  (!APP_NUM!)
echo   Installer: !MAIN_SETUP!
echo   Add-on   : !ADDON_SETUP!
echo.

echo STEP 1/8  Pre-flight check
python "%VERIFY%" --pre
if errorlevel 1 goto :fail
rem Publishability: do not produce a version installed clients CANNOT SEE
rem (the comparison is numeric; with v0.31 out, v0.4 is invisible).
python "packaging\check_publishable.py"
if errorlevel 1 goto :fail
python "packaging\verify_inno.py" all --iscc "%ISCC%"
if errorlevel 1 goto :fail
echo.

echo STEP 2/8  Cleaning previous output
rem MEASURED GAP: `rmdir /s /q` can fail silently -- a locked file, an
rem open Explorer window or a permission problem leaves the tree in
rem place. The result was never checked, so the chain could carry on with
rem LAST RUN's build\ and dist\ and what looked like fresh PyInstaller
rem output could be a leftover. Each removal is now verified.
if exist "build" (
    rmdir /s /q "build"
    if exist "build" (
        echo ERROR: the stale build\ tree could not be removed.
        echo        Close anything holding it open and run again.
        goto :fail
    )
)
if exist "dist" (
    rmdir /s /q "dist"
    if exist "dist" (
        echo ERROR: the stale dist\ tree could not be removed.
        echo        Close anything holding it open and run again.
        goto :fail
    )
)
rem ONLY this version's four exact outputs. Older releases in
rem installer_output are KEPT: they are the artifacts already published,
rem and a broad `del *.exe` would destroy them. A stale file that cannot
rem be removed STOPS the chain -- otherwise the next steps could not tell
rem a fresh build from last run's leftover.
for %%T in ("!MAIN_SETUP!" "!MAIN_SETUP!.sig" "!ADDON_SETUP!" "!ADDON_SETUP!.sig") do (
    if exist "%%~T" (
        del /f /q "%%~T"
        if exist "%%~T" (
            echo ERROR: the stale output could not be removed: %%~T
            goto :fail
        )
    )
)
echo   OK  build\ and dist\ cleaned, this version's outputs removed
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
python "packaging\run_pyinstaller.py" "%SPEC%" --noconfirm --clean --log-level WARN
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
rem The EXACT file must exist. Without this a silent Inno failure left the
rem old installer in place and the wildcard signed THAT.
if not exist "!MAIN_SETUP!" (
    echo ERROR: the expected installer was not produced: !MAIN_SETUP!
    goto :fail
)
echo   OK  build finished  ^(!MAIN_SETUP!^)
echo.

echo STEP 6/8  Internet Video add-on
rem yt-dlp + deno are NOT in the main package; they ship as a separate,
rem optional install.
rem The version was read ONCE at the top; it is NOT read again here.
"%ISCC%" /Q /DAddonVersion=!APP_VER! /DAddonNumericVersion=!APP_NUM! "packaging\MLCPlayer_InternetVideo.iss"
if errorlevel 1 (
    echo ERROR: the Internet Video add-on could not be built.
    goto :fail
)
rem The add-on is MANDATORY. It used to be signed only `if defined`, so a
rem missing add-on was skipped in silence and the release went out without
rem it.
if not exist "!ADDON_SETUP!" (
    echo ERROR: the expected add-on was not produced: !ADDON_SETUP!
    goto :fail
)
echo   OK  add-on built  ^(!ADDON_SETUP!^)
echo.

echo STEP 7/8  Publisher signature
rem IN THE CHAIN SO IT CANNOT BE FORGOTTEN: the updater REJECTS an
rem unsigned release (fail-closed) and the user cannot see why.
python "packaging\sign_release.py" "!MAIN_SETUP!"
if errorlevel 1 (
    echo ERROR: the installer could not be signed. Without a private key,
    echo        run first: python packaging\sign_release.py --init
    goto :fail
)
rem The add-on is signed too: the user downloads it from GitHub as well.
python "packaging\sign_release.py" "!ADDON_SETUP!"
if errorlevel 1 goto :fail
echo.

echo STEP 8/8  Result
python "%VERIFY%" --final "!MAIN_SETUP!"
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo   DONE
echo.
echo   Folder   : dist\MLC Player\      (move the whole folder together)
echo   Installer: !MAIN_SETUP!
echo   Signature: !MAIN_SETUP!.sig   (MUST be uploaded to the release with it)
echo   Add-on   : !ADDON_SETUP! (+ .sig)  - internet video components
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
