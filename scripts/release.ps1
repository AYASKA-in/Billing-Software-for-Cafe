param(
    [string]$Version = "",
    [switch]$SkipSmoke,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"

function Get-Version {
    param([string]$VersionArg)
    if ($VersionArg -and $VersionArg.Trim()) {
        return $VersionArg.Trim()
    }
    $versionFile = Join-Path $PSScriptRoot "..\VERSION"
    if (-not (Test-Path $versionFile)) {
        throw "VERSION file not found at $versionFile"
    }
    return (Get-Content $versionFile -Raw).Trim()
}

function Ensure-PyInstaller {
    param([string]$PythonExe)
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $PythonExe -c "import PyInstaller" *> $null
    $probeExitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousPreference

    if ($probeExitCode -ne 0) {
        Write-Host "PyInstaller not found. Installing..."
        & $PythonExe -m pip install pyinstaller
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to install PyInstaller"
        }
    }
}

function Resolve-IsccPath {
    $cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    $candidates = @(
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    )

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) {
            return $candidate
        }
    }

    $registryPaths = @(
        "HKLM:/Software/Microsoft/Windows/CurrentVersion/Uninstall/*",
        "HKLM:/Software/WOW6432Node/Microsoft/Windows/CurrentVersion/Uninstall/*",
        "HKCU:/Software/Microsoft/Windows/CurrentVersion/Uninstall/*"
    )
    foreach ($path in $registryPaths) {
        $entries = Get-ItemProperty $path -ErrorAction SilentlyContinue |
            Where-Object { $_.DisplayName -like "*Inno Setup*" }
        foreach ($entry in $entries) {
            $installLocation = $entry.InstallLocation
            if ($installLocation) {
                $isccFromRegistry = Join-Path $installLocation "ISCC.exe"
                if (Test-Path $isccFromRegistry) {
                    return $isccFromRegistry
                }
            }
        }
    }

    return $null
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python executable not found at $pythonExe"
}

$releaseVersion = Get-Version -VersionArg $Version
$releaseRoot = Join-Path $repoRoot "release"
$versionDir = Join-Path $releaseRoot ("v" + $releaseVersion)
$distDir = Join-Path $versionDir "dist"
$buildDir = Join-Path $versionDir "build"

if (Test-Path $versionDir) {
    Remove-Item $versionDir -Recurse -Force
}
New-Item -ItemType Directory -Path $distDir | Out-Null
New-Item -ItemType Directory -Path $buildDir | Out-Null

if (-not $SkipSmoke) {
    Write-Host "Running hard smoke regression..."
    & $pythonExe scripts/hard_smoke.py
    if ($LASTEXITCODE -ne 0) {
        throw "Hard smoke failed. Release aborted."
    }
}

Ensure-PyInstaller -PythonExe $pythonExe

Write-Host "Building Windows executable with PyInstaller..."
$schemaFile = Join-Path $repoRoot "app\database\schema.sql"
$addDataArg = "$schemaFile;app/database"
$iconFile = Join-Path $repoRoot "app_icon.ico"
$logoFile = Join-Path $repoRoot "app_logo_circular.png"
$versionFile = Join-Path $repoRoot "VERSION"
$licensePublicKey = Join-Path $repoRoot "config\license_public_key.pem"
$addIconArg = "$iconFile;."
$addLogoArg = "$logoFile;."
$addVersionArg = "$versionFile;."
$pyInstallerArgs = @(
    "-m",
    "PyInstaller",
    "--noconfirm",
    "--clean",
    "--windowed",
    "--name",
    "CafePOS",
    "--icon",
    $iconFile,
    "--distpath",
    $distDir,
    "--workpath",
    $buildDir,
    "--specpath",
    $buildDir,
    "--add-data",
    $addDataArg,
    "--add-data",
    $addIconArg,
    "--add-data",
    $addLogoArg,
    "--add-data",
    $addVersionArg,
    "main.py"
)
if (Test-Path $licensePublicKey) {
    $pyInstallerArgs = $pyInstallerArgs[0..($pyInstallerArgs.Length - 2)] + @(
        "--add-data",
        "$licensePublicKey;config",
        "main.py"
    )
}
& $pythonExe @pyInstallerArgs
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed"
}

$exeFolder = Join-Path $distDir "CafePOS"
if (-not (Test-Path $exeFolder)) {
    throw "Build output missing: $exeFolder"
}

Copy-Item README.md (Join-Path $versionDir "README.txt") -Force
Copy-Item VERSION (Join-Path $versionDir "VERSION.txt") -Force

$zipPath = Join-Path $versionDir ("CafePOS-v" + $releaseVersion + "-win64.zip")
if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}

$packageRoot = Join-Path $env:TEMP ("CafePOS-release-" + [guid]::NewGuid().ToString())
$packageExeFolder = Join-Path $packageRoot "CafePOS"
try {
    New-Item -ItemType Directory -Path $packageExeFolder | Out-Null
    Copy-Item $exeFolder\* $packageExeFolder -Recurse -Force

    $zipCreated = $false
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        try {
            Compress-Archive -Path $packageExeFolder -DestinationPath $zipPath -Force
            $zipCreated = $true
            break
        } catch {
            if ($attempt -eq 3) {
                throw
            }
            Start-Sleep -Seconds (2 * $attempt)
        }
    }

    if (-not $zipCreated) {
        throw "Failed to create portable zip"
    }
} finally {
    if (Test-Path $packageRoot) {
        Remove-Item $packageRoot -Recurse -Force
    }
}

$installerBuilt = $false
$installerPath = Join-Path $versionDir ("CafePOS-v" + $releaseVersion + "-setup.exe")
if (-not $SkipInstaller) {
    $isccPath = Resolve-IsccPath
    if ($isccPath) {
        Write-Host "Building installer with Inno Setup..."
        $isccArgs = @(
            (Join-Path $repoRoot "installer\CafePOS.iss"),
            "/DAppVersion=$releaseVersion",
            "/DSourceDir=$exeFolder",
            "/DOutputDir=$versionDir",
            "/DOutputBaseFilename=CafePOS-v$releaseVersion-setup"
        )
        & $isccPath @isccArgs
        if ($LASTEXITCODE -eq 0 -and (Test-Path $installerPath)) {
            $installerBuilt = $true
        }
    }
}

$manifestPath = Join-Path $versionDir "manifest.txt"
$lines = @(
    "Cafe POS Release",
    "Version: $releaseVersion",
    "Created: $(Get-Date -Format s)",
    "Portable ZIP: $zipPath",
    "Installer: " + ($(if ($installerBuilt) { $installerPath } else { "not built (install Inno Setup or use -SkipInstaller)" }))
)
$lines | Out-File -FilePath $manifestPath -Encoding utf8

Write-Host "Release completed."
Write-Host "Version folder: $versionDir"
Write-Host "Portable package: $zipPath"
if ($installerBuilt) {
    Write-Host "Installer package: $installerPath"
} else {
    Write-Host "Installer package: not built"
}
