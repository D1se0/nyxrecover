#!/usr/bin/env pwsh
# ============================================================================
#  🜲 NyxRecover — build de Windows (PyInstaller → exe portable + instalador)
#  Ejecutar en Windows con Python 3.10+:  .\packaging\build-windows.ps1
#  Produce:
#    dist\NyxRecover-<ver>-windows-x64.zip         (portable, sin instalación)
#    dist\NyxRecover-<ver>-windows-x64-setup.exe   (instalador Inno Setup)
# ============================================================================
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Version = (Select-String -Path "$Root\nyx\nyxcore\version.py" -Pattern 'VERSION = "([^"]+)"').Matches[0].Groups[1].Value
Write-Host "🜲 NyxRecover $Version — build Windows" -ForegroundColor Magenta

# icono (Pillow, solo si falta)
if (-not (Test-Path "$Root\assets\nyx.ico")) {
  & python "$Root\packaging\make_icon.py"
}

# venv aislado
python -m venv "$Root\.venv-win"
& "$Root\.venv-win\Scripts\pip.exe" install -q --upgrade pip
& "$Root\.venv-win\Scripts\pip.exe" install -q textual rich pyinstaller

# limpiar
Remove-Item -Recurse -Force "$Root\build", "$Root\dist\NyxRecover*" -ErrorAction SilentlyContinue

# PyInstaller: un solo exe + icono
& "$Root\.venv-win\Scripts\pyinstaller.exe" `
  --name "NyxRecover" `
  --onefile `
  --console `
  --icon="$Root\assets\nyx.ico" `
  --add-data "$Root\nyx;nyx" `
  --collect-all textual `
  --collect-all rich `
  --distpath "$Root\dist" `
  "$Root\nyx\launcher.py"

Compress-Archive -Path "$Root\dist\NyxRecover.exe" `
  -DestinationPath "$Root\dist\NyxRecover-$Version-windows-x64.zip" -Force
Write-Host "✓ Generado: dist\NyxRecover-$Version-windows-x64.zip" -ForegroundColor Green

# instalador (Inno Setup 6) si está disponible
$ISCC = Get-ChildItem "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($ISCC) {
  & $ISCC.FullName /DAppVersion=$Version "$Root\packaging\windows-installer.iss"
  Write-Host "✓ Generado: dist\NyxRecover-$Version-windows-x64-setup.exe" -ForegroundColor Green
} else {
  Write-Warning "Inno Setup 6 no encontrado — solo se genera el portable. Instálalo: winget install JRSoftware.InnoSetup"
}
