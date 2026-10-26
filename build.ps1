$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path "assets\icon.ico")) {
    python tools\gen_icon.py
}

$venv = ".venv-build"
if (-not (Test-Path "$venv\Scripts\python.exe")) {
    $created = $false
    foreach ($cmd in @(
        @{ exe = "py"; args = @("-3.12", "-m", "venv", $venv) },
        @{ exe = "py"; args = @("-3.9", "-m", "venv", $venv) },
        @{ exe = "python"; args = @("-m", "venv", $venv) }
    )) {
        $exe = $cmd.exe
        $argList = $cmd.args
        & $exe @argList
        if (Test-Path "$venv\Scripts\python.exe") { $created = $true; break }
    }
    if (-not $created) { throw "无法创建虚拟环境 $venv" }
}

& "$venv\Scripts\python.exe" -m pip install --quiet --upgrade pip 2>&1 | Out-Null
& "$venv\Scripts\python.exe" -m pip install --quiet pyinstaller 2>&1 | Out-Null

$ErrorActionPreference = "Continue"
& "$venv\Scripts\python.exe" -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --noconsole `
    --name "摸鱼阅读" `
    --icon "assets\icon.ico" `
    --add-data "assets\icon.ico;assets" `
    run.py 2>&1 | ForEach-Object { Write-Host $_ }
$buildOk = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = "Stop"

if (-not $buildOk -or -not (Test-Path "dist\摸鱼阅读.exe")) { throw "打包失败" }
Write-Host ""
Write-Host "打包完成: dist\摸鱼阅读.exe"
