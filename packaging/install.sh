#!/usr/bin/env bash
# ============================================================================
#  🜲 NyxRecover — Instalador universal (Linux / macOS)
#  Instala TODO en ~/.nyxrecover/app — sin archivos fuera de esa carpeta.
#  Desinstalación limpia:  ~/.nyxrecover/uninstall.sh
# ============================================================================
set -euo pipefail

APP_DIR="$HOME/.nyxrecover/app"
BIN_DIR="$HOME/.local/bin"
REPO_RAW="https://raw.githubusercontent.com/D1se0/nyxrecover/main"

c_cyan='\033[0;36m'; c_purple='\033[1;35m'; c_green='\033[0;32m'; c_red='\033[0;31m'; c_off='\033[0m'
banner() {
  echo -e "${c_purple}"
  cat <<'ART'
  ███╗   ██╗██╗   ██╗██╗  ██╗    🜲  NyxRecover
  ████╗  ██╝╚██╗ ██╔╝██║ ██╔╝    Recuperación forense + borrado seguro
  ██╔██╗ ██║  ╚████╔╝ █████╔╝     — instalador universal —
  ██║╚██╗██║   ╚██╔╝  ██╔═██╗
  ██║ ╚████║    ██║   ██║  ██╗    https://github.com/D1se0/nyxrecover
  ╚═╝  ╚═══╝    ╚═╝   ╚═╝  ╚═╝
ART
  echo -e "${c_off}"
}

banner
echo -e "${c_cyan}▸ Destino único: ${APP_DIR} (cero archivos basura)${c_off}"

# ── 1. Dependencias del sistema ─────────────────────────────────────────────
NEED_PY=1
if command -v python3 >/dev/null 2>&1; then
  PYV="$(python3 -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
  if python3 -c "import sys; exit(0 if sys.version_info >= (3,9) else 1)"; then
    NEED_PY=0
    echo "✓ Python ${PYV} encontrado"
  fi
fi
if [ "$NEED_PY" = "1" ]; then
  echo "▸ Instalando Python 3…"
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -y && sudo apt-get install -y python3 python3-venv python3-pip
  elif command -v dnf >/dev/null 2>&1; then sudo dnf install -y python3 python3-pip
  elif command -v pacman >/dev/null 2>&1; then sudo pacman -Sy --noconfirm python python-pip
  elif command -v brew >/dev/null 2>&1; then brew install python
  else echo -e "${c_red}✗ Instala Python 3.9+ manualmente${c_off}"; exit 1; fi
fi

# ── 2. Obtener el código (git clone o descarga tarball) ─────────────────────
SRC_DIR="$(mktemp -d)"
trap 'rm -rf "$SRC_DIR"' EXIT
if [ -f "$(dirname "$0")/../nyx/nyxcore/cli.py" ]; then
  echo "▸ Instalando desde copia local…"
  cp -r "$(cd "$(dirname "$0")/.." && pwd)/." "$SRC_DIR/"
elif command -v git >/dev/null 2>&1; then
  echo "▸ Descargando desde GitHub…"
  git clone --depth 1 "${NYX_REPO:-https://github.com/D1se0/nyxrecover.git}" "$SRC_DIR"
else
  echo "▸ Descargando tarball…"
  curl -fsSL "${NYX_REPO:-https://github.com/D1se0/nyxrecover}/archive/refs/heads/main.tar.gz" | tar xz -C "$SRC_DIR" --strip-components=1
fi

# ── 3. Instalar en la carpeta única ─────────────────────────────────────────
mkdir -p "$APP_DIR" "$BIN_DIR"
rm -rf "$APP_DIR.tmp"
cp -r "$SRC_DIR" "$APP_DIR.tmp"
rm -rf "$APP_DIR"
mv "$APP_DIR.tmp" "$APP_DIR"

# ── 4. Entorno virtual aislado + dependencias ───────────────────────────────
echo "▸ Creando entorno aislado…"
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -q --upgrade pip
"$APP_DIR/.venv/bin/pip" install -q -e "$APP_DIR"

# ── 5. Lanzadores en ~/.local/bin (solo 2 stubs, sin basura) ────────────────
for cmd in nyx nyx-tui; do
  cat > "$BIN_DIR/$cmd" <<EOF
#!/usr/bin/env bash
exec "$APP_DIR/.venv/bin/$cmd" "\$@"
EOF
  chmod +x "$BIN_DIR/$cmd"
done
case ":$PATH:" in *":$BIN_DIR:"*) ;; *) echo -e "${c_yellow}▸ Añade a tu PATH: export PATH=\"$BIN_DIR:\$PATH\"${c_off}";; esac

# ── 6. Desinstalador limpio ─────────────────────────────────────────────────
cat > "$HOME/.nyxrecover/uninstall.sh" <<EOF
#!/usr/bin/env bash
set -e
echo "🜲 Desinstalando NyxRecover…"
rm -rf "$APP_DIR" "$HOME/.nyxrecover/locks" "$HOME/.nyxrecover/journal"
rm -f "$BIN_DIR/nyx" "$BIN_DIR/nyx-tui"
rmdir "$HOME/.nyxrecover" 2>/dev/null || true
echo "✓ Desinstalado. No queda ningún archivo de NyxRecover en el sistema."
EOF
chmod +x "$HOME/.nyxrecover/uninstall.sh"

echo
echo -e "${c_green}✓ Instalación completada${c_off}"
echo "  ▸ TUI:        nyx-tui     (sudo nyx-tui para acceso a discos)"
echo "  ▸ CLI:        nyx --help  (sudo nyx devices …)"
echo "  ▸ Desinstalar: ~/.nyxrecover/uninstall.sh"
