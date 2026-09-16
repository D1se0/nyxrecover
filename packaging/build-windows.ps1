#!/usr/bin/env pwsh
# ============================================================================
#  🜲 NyxRecover — build de Windows (PyInstaller → exe portable)
#  Ejecutar en Windows con Python 3.10+:  .\packaging\build-windows.ps1
#  Produce: dist\NyxRecover-<ver>-windows-x64.zip (portable, sin instalación)
# ============================================================================
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Version = (Select-String -Path "$Root\nyx\nyxcore\version.py" -Pattern 'VERSION = "([^"]+)"').Matches[0].Groups[1].Value
Write-Host "🜲 NyxRecover $Version — build Windows" -ForegroundColor Magenta

# venv aislado
python -m venv "$Root\.venv-win"
& "$Root\.venv-win\Scripts\pip.exe" install -q --upgrade pip
& "$Root\.venv-win\Scripts\pip.exe" install -q textual rich pyinstaller

# limpiar
Remove-Item -Recurse -Force "$Root\build", "$Root\dist\NyxRecover*" -ErrorAction SilentlyContinue

# PyInstaller: un solo exe + icono si existe
$IconArg = ""
if (Test-Path "$Root\assets\nyx.ico") { $IconArg = "--icon=$Root\assets\nyx.ico" }
& "$Root\.venv-win\Scripts\pyinstaller.exe" `
  --name "NyxRecover" `
  --onefile `
  --console `
  $IconArg `
  --add-data "$Root\nyx;nyx" `
  --hidden-import textual `
  --collect-all textual `
  --collect-all rich `
  --distpath "$Root\dist" `
  "$Root\nyx\launcher.py"

Compress-Archive -Path "$Root\dist\NyxRecover.exe" `
  -DestinationPath "$Root\dist\NyxRecover-$Version-windows-x64.zip" -Force
Write-Host "✓ Generado: dist\NyxRecover-$Version-windows-x64.zip" -ForegroundColor Green
