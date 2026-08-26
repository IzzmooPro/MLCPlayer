@echo off
rem SPDX-FileCopyrightText: 2026 MLC Player contributors
rem SPDX-License-Identifier: GPL-3.0-only
rem GitHub-hosted MAIN installer build boundary. This deliberately produces
rem one unsigned main installer and never builds the optional internet add-on.
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul 2>&1

if /I not "%MLC_HOSTED_UNSIGNED_BUILD%"=="1" (
    echo ERROR: MLC_HOSTED_UNSIGNED_BUILD=1 is required.
    goto :fail
)

cd /d "%~dp0.."
set "SPEC=MLCPlayer.spec"
set "ISS=packaging\MLCPlayer.iss"
set "VERIFY=packaging\verify_build.py"

if not exist "%SPEC%" (
    echo ERROR: wrong project root.
    goto :fail
)
where python >nul 2>&1
if errorlevel 1 goto :fail
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 goto :fail
python "packaging\verify_dependencies.py" "requirements-lock.txt"
if errorlevel 1 goto :fail

set "ISCC="
for %%P in (
    "%ProgramFiles%\Inno Setup 7\ISCC.exe"
    "%ProgramFiles%\Inno Setup 6\ISCC.exe"
    "%ProgramFiles(x86)%\Inno Setup 7\ISCC.exe"
    "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
) do if not defined ISCC if exist %%P set "ISCC=%%~P"
if not defined ISCC (
    echo ERROR: ISCC.exe not found.
    goto :fail
)

set "APP_VER="
for /f "usebackq delims=" %%V in (`python -c "import sys; sys.path.insert(0,'.'); from app.config import APP_VERSION; print(APP_VERSION)"`) do set "APP_VER=%%V"
if not defined APP_VER goto :fail
set "MAIN_SETUP=installer_output\MLCPlayer_Setup_!APP_VER!.exe"

echo STEP 1/6  Main-package source and runtime verification
python "%VERIFY%" --pre-main
if errorlevel 1 goto :fail

echo STEP 2/6  Clean exact build outputs
if exist "build" (
    rmdir /s /q "build"
    if exist "build" goto :fail
)
if exist "dist" (
    rmdir /s /q "dist"
    if exist "dist" goto :fail
)
if exist "!MAIN_SETUP!" (
    del /f /q "!MAIN_SETUP!"
    if exist "!MAIN_SETUP!" goto :fail
)
if exist "!MAIN_SETUP!.sig" (
    del /f /q "!MAIN_SETUP!.sig"
    if exist "!MAIN_SETUP!.sig" goto :fail
)

echo STEP 3/6  Compile translations
python "packaging\compile_translations.py"
if errorlevel 1 goto :fail

echo STEP 4/6  PyInstaller main package
python "packaging\run_pyinstaller.py" "%SPEC%" --noconfirm --clean --log-level WARN
if errorlevel 1 goto :fail
python "%VERIFY%" --post
if errorlevel 1 goto :fail

echo STEP 5/6  Inno Setup unsigned main installer
"%ISCC%" /Q "%ISS%"
if errorlevel 1 goto :fail
if not exist "!MAIN_SETUP!" goto :fail
if exist "!MAIN_SETUP!.sig" (
    echo ERROR: an unexpected detached signature exists.
    goto :fail
)

echo STEP 6/6  Exact artifact verification
python "%VERIFY%" --final "!MAIN_SETUP!"
if errorlevel 1 goto :fail

echo DONE: !MAIN_SETUP!
endlocal
exit /b 0

:fail
echo FAILED: hosted unsigned main build stopped.
endlocal
exit /b 1
