#!/usr/bin/env bash
# ============================================================================
#  🜲 NyxRecover — empaquetador .deb (Debian/Ubuntu/Kali)
#  Genera nyxrecover_<ver>_all.deb con dependencias de sistema python3.
#  Uso:  ./packaging/build-deb.sh
# ============================================================================
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(grep -oP '(?<=^VERSION = ")[^"]+' "$ROOT/nyx/nyxcore/version.py")"
WORK="$(mktemp -d)"
PKG="nyxrecover_${VERSION}_all"
trap 'rm -rf "$WORK"' EXIT

echo "🜲 Construyendo $PKG.deb"

# ── árbol Debian ────────────────────────────────────────────────────────────
mkdir -p "$WORK/$PKG/DEBIAN" \
         "$WORK/$PKG/usr/lib/nyxrecover" \
         "$WORK/$PKG/usr/bin" \
         "$WORK/$PKG/usr/share/applications" \
         "$WORK/$PKG/usr/share/icons/hicolor/scalable/apps" \
         "$WORK/$PKG/usr/share/doc/nyxrecover"

cp -r "$ROOT/nyx" "$WORK/$PKG/usr/lib/nyxrecover/"
find "$WORK/$PKG" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
cp "$ROOT/assets/nyx.svg" "$WORK/$PKG/usr/share/icons/hicolor/scalable/apps/nyxrecover.svg" 2>/dev/null || true

cat > "$WORK/$PKG/DEBIAN/control" <<EOF
Package: nyxrecover
Version: $VERSION
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.9), python3-venv
Recommends: python3-tk, python3-pil
Installed-Size: 8192
Maintainer: NyxRecover Team <nyxrecover@users.noreply.github.com>
Description: Recuperacion forense de datos borrados y borrado seguro
 NyxRecover escanea discos y particiones para rescatar archivos eliminados
 (carving por firmas + parsers ext/FAT/NTFS), analiza timelines, espacio
 slack, cifrado LUKS/BitLocker y genera certificados de borrado NIST/DoD.
 Incluye aplicacion de escritorio con ventana, TUI oscura y CLI completa.
Homepage: https://github.com/D1se0/nyxrecover
EOF

cat > "$WORK/$PKG/DEBIAN/postinst" <<'EOF'
#!/bin/bash
set -e
echo "NyxRecover: instalando entorno Python (una sola vez)..."
mkdir -p /var/lib/nyxrecover
python3 -m venv /var/lib/nyxrecover/venv
/var/lib/nyxrecover/venv/bin/pip install -q --upgrade pip
/var/lib/nyxrecover/venv/bin/pip install -q customtkinter pillow textual rich
echo "OK - NyxRecover instalado."
echo "  App de escritorio : nyx-app  (o el icono 'NyxRecover' en tu menu)"
echo "  Terminal (TUI)    : nyx-tui"
echo "  Linea de comandos : nyx --help"
EOF

cat > "$WORK/$PKG/DEBIAN/prerm" <<'EOF'
#!/bin/bash
set -e
rm -rf /var/lib/nyxrecover
rm -f /usr/local/bin/nyx /usr/local/bin/nyx-tui 2>/dev/null || true
exit 0
EOF

cat > "$WORK/$PKG/DEBIAN/postrm" <<'EOF'
#!/bin/bash
set -e
rm -rf /usr/lib/nyxrecover
exit 0
EOF

# lanzadores (usan el venv con textual instalado)
cat > "$WORK/$PKG/usr/bin/nyx" <<'EOF'
#!/bin/bash
exec /var/lib/nyxrecover/venv/bin/python -c 'import sys; sys.path.insert(0, "/usr/lib/nyxrecover"); from nyx.nyxcore.cli import main; main()' "$@"
EOF
cat > "$WORK/$PKG/usr/bin/nyx-tui" <<'EOF'
#!/bin/bash
exec /var/lib/nyxrecover/venv/bin/python -c 'import sys; sys.path.insert(0, "/usr/lib/nyxrecover"); from nyx.nyxcore.tui import main; main()' "$@"
EOF
cat > "$WORK/$PKG/usr/bin/nyx-app" <<'EOF'
#!/bin/bash
exec /var/lib/nyxrecover/venv/bin/python -c 'import sys; sys.path.insert(0, "/usr/lib/nyxrecover"); from nyx.nyxcore.gui import main; main()' "$@"
EOF
chmod +x "$WORK/$PKG/usr/bin/nyx" "$WORK/$PKG/usr/bin/nyx-tui" "$WORK/$PKG/usr/bin/nyx-app" \
         "$WORK/$PKG/DEBIAN/postinst" "$WORK/$PKG/DEBIAN/prerm" \
         "$WORK/$PKG/DEBIAN/postrm"

# entrada de menu (aplicacion de escritorio)
cat > "$WORK/$PKG/usr/share/applications/nyxrecover.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Version=1.0
Name=NyxRecover
GenericName=Recuperacion forense y borrado seguro
Comment=Rescata archivos borrados y borra datos con estandares NIST/DoD
Exec=nyx-app
Icon=nyxrecover
Terminal=false
Categories=System;Filesystem;Security;Utility;
Keywords=forense;recuperar;borrado;disco;usb;
EOF

# documentación
cp "$ROOT/README.md" "$WORK/$PKG/usr/share/doc/nyxrecover/" 2>/dev/null || true

# ── construir ───────────────────────────────────────────────────────────────
mkdir -p "$ROOT/dist"
dpkg-deb --build --root-owner-group "$WORK/$PKG" "$ROOT/dist/$PKG.deb"
echo "✓ Generado: dist/$PKG.deb"
