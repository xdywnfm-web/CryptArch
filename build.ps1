$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$destination = Join-Path $PSScriptRoot 'release\CryptArch-icon'
$staging = Join-Path $PSScriptRoot 'release\icon-build'
if (Test-Path -LiteralPath $destination) { throw "Release already exists: $destination" }
if (Test-Path -LiteralPath $staging) { throw "Staging directory already exists: $staging" }
python -m PyInstaller --noconfirm --clean --windowed --name CryptArch --icon "$PSScriptRoot\assets\CryptArch.ico" --distpath "$staging" --workpath build-icon --specpath build-icon --add-data "$PSScriptRoot\assets\CryptArch.ico;assets" --add-binary "$PSScriptRoot\bin\ffmpeg.exe;bin" --add-binary "$PSScriptRoot\bin\ffprobe.exe;bin" "$PSScriptRoot\app.py"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed: $LASTEXITCODE" }
Copy-Item README.md,FFMPEG-LICENSE.txt,FFMPEG-README.txt -Destination (Join-Path $staging 'CryptArch')
Move-Item -LiteralPath (Join-Path $staging 'CryptArch') -Destination $destination
if (@(Get-ChildItem -LiteralPath $staging -Force).Count -eq 0) { Remove-Item -LiteralPath $staging }
Write-Host "Ready: $destination\CryptArch.exe"
