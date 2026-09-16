#!/usr/bin/env bash
# ============================================================================
#  🜲 NyxRecover — build macOS (zip portable con venv)
#  Uso: ./packaging/build-macos.sh
# ============================================================================
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(grep -oP '(?<=^VERSION = ")[^"]+' "$ROOT/nyx/nyxcore/version.py")"
echo "🜲 NyxRecover $VERSION — build macOS"

python3 -m venv "$ROOT/.venv-mac"
"$ROOT/.venv-mac/bin/pip" install -q --upgrade pip
"$ROOT/.venv-mac/bin/pip" install -q textual rich pyinstaller

rm -rf "$ROOT/build" "$ROOT/dist/NyxRecover.app" "$ROOT/dist/NyxRecover-$VERSION-macos.zip"
"$ROOT/.venv-mac/bin/pyinstaller" \
  --name NyxRecover --onefile --console \
  --distpath "$ROOT/dist" \
  "$ROOT/nyx/launcher.py"

mkdir -p "$ROOT/dist/stage"
cp "$ROOT/dist/NyxRecover" "$ROOT/dist/stage/"
cp "$ROOT/README.md" "$ROOT/dist/stage/"
(cd "$ROOT/dist" && zip -qr "NyxRecover-$VERSION-macos.zip" stage)
rm -rf "$ROOT/dist/stage"
echo "✓ Generado: dist/NyxRecover-$VERSION-macos.zip"
