# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
# MLC Player - bootstrap for the automatic launcher.
#
# Goal: on a freshly installed Windows, double-clicking Start.bat should
# open the player. Python is NOT installed if it is already present, only
# verified; pip is NOT run if the packages are already there. That keeps
# every launch after the first one fast.
#
# -CheckOnly: verifies everything but does NOT start the player.

param(
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
$MinimumPython = [Version]"3.12"
$MaximumPythonExclusive = [Version]"3.15"
$Python = $null

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$MainFile = Join-Path $ProjectRoot "main.py"
$Requirements = Join-Path $ProjectRoot "requirements.txt"
$DependencyVerifier = Join-Path $ProjectRoot "packaging\verify_dependencies.py"

# The runtime binaries are carried in the repository; pip does not
# provide them.
$RequiredBinaries = @("mpv-2.dll", "yt-dlp.exe", "deno.exe")

function Install-PythonFromOfficialSite {
    Write-Host "[INFO] Downloading Python from the official site..."
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

    $index = Invoke-WebRequest -UseBasicParsing -Uri "https://www.python.org/ftp/python/"
    $versions = [regex]::Matches($index.Content, 'href="(3\.13\.\d+)/"') |
        ForEach-Object { [Version]$_.Groups[1].Value } |
        Sort-Object -Descending -Unique
    $latest = $versions | Select-Object -First 1
    if ($null -eq $latest) {
        throw "Could not determine a Python 3.13 download on the official site."
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
            throw "The official Python installer failed (exit code: $($process.ExitCode))."
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
        if ([Version]$versionText -ge $MaximumPythonExclusive) { return $null }
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
    # Metadata is checked without importing mpv, so the native DLL is not
    # loaded here. A present but stale package is intentionally not accepted.
    if (-not (Test-Path $DependencyVerifier)) { return $false }
    & $Python.Executable @($Python.PrefixArgs) $DependencyVerifier $Requirements --quiet
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
    Write-Host "[INFO] Python 3.12-3.14 not found. Installing Python 3.13..."
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
    throw "Python was installed but cannot be found in this session. Restart the computer and run Start.bat again."
}

Write-Host "[OK] Python $($Python.Version) is ready."

# --- 2) Runtime binaries --------------------------------------------------
# Without mpv the player cannot open, and pip does NOT fix that, so this is
# checked first.

$BinDir = Join-Path $ProjectRoot "bin"
$missingBinaries = @($RequiredBinaries | Where-Object { -not (Test-Path (Join-Path $BinDir $_)) })
if ($missingBinaries.Count -gt 0) {
    throw ("These files are missing from the bin folder: " + ($missingBinaries -join ", ") +
           ". Make sure the project was copied in full (see bin\RUNTIME_MANIFEST.txt).")
}
Write-Host "[OK] Runtime binaries are in place (mpv, yt-dlp, deno)."

# --- 3) Python packages ---------------------------------------------------

if (Test-ModulesInstalled) {
    Write-Host "[OK] The required packages are already installed."
}
else {
    Write-Host "[INFO] Installing the missing packages (requirements.txt)..."
    if (-not (Test-Path $Requirements)) {
        throw "requirements.txt not found: $Requirements"
    }
    & $Python.Executable @($Python.PrefixArgs) -m pip install --disable-pip-version-check -r $Requirements
    if ($LASTEXITCODE -ne 0) {
        throw "Package installation failed (pip exit code: $LASTEXITCODE)."
    }
    if (-not (Test-ModulesInstalled)) {
        throw "The packages were installed but cannot be loaded. Read the pip output above."
    }
    Write-Host "[OK] Packages installed."
}

# --- 4) Launch ------------------------------------------------------------

if ($CheckOnly) {
    Write-Host "[OK] Checks passed. -CheckOnly was given, so the player was not started."
    exit 0
}

Write-Host "[INFO] Starting MLC Player..."
& $Python.Executable @($Python.PrefixArgs) $MainFile
exit $LASTEXITCODE
