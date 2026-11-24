param([switch]$ExternalFfmpeg)
$ErrorActionPreference = 'Stop'
$project = Split-Path $PSScriptRoot
$name = if ($ExternalFfmpeg) { 'CryptArch V2 Beta (external FFmpeg)' } else { 'CryptArch V2 Beta WPF' }
$out = Join-Path $project "release\$name"
$stage = Join-Path $project $(if ($ExternalFfmpeg) { 'build-wpf-external' } else { 'build-wpf' })
$framework = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319'
if (Test-Path -LiteralPath $out) { throw "Release already exists: $out" }
if (Test-Path -LiteralPath $stage) { throw "Build directory already exists: $stage" }
New-Item -ItemType Directory -Path $stage | Out-Null
Set-Location $project
$tools = @()
if (-not $ExternalFfmpeg) {
    $tools = @('--add-binary', "$project\bin\ffmpeg.exe;bin", '--add-binary', "$project\bin\ffprobe.exe;bin")
}
python -m PyInstaller --noconfirm --console --name CryptArchEngine --paths "$project" --distpath "$stage\dist" --workpath "$stage\work" --specpath "$stage" @tools "$PSScriptRoot\worker.py"
if ($LASTEXITCODE -ne 0) { throw "Engine build failed: $LASTEXITCODE" }
$bundle = Join-Path $stage 'bundle'
New-Item -ItemType Directory -Path $bundle | Out-Null
$refs = @('System.Xaml.dll', 'System.Web.Extensions.dll', 'System.Windows.Forms.dll',
    'WPF\WindowsBase.dll', 'WPF\PresentationCore.dll', 'WPF\PresentationFramework.dll')
$refs = $refs | ForEach-Object { "/reference:$framework\$_" }
& "$framework\csc.exe" /nologo /codepage:65001 /target:winexe /platform:x64 @refs `
    "/win32icon:$project\assets\CryptArch.ico" "/resource:$PSScriptRoot\Workspace.xaml,Workspace.xaml" `
    "/resource:$PSScriptRoot\Notice.xaml,Notice.xaml" `
    "/out:$bundle\CryptArch V2 Beta.exe" "$PSScriptRoot\Program.cs"
if ($LASTEXITCODE -ne 0) { throw "WPF build failed: $LASTEXITCODE" }
Move-Item -LiteralPath "$stage\dist\CryptArchEngine" -Destination "$bundle\engine"
Copy-Item LICENSE,FFMPEG-LICENSE.txt,FFMPEG-README.txt -Destination $bundle
Copy-Item "$PSScriptRoot\README.md" -Destination $bundle
Move-Item -LiteralPath $bundle -Destination $out
Write-Host "Ready: $out\CryptArch V2 Beta.exe"
