param(
    [string]$Python = ".\.venv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$BuildRoot = Join-Path $ProjectRoot "build\installer"
$PayloadDir = Join-Path $BuildRoot "payload"
$DistDir = Join-Path $ProjectRoot "dist"
$SetupExe = Join-Path $DistDir "PurchaseTagger-v1.0-Setup.exe"
$AppExe = Join-Path $DistDir "purchase_tagger_app.exe"

function Assert-UnderProjectRoot {
    param([string]$Path)

    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $rootPath = [System.IO.Path]::GetFullPath($ProjectRoot)
    if (-not $fullPath.StartsWith($rootPath, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to operate outside project root: $fullPath"
    }
}

Assert-UnderProjectRoot $BuildRoot
Assert-UnderProjectRoot $DistDir

if (-not (Test-Path $Python)) {
    throw "Python executable not found: $Python"
}

& $Python -m PyInstaller --noconfirm --clean (Join-Path $ProjectRoot "purchase_tagger_app.spec")

if (-not (Test-Path $AppExe)) {
    throw "PyInstaller did not create expected executable: $AppExe"
}

if (Test-Path $BuildRoot) {
    Remove-Item -LiteralPath $BuildRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $PayloadDir -Force | Out-Null
New-Item -ItemType Directory -Path $DistDir -Force | Out-Null

Copy-Item -LiteralPath $AppExe -Destination (Join-Path $PayloadDir "purchase_tagger_app.exe") -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "README.md") -Destination (Join-Path $PayloadDir "README.md") -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "CHANGELOG.md") -Destination (Join-Path $PayloadDir "CHANGELOG.md") -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "LICENSE") -Destination (Join-Path $PayloadDir "LICENSE") -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "tags.json") -Destination (Join-Path $PayloadDir "tags.json") -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "docs\USER_MANUAL.md") -Destination (Join-Path $PayloadDir "MANUAL_DE_USUARIO.md") -Force

$installCmd = @'
@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
exit /b %ERRORLEVEL%
'@
Set-Content -LiteralPath (Join-Path $PayloadDir "install.cmd") -Value $installCmd -Encoding ASCII

$installPs1 = @'
$ErrorActionPreference = "Stop"

$appName = "PurchaseTagger"
$installRoot = Join-Path $env:LOCALAPPDATA "Programs\PurchaseTagger"
$docsRoot = Join-Path $installRoot "docs"
$exePath = Join-Path $installRoot "PurchaseTagger.exe"
$desktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "PurchaseTagger.lnk"
$startMenuDir = Join-Path ([Environment]::GetFolderPath("Programs")) "PurchaseTagger"
$startMenuShortcut = Join-Path $startMenuDir "PurchaseTagger.lnk"
$manualShortcut = Join-Path $startMenuDir "Manual de usuario.lnk"
$uninstallScript = Join-Path $installRoot "uninstall.ps1"

New-Item -ItemType Directory -Path $installRoot -Force | Out-Null
New-Item -ItemType Directory -Path $docsRoot -Force | Out-Null
New-Item -ItemType Directory -Path $startMenuDir -Force | Out-Null

Copy-Item -LiteralPath (Join-Path $PSScriptRoot "purchase_tagger_app.exe") -Destination $exePath -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "README.md") -Destination (Join-Path $docsRoot "README.md") -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "CHANGELOG.md") -Destination (Join-Path $docsRoot "CHANGELOG.md") -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "LICENSE") -Destination (Join-Path $docsRoot "LICENSE") -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "tags.json") -Destination (Join-Path $docsRoot "tags.json") -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "MANUAL_DE_USUARIO.md") -Destination (Join-Path $docsRoot "MANUAL_DE_USUARIO.md") -Force

$shell = New-Object -ComObject WScript.Shell

