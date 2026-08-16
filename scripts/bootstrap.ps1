# MLC Player - otomatik baslatma bootstrap'i.
#
# Amac: format sonrasi bos bir Windows'ta Baslat.bat'a cift tiklayinca
# program acilsin. Python varsa KURULMAZ, yalnizca dogrulanir; paketler
# zaten kuruluysa pip CALISTIRILMAZ. Yani ikinci acilis hizlidir.
#
# -CheckOnly: her seyi dogrular ama programi BASLATMAZ (tanilama icin).

param(
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
$MinimumPython = [Version]"3.12"
$Python = $null

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$MainFile = Join-Path $ProjectRoot "main.py"
$Requirements = Join-Path $ProjectRoot "requirements.txt"

# Urunun calisma zamani ikilileri depoda tasinir; pip ile gelmezler.
$RequiredBinaries = @("mpv-2.dll", "yt-dlp.exe", "deno.exe")

# Import adi <-> pip paketi. Kontrol import adiyla yapilir, cunku
# python-mpv paketinin modul adi "mpv"dir.
$RequiredModules = @("PyQt6", "mpv")

function Install-PythonFromOfficialSite {
    Write-Host "[BILGI] Python resmi sitesinden indiriliyor..."
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

    $index = Invoke-WebRequest -UseBasicParsing -Uri "https://www.python.org/ftp/python/"
    $versions = [regex]::Matches($index.Content, 'href="(3\.13\.\d+)/"') |
        ForEach-Object { [Version]$_.Groups[1].Value } |
        Sort-Object -Descending -Unique
    $latest = $versions | Select-Object -First 1
    if ($null -eq $latest) {
        throw "Python 3.13 indirme surumu resmi sitede belirlenemedi."
    }

    $versionText = $latest.ToString()
    $installer = Join-Path $env:TEMP "python-$versionText-amd64.exe"
    $downloadUrl = "https://www.python.org/ftp/python/$versionText/python-$versionText-amd64.exe"

    try {
        Invoke-WebRequest -UseBasicParsing -Uri $downloadUrl -OutFile $installer
        $process = Start-Process -FilePath $installer -Wait -PassThru -ArgumentList @(
            "/quiet",
            "InstallAllUsers=0",
            "PrependPath=1",
            "Include_launcher=1",
            "Include_pip=1"
        )
        if ($process.ExitCode -ne 0) {
            throw "Python resmi kurucusu hata verdi (cikis kodu: $($process.ExitCode))."
        }
    }
    finally {
        Remove-Item -LiteralPath $installer -Force -ErrorAction SilentlyContinue
    }
}

function Test-PythonCommand {
    param(
        [string]$Executable,
        [string[]]$PrefixArgs = @()
    )

    try {
        $versionText = & $Executable @PrefixArgs -c "import sys; print('.'.join(map(str, sys.version_info[:3])))" 2>$null
        if ($LASTEXITCODE -ne 0) { return $null }
        if ([Version]$versionText -lt $MinimumPython) { return $null }
        return [PSCustomObject]@{
            Executable = $Executable
            PrefixArgs = $PrefixArgs
            Version = $versionText
        }
    }
    catch {
        return $null
    }
}

function Test-ModulesInstalled {
    # Paketler kurulu mu? Kurulu ise pip'e HIC dokunulmaz.
    #
    # Modul ICE AKTARILMAZ, yalnizca bulunur: `import mpv` calisma aninda
    # libmpv DLL'ini yuklemeye calisir ve bin/ PATH'te olmadigi icin
    # basarisiz olurdu -> her acilista bosuna pip calisirdi.
    $names = ($RequiredModules | ForEach-Object { "'$_'" }) -join ","
    $probe = "import importlib.util as u,sys; sys.exit(1 if any(u.find_spec(m) is None for m in ($names,)) else 0)"
    & $Python.Executable @($Python.PrefixArgs) -c $probe
    return ($LASTEXITCODE -eq 0)
}

# --- 1) Python ------------------------------------------------------------

$Candidates = @(
    [PSCustomObject]@{ Executable = "py"; PrefixArgs = @("-3.14") }
    [PSCustomObject]@{ Executable = "py"; PrefixArgs = @("-3.13") }
    [PSCustomObject]@{ Executable = "py"; PrefixArgs = @("-3.12") }
    [PSCustomObject]@{ Executable = "python"; PrefixArgs = @() }
    [PSCustomObject]@{ Executable = "python3"; PrefixArgs = @() }
)

foreach ($candidate in $Candidates) {
    $Python = Test-PythonCommand -Executable $candidate.Executable -PrefixArgs $candidate.PrefixArgs
    if ($null -ne $Python) { break }
}

if ($null -eq $Python) {
    Write-Host "[BILGI] Python 3.12+ bulunamadi. Python 3.13 kuruluyor..."
    $installedWithWinget = $false
    if ($null -ne (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
        & winget.exe install --id Python.Python.3.13 --exact --scope user --accept-package-agreements --accept-source-agreements
        $installedWithWinget = ($LASTEXITCODE -eq 0)
    }
    if (-not $installedWithWinget) {
        Install-PythonFromOfficialSite
    }

    $PostInstallCandidates = @(
        [PSCustomObject]@{ Executable = "py"; PrefixArgs = @("-3.13") }
        [PSCustomObject]@{ Executable = "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"; PrefixArgs = @() }
        [PSCustomObject]@{ Executable = "$env:LOCALAPPDATA\Python\pythoncore-3.13-64\python.exe"; PrefixArgs = @() }
    )
    foreach ($candidate in $PostInstallCandidates) {
        $Python = Test-PythonCommand -Executable $candidate.Executable -PrefixArgs $candidate.PrefixArgs
        if ($null -ne $Python) { break }
    }
}

if ($null -eq $Python) {
    throw "Python kuruldu ancak bu oturumda bulunamadi. Bilgisayari yeniden baslatip Baslat.bat dosyasini tekrar calistirin."
}

Write-Host "[OK] Python $($Python.Version) hazir."

# --- 2) Calisma zamani ikilileri -----------------------------------------
# mpv olmadan program acilmaz; eksikse pip bunu COZMEZ, o yuzden once bakilir.

$BinDir = Join-Path $ProjectRoot "bin"
$missingBinaries = @($RequiredBinaries | Where-Object { -not (Test-Path (Join-Path $BinDir $_)) })
if ($missingBinaries.Count -gt 0) {
    throw ("bin klasorunde su dosyalar eksik: " + ($missingBinaries -join ", ") +
           ". Projeyi eksiksiz kopyaladiginizdan emin olun (bkz. bin\RUNTIME_MANIFEST.txt).")
}
Write-Host "[OK] Calisma zamani ikilileri yerinde (mpv, yt-dlp, deno)."

# --- 3) Python paketleri --------------------------------------------------

if (Test-ModulesInstalled) {
    Write-Host "[OK] Gerekli paketler zaten kurulu."
}
else {
    Write-Host "[BILGI] Eksik paketler kuruluyor (requirements.txt)..."
    if (-not (Test-Path $Requirements)) {
        throw "requirements.txt bulunamadi: $Requirements"
    }
    & $Python.Executable @($Python.PrefixArgs) -m pip install --disable-pip-version-check -r $Requirements
    if ($LASTEXITCODE -ne 0) {
        throw "Paket kurulumu basarisiz oldu (pip cikis kodu: $LASTEXITCODE)."
    }
    if (-not (Test-ModulesInstalled)) {
        throw "Paketler kuruldu ancak yuklenemiyor. Yukaridaki pip ciktisini inceleyin."
    }
    Write-Host "[OK] Paketler kuruldu."
}

# --- 4) Baslat ------------------------------------------------------------

if ($CheckOnly) {
    Write-Host "[OK] Kontrol tamam. -CheckOnly verildigi icin program baslatilmadi."
    exit 0
}

Write-Host "[BILGI] MLC Player baslatiliyor..."
& $Python.Executable @($Python.PrefixArgs) $MainFile
exit $LASTEXITCODE
