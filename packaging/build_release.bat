@echo off
rem ============================================================
rem  MLC Player - tek tikla surum uretimi
rem
rem  Sirasiyla:
rem    1. On kontrol  (kaynak dosyalar + runtime SHA-256)
rem    2. PyInstaller (onedir  -> dist\MLC Player\)
rem    3. Paket kontrolu (bin/licenses/assets eksiksiz mi)
rem    4. Inno Setup  (-> installer_output\MLCPlayer_Setup_*.exe)
rem    5. Sonuc raporu
rem
rem  Herhangi bir adim basarisiz olursa ZINCIR DURUR ve hatayi yazar.
rem  Elle mudahale gerekmez.
rem ============================================================
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul 2>&1

rem Proje kokune gec (bu dosya packaging\ altinda).
cd /d "%~dp0.."
set "PROJECT=%CD%"
set "SPEC=MLCPlayer.spec"
set "ISS=packaging\MLCPlayer.iss"
set "VERIFY=packaging\verify_build.py"

echo.
echo ============================================================
echo   MLC Player surum uretimi
echo   Proje: %PROJECT%
echo ============================================================
echo.

rem --- Yanlis klasorde calistirmaya karsi guvenlik ---
if not exist "%SPEC%" (
    echo HATA: %SPEC% bulunamadi. Bu betik proje kokunden calismalidir.
    goto :fail
)

rem --- Python ---
where python >nul 2>&1
if errorlevel 1 (
    echo HATA: python PATH'te bulunamadi.
    goto :fail
)

rem --- PyInstaller ---
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo HATA: PyInstaller kurulu degil.  Kurulum: pip install pyinstaller
    goto :fail
)

rem --- Inno Setup derleyicisi (6 veya 7, her iki Program Files konumu) ---
set "ISCC="
for %%P in (
    "%ProgramFiles%\Inno Setup 7\ISCC.exe"
    "%ProgramFiles%\Inno Setup 6\ISCC.exe"
    "%ProgramFiles(x86)%\Inno Setup 7\ISCC.exe"
    "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
) do if not defined ISCC if exist %%P set "ISCC=%%~P"
if not defined ISCC (
    echo HATA: ISCC.exe bulunamadi.  Inno Setup kurulu olmalidir.
    goto :fail
)

echo ADIM 1/7  On kontrol
python "%VERIFY%" --pre
if errorlevel 1 goto :fail
rem Yayimlanabilirlik: kurulu istemcilerin GOREMEYECEGI bir surum uretilmesin
rem (surum karsilastirmasi sayisaldir; v0.31 varken v0.4 gorunmez).
python "packaging\check_publishable.py"
if errorlevel 1 goto :fail
echo.

echo ADIM 2/7  Onceki ciktilarin temizligi
if exist "build" rmdir /s /q "build"
if exist "dist"  rmdir /s /q "dist"
echo   OK  build\ ve dist\ temizlendi
echo.

echo ADIM 3/7  PyInstaller (onedir)  -  birkac dakika surebilir
python -m PyInstaller "%SPEC%" --noconfirm --clean --log-level WARN
if errorlevel 1 (
    echo HATA: PyInstaller basarisiz oldu.
    goto :fail
)
python "%VERIFY%" --post
if errorlevel 1 goto :fail
echo.

echo ADIM 4/7  Inno Setup kurulum dosyasi
echo   Derleyici: %ISCC%
"%ISCC%" /Q "%ISS%"
if errorlevel 1 (
    echo HATA: Inno Setup derlemesi basarisiz oldu.
    goto :fail
)
echo   OK  derleme tamamlandi
echo.

echo ADIM 5/7  Internet Videosu ek paketi
rem yt-dlp + deno ana pakette DEGIL; ayri, istege bagli kurulumla gelir.
for /f "usebackq delims=" %%V in (`python -c "import sys; sys.path.insert(0,'.'); from app.config import APP_VERSION, WINDOWS_VERSION; print(APP_VERSION + '|' + WINDOWS_VERSION)"`) do (
    for /f "tokens=1,2 delims=|" %%A in ("%%V") do (
        set "ADDON_VER=%%A"
        set "ADDON_NUM=%%B"
    )
)
"%ISCC%" /Q /DAddonVersion=!ADDON_VER! /DAddonNumericVersion=!ADDON_NUM! "packaging\MLCPlayer_InternetVideo.iss"
if errorlevel 1 (
    echo HATA: Internet Videosu ek paketi derlenemedi.
    goto :fail
)
echo   OK  ek paket derlendi
echo.

echo ADIM 6/7  Yayinci imzasi
rem UNUTULAMAZ OLMASI ICIN ZINCIRDE: imzasiz yayimlanan bir surumu
rem guncelleyici REDDEDER (fail-closed) ve kullanici sebebini goremez.
set "SETUP_TO_SIGN="
for %%F in ("installer_output\MLCPlayer_Setup_*.exe") do set "SETUP_TO_SIGN=installer_output\%%~nxF"
python "packaging\sign_release.py" "%SETUP_TO_SIGN%"
if errorlevel 1 (
    echo HATA: Kurulum imzalanamadi. Ozel anahtar yoksa once:
    echo        python packaging\sign_release.py --init
    goto :fail
)
rem Ek paket de imzalanir: kullanici onu da GitHub'dan indirir.
set "ADDON_TO_SIGN="
for %%F in ("installer_output\MLCPlayer_InternetVideo_*.exe") do set "ADDON_TO_SIGN=installer_output\%%~nxF"
if defined ADDON_TO_SIGN (
    python "packaging\sign_release.py" "!ADDON_TO_SIGN!"
    if errorlevel 1 goto :fail
)
echo.

echo ADIM 7/7  Sonuc
set "SETUP="
for %%F in ("installer_output\MLCPlayer_Setup_*.exe") do set "SETUP=installer_output\%%~nxF"
if not defined SETUP (
    echo HATA: installer_output icinde kurulum dosyasi yok.
    goto :fail
)
python "%VERIFY%" --final "%SETUP%"
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo   TAMAMLANDI
echo.
echo   Klasor : dist\MLC Player\        (tamamini birlikte tasiyin)
echo   Kurulum: %SETUP%
echo   Imza   : %SETUP%.sig   (release'e MUTLAKA birlikte yuklenir)
echo   Ek paket: !ADDON_TO_SIGN! (+ .sig)  - internet videosu bilesenleri
echo.
echo   Arkadasiniza GONDERECEGINIZ dosya kurulum dosyasidir.
echo ============================================================
echo.
endlocal
exit /b 0

:fail
echo.
echo ============================================================
echo   BASARISIZ - yukaridaki hataya bakin. Cikti uretilmedi.
echo ============================================================
echo.
endlocal
exit /b 1
