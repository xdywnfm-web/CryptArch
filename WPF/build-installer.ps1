$ErrorActionPreference = 'Stop'
$compiler = (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source
if (-not $compiler) {
    $compiler = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe") |
        Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $compiler) { throw 'Install Inno Setup 6 before building the installer.' }
& $compiler /Qp "$PSScriptRoot\installer.iss"
if ($LASTEXITCODE -ne 0) { throw "Installer build failed: $LASTEXITCODE" }
