param([string]$OutputDir = (Join-Path $PSScriptRoot 'release'))
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$compiler = Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'
if (-not (Test-Path -LiteralPath $compiler)) {
    $compiler = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'
}
if (-not (Test-Path -LiteralPath $compiler)) {
    throw 'Inno Setup 6 not found. Install Inno Setup before building the installer.'
}
if (-not (Test-Path -LiteralPath 'release\CryptArch-icon\CryptArch.exe')) {
    throw 'Current release not found. Build the application before building the installer.'
}
if (-not (Test-Path -LiteralPath $OutputDir)) {
    throw "Output directory not found: $OutputDir"
}
& $compiler '/Qp' "/O$OutputDir" 'installer.iss'
if ($LASTEXITCODE -ne 0) { throw "Installer build failed: $LASTEXITCODE" }
Write-Host "Ready: $OutputDir\CryptArch-Setup.exe"
