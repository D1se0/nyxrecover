#!/usr/bin/env pwsh
# ============================================================================
#  NyxRecover — build de Windows (app de ventana + CLI + instalador)
#  Produce:
#    dist\NyxRecover-<ver>-windows-x64.zip         (portable: app + cli)
#    dist\NyxRecover-<ver>-windows-x64-setup.exe   (instalador Inno Setup)
# ============================================================================
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Version = (Select-String -Path "$Root\nyx\nyxcore\version.py" -Pattern 'VERSION = "([^"]+)"').Matches[0].Groups[1].Value
Write-Host "NyxRecover $Version — build Windows" -ForegroundColor Magenta

if (-not (Test-Path "$Root\assets\nyx.ico")) { & python "$Root\packaging\make_icon.py" }

python -m venv "$Root\.venv-win"
& "$Root\.venv-win\Scripts\pip.exe" install -q --upgrade pip
& "$Root\.venv-win\Scripts\pip.exe" install -q customtkinter pillow textual rich pyinstaller

Remove-Item -Recurse -Force "$Root\build", "$Root\dist\NyxRecover*" -ErrorAction SilentlyContinue

# 1) App de escritorio (ventana, sin consola)
& "$Root\.venv-win\Scripts\pyinstaller.exe" `
  --name "NyxRecover" --onefile --noconsole `
  --icon="$Root\assets\nyx.ico" `
  --add-data "$Root\nyx;nyx" `
  --collect-all customtkinter --collect-all textual --collect-all rich `
  --distpath "$Root\dist" "$Root\nyx\launcher.py"

# 2) CLI para scripts (consola)
& "$Root\.venv-win\Scripts\pyinstaller.exe" `
  --name "NyxRecover-cli" --onefile --console `
  --icon="$Root\assets\nyx.ico" `
  --add-data "$Root\nyx;nyx" `
  --collect-all customtkinter --collect-all textual --collect-all rich `
  --distpath "$Root\dist" "$Root\nyx\launcher.py"

# smoke test del CLI (la app de ventana no se lanza en CI por falta de sesión interactiva)
& "$Root\dist\NyxRecover-cli.exe" --cli audit 2>&1 | Tee-Object -Variable smoke
if ($LASTEXITCODE -ne 0) { throw "Smoke test del CLI fallo" }

# zip portable con ambos
Compress-Archive -Path "$Root\dist\NyxRecover.exe", "$Root\dist\NyxRecover-cli.exe" `
  -DestinationPath "$Root\dist\NyxRecover-$Version-windows-x64.zip" -Force
Write-Host "OK dist\NyxRecover-$Version-windows-x64.zip" -ForegroundColor Green

# instalador
$ISCC = Get-ChildItem "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe", "${env:ProgramFiles}\Inno Setup 7\ISCC.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($ISCC) {
  & $ISCC.FullName /DAppVersion=$Version "$Root\packaging\windows-installer.iss"
  Write-Host "OK dist\NyxRecover-$Version-windows-x64-setup.exe" -ForegroundColor Green
} else {
  Write-Warning "Inno Setup no encontrado — solo portable. winget install JRSoftware.InnoSetup"
}
