# 🜲 NyxRecover v1.0.0 — «Fénix»

> Primera versión estable. Lo que borraste nunca se fue de verdad.

**NyxRecover** es una suite forense gratuita que recupera archivos eliminados de
cualquier disco —reconstruyéndolos de forma íntegra— y, al revés, borra medios
con estándares NIST/DoD emitiendo un certificado verificable.

---

## 📦 Descargas

| Archivo | Plataforma | Uso |
|---|---|---|
| `nyxrecover_1.0.0_all.deb` | Linux Debian/Ubuntu/Kali | `sudo dpkg -i nyxrecover_1.0.0_all.deb` → `nyx-tui` |
| `NyxRecover-1.0.0-windows-x64.zip` | Windows 10/11 x64 | Descomprimir → `NyxRecover.exe` (portable) |
| `NyxRecover-1.0.0-macos.zip` | macOS | Descomprimir → `chmod +x NyxRecover && sudo ./NyxRecover` |

SHA-256 de todos los archivos disponibles en `SHA256SUMS.txt` adjunto a esta release.

## ✨ Novedades

### Recuperación (lo principal)
- 🧠 **Modo inteligente**: parsers de filesystem (ext2/3/4 · FAT12/16/32 · NTFS) + carving por firmas combinados.
- 🪄 **Carving**: 22 familias fiables con footer real y sanity-checks, ~71 MB/s medidos en hardware real.
- 🗂 **Recuperación selectiva** por ruta, incluyendo archivos borrados con su árbol original.
- 🧾 **Manifiesto por sesión**: origen, offset, inode y SHA-256 de cada archivo rescatado (cadena de custodia).
- 📅 **Timeline forense** (creación/modificación/acceso/borrado) exportable a CSV.
- 🕳 **Slack space**, 🔎 **keywords en crudo**, 📄 **Office/PDF ocultos**, 🌙 **hiberfil.sys**.
- 🔐 **Detección de cifrado**: LUKS1/2 (versión, cifrado, slots), BitLocker, heurística VeraCrypt + mapa de entropía.
- 🖼 **Análisis de imágenes**: dimensiones y perceptual-hash sin dependencias nativas.

### Borrado seguro
- 🔥 Métodos **NIST 800-88 Clear (zero)**, **DoD 5220.22-M**, **CSPRNG** y **Gutmann (35)**.
- ✔ **Verificación por muestreo** post-borrado y **certificado HTML** auditable.
- 🧽 **wipe-free**: limpia solo el espacio libre de particiones montadas.
- 🛡 **Alertas de seguridad**: frase de confirmación escrita, clasificación de riesgo
  (sistema/interno/extraíble), bloqueo de discos del sistema, lock exclusivo y desmontaje seguro.

### Interfaz
- 🌑 **TUI dark-glass** (Textual): pestañas Panel · Recuperar · Analizar · Borrar · Registro,
  progreso en vivo y diálogos de confirmación.
- ⌨️ **CLI completa** (Rich): los mismos 12 comandos con tablas y barras de progreso.
- 🌐 **Web oficial** (React + Vite + Tailwind) en GitHub Pages: detección de SO y
  descarga automática desde GitHub Releases.

## 🔬 Calidad
- 52 tests automatizados sobre filesystems reales (mkfs ext4/FAT32/NTFS).
- Probado sobre disco físico secundario de 10 GB: recuperación de borrados, borrado
  verificado byte a byte, y empaquetado .deb con desinstalación sin residuos.

## ⚖️ Uso responsable
Solo en discos propios o con autorización explícita.
