# 🜲 NyxRecover

> **Recuperación forense de datos borrados + borrado seguro certificado.**
> Gratis, open source, y con más funciones que muchas herramientas de pago.

NyxRecover explora discos duros, SSD y particiones para **rescatar archivos que fueron eliminados** —porque los datos rara vez desaparecen de verdad— reconstruyéndolos de forma íntegra. Y cuando necesitas lo contrario, **borra el medio con estándares NIST/DoD** y emite un certificado verificable. Todo con una TUI oscura con estética *glass* y una CLI completa.

![tests](https://img.shields.io/badge/tests-52%20passed-brightgreen) ![plataformas](https://img.shields.io/badge/OS-Linux%20%7C%20Windows%20%7C%20macOS-blueviolet) ![licencia](https://img.shields.io/badge/license-GPL--3.0-blue) ![precio](https://img.shields.io/badge/precio-0%20€-success)

---

## ✨ Funciones

### 🧲 Extracción de datos "borrados" (lo principal)
| Función | Qué hace |
|---|---|
| **Recuperación inteligente** | Parsers de filesystem (ext2/3/4, FAT12/16/32, NTFS) + carving por firmas, combinados |
| **Carving por firmas** | 22 familias fiables (JPG, PNG, GIF, PDF, ZIP/Office, 7z, RAR, GZip, XZ, BZip2, SQLite, ELF, MP4, MKV, FLAC, OGG, ISO, OLE, RTF, LUKS…) con detección de *footer* real |
| **Árbol del filesystem** | Recorre inodos/MFT/entradas FAT: ficheros vivos **y borrados**, con su ruta original |
| **Selección de rutas** | Recupera solo lo que quieras: `--paths "/documentos/contrasenas.txt"` |
| **Timeline forense** | Historial M/A/C/D por archivo, exportable a CSV |
| **Slack space** | Extrae los bytes ocultos tras el EOF de cada archivo |
| **Keywords en crudo** | Busca contraseñas/DNI/texto sobre el disco completo con contexto |
| **Docs ocultos** | Localiza y analiza OLE/Office y PDF (revisiones, JavaScript, adjuntos) |
| **Hibernación** | Analiza cabeceras de hiberfil.sys |
| **Detección de cifrado** | LUKS1/2 (cifrado/modo/slots), BitLocker, heurística VeraCrypt + mapa de entropía |
| **Análisis de imágenes** | Dimensiones, hashes SHA-256 y *perceptual hash* para encontrar duplicados |
| **Manifiesto + auditoría** | Cada archivo recuperado: origen, offset, inode, SHA-256; journal anti-manipulación |

### 🔥 Borrado seguro (lo destructivo, con redes de seguridad)
| Método | Estándar | Pasadas |
|---|---|---|
| `zero` | NIST SP 800-88 Rev.1 **Clear** | 1 (ceros verificados) |
| `dod5220` | US DoD 5220.22-M | 3 |
| `random` | CSPRNG (`secrets`) | 1–7 |
| `gutmann` | Peter Gutmann | 35 |

**Redes de seguridad**: frase de confirmación escrita (`ELIMINAR SDB`), clasificación de riesgo del dispositivo, bloqueo del sistema denegado, lock exclusivo (flock), desmontaje seguro automático, verificación por muestreo post-borrado y **certificado HTML** con el resultado.

Extras: `wipe-free` (limpia solo el espacio libre de una partición montada) y borrado individual de archivos.

---

## 🚀 Instalación

### Linux (Debian/Ubuntu/Kali) — .deb
```bash
sudo dpkg -i nyxrecover_*_all.deb
sudo nyx-tui        # interfaz interactiva
sudo nyx --help     # consola
```

### Windows — portable
Descarga `NyxRecover-*-windows-x64.zip`, descomprime y ejecuta `NyxRecover.exe`
(con `--cli` para modo consola). Sin instalación, sin registro.

### macOS
Descarga `NyxRecover-*-macos.zip`, `chmod +x NyxRecover` y ejecútalo con `sudo`.

### Desde código (cualquier plataforma)
```bash
git clone https://github.com/D1se0/nyxrecover.git
cd nyxrecover
./packaging/install.sh        # instala TODO en ~/.nyxrecover (sin basura)
# desinstalación limpia: ~/.nyxrecover/uninstall.sh
```

---

## 📖 Uso rápido (CLI)

```bash
sudo nyx devices                          # lista discos con tipo/riesgo
sudo nyx info /dev/sdb1                   # hardware + filesystem + cifrado
sudo nyx recover /dev/sdb1 -m smart       # recuperación inteligente
sudo nyx recover /dev/sdb1 -m fs --only-deleted --paths "/informe.docx"
sudo nyx timeline /dev/sdb1               # línea temporal + CSV
sudo nyx keywords /dev/sdb1 -k "password,DNI"
sudo nyx slack /dev/sdb1                  # espacio slack
sudo nyx cipher /dev/sdb1                 # ¿está cifrado?
sudo nyx wipe /dev/sdb1 --method zero     # borrado certificado (pide frase)
sudo nyx wipe-free /mnt/usb               # limpia espacio libre montado
nyx audit                                 # verifica la cadena de auditoría
sudo nyx report /dev/sdb1                 # informe HTML
```

La **TUI** (`nyx-tui`) ofrece lo mismo con paneles, progreso en vivo, pestañas
(Panel · Recuperar · Analizar · Borrar · Registro) y diálogos de confirmación.

## 🖥 Tecnologías

- **Núcleo 100% Python** (parsers ext/FAT/NTFS, carving, borrado): sin dependencias nativas.
- **TUI**: [Textual](https://github.com/Textualize/textual) — estética dark glass.
- **CLI**: [Rich](https://github.com/Textualize/rich).
- **Web**: React 19 + Vite + Tailwind 4, desplegada en GitHub Pages, con detección de SO y descarga directa desde GitHub Releases.

## 🧪 Calidad

- **52 tests pytest** sobre imágenes reales creadas con `mkfs.ext4/mkfs.vfat/mkfs.ntfs`.
- Probado sobre hardware real (VM con disco secundario de 10 GB): recuperación de archivos borrados, keywords a 71 MB/s, borrado NIST verificado byte a byte, instalación/desinstalación .deb sin residuos.

## ⚖️ Uso responsable

Solo en discos propios o con autorización explícita. La recuperación forense sin consentimiento puede ser ilegal en tu jurisdicción.

## 📄 Licencia

GPL-3.0 · NyxRecover Team