$shortcut = $shell.CreateShortcut($desktopShortcut)
$shortcut.TargetPath = $exePath
$shortcut.WorkingDirectory = $installRoot
$shortcut.IconLocation = $exePath
$shortcut.Save()

$shortcut = $shell.CreateShortcut($startMenuShortcut)
$shortcut.TargetPath = $exePath
$shortcut.WorkingDirectory = $installRoot
$shortcut.IconLocation = $exePath
$shortcut.Save()

$shortcut = $shell.CreateShortcut($manualShortcut)
$shortcut.TargetPath = Join-Path $docsRoot "MANUAL_DE_USUARIO.md"
$shortcut.WorkingDirectory = $docsRoot
$shortcut.Save()

Set-Content -LiteralPath $uninstallScript -Encoding UTF8 -Value @"
`$ErrorActionPreference = "Stop"
Remove-Item -LiteralPath "$desktopShortcut" -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath "$startMenuDir" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath "$installRoot" -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "PurchaseTagger desinstalado."
"@

Write-Host "$appName instalado en $installRoot"
'@
Set-Content -LiteralPath (Join-Path $PayloadDir "install.ps1") -Value $installPs1 -Encoding UTF8

$sedPath = Join-Path $BuildRoot "PurchaseTagger.iexpress.sed"
$sourcePath = $PayloadDir.TrimEnd("\") + "\"
$sed = @"
[Version]
Class=IEXPRESS
SEDVersion=3

[Options]
PackagePurpose=InstallApp
ShowInstallProgramWindow=0
HideExtractAnimation=1
UseLongFileName=1
InsideCompressed=0
CAB_FixedSize=0
CAB_ResvCodeSigning=0
RebootMode=N
InstallPrompt=%InstallPrompt%
DisplayLicense=%DisplayLicense%
FinishMessage=%FinishMessage%
TargetName=%TargetName%
FriendlyName=%FriendlyName%
AppLaunched=%AppLaunched%
PostInstallCmd=%PostInstallCmd%
AdminQuietInstCmd=
UserQuietInstCmd=
SourceFiles=SourceFiles

[Strings]
InstallPrompt=Instalar PurchaseTagger v1.0 en este usuario?
DisplayLicense=
FinishMessage=PurchaseTagger v1.0 fue instalado. Puede abrirlo desde el Escritorio o el Menu Inicio.
TargetName=$SetupExe
FriendlyName=PurchaseTagger v1.0
AppLaunched=install.cmd
PostInstallCmd=<None>
FILE0=purchase_tagger_app.exe
FILE1=install.cmd
FILE2=install.ps1
FILE3=README.md
FILE4=CHANGELOG.md
FILE5=LICENSE
FILE6=tags.json
FILE7=MANUAL_DE_USUARIO.md

[SourceFiles]
SourceFiles0=$sourcePath

[SourceFiles0]
%FILE0%=
%FILE1%=
%FILE2%=
%FILE3%=
%FILE4%=
%FILE5%=
%FILE6%=
%FILE7%=
"@
Set-Content -LiteralPath $sedPath -Value $sed -Encoding ASCII

if (Test-Path $SetupExe) {
    Remove-Item -LiteralPath $SetupExe -Force
}

$iexpress = Start-Process -FilePath "iexpress.exe" -ArgumentList @("/N", "/Q", $sedPath) -Wait -PassThru -WindowStyle Hidden

for ($i = 0; $i -lt 60 -and -not (Test-Path $SetupExe); $i++) {
    Start-Sleep -Seconds 1
}

if (-not (Test-Path $SetupExe)) {
    throw "IExpress did not create expected installer: $SetupExe (exit code $($iexpress.ExitCode))"
}

$zipPath = Join-Path $DistDir "PurchaseTagger-v1.0-portable.zip"
if (Test-Path $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -Path (Join-Path $PayloadDir "*") -DestinationPath $zipPath -Force

Write-Host "Installer created: $SetupExe"
Write-Host "Portable package created: $zipPath"
