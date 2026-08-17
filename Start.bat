@echo off
rem SPDX-FileCopyrightText: 2026 MLC Player contributors
rem SPDX-License-Identifier: GPL-3.0-only
setlocal
cd /d "%~dp0"

echo ============================================================
echo   MLC Player - automatic launcher
echo ============================================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\bootstrap.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo [ERROR] The player could not be started. Read the explanation above.
    pause
)

exit /b %EXIT_CODE%
