# 🜲 NyxRecover v1.0.0 «Fénix»

> **Recuperación forense de datos borrados + borrado seguro certificado — gratis, open source y sin telemetría.**

NyxRecover nace de una idea simple: **lo que borras de un disco nunca se va del todo**. Mientras los bytes sigan en la superficie, se pueden rescatar. Esta suite los localiza, los reconstruye íntegros y los entrega con trazabilidad forense. Y cuando lo que quieres es justo lo contrario — que desaparezcan *para siempre* — los destruye con estándares NIST/DoD y emite un certificado verificable.

---

## ✨ Qué hace

### 🪄 Recuperación de datos eliminados
- **Modo inteligente (`smart`)**: combina parser de filesystem + carving por firmas.
- **Parsers propios** de **ext2/ext3/ext4** (superbloque, grupos, inodos, extents, entradas borradas), **NTFS** (MFT, atributos residentes/no residentes, runs) y **FAT12/16/32** (BPB, cadenas de clusters, LFN).
- **Carving por firmas** con 45+ familias (JPEG, PNG, GIF, BMP, WebP, PDF, ZIP, RAR, 7z, gzip, Office OLE+OOXML, MP4, MOV, AVI, MKV, MP3, WAV, FLAC, OGG, SQLite, ELF, LNK, PCAP…) con footers reales y validación anti-basura.
- Acepta **discos, particiones, USB, SD e imágenes crudas** (`.img`, `.dd`, `.raw`).
- Velocidad de escaneo **~71 MB/s** (10 GB ≈ 2 minutos).

### 🔬 Análisis forense
- **Timeline** completa: creación, modificación y borrado de cada archivo, exportable a CSV.
- **Keywords** en crudo (ASCII/UTF-8/UTF-16) con offsets exactos y contexto — encuentra texto aunque el archivo esté borrado.
- **Slack space**: extrae los bytes ocultos tras el final lógico de cada archivo.
- **Detección de cifrado**: LUKS1/2, BitLocker y heurística de entropía para VeraCrypt/TrueCrypt, con mapa de entropía visual del disco.

### 🔥 Borrado seguro certificado
- **4 estándares**: `zero` (NIST SP 800-88 Clear), `dod5220` (DoD 5220.22-M), `random` (CSPRNG) y `gutmann` (35 pasadas).
- **Verificación por muestreo** tras el borrado + **certificado HTML** auditable.
- **`wipe-free`**: sobrescribe solo el espacio libre — tus archivos intactos, los borrados irrecuperables.

### 🛡 Seguridad ante todo
- **Frase de confirmación escrita** generada por dispositivo antes de cualquier borrado.
- **Clasificación de riesgo** (sistema / interno / extraíble) y **bloqueo automático** del disco de sistema.
- **Lock exclusivo** del dispositivo durante la operación y **desmontaje seguro** previo.

### 🧾 Cadena de custodia
- **Journal diario** con **hash-chain SHA-256**: cualquier manipulación del registro se detecta con `nyx audit`.
- **Manifiesto por sesión** de recuperación con SHA-256, offset de origen y marca temporal de cada archivo.

### 🖥 Dos interfaces
- **TUI dark-glass** (5 pestañas: Panel, Recuperar, Analizar, Borrar, Registro) con progreso en vivo.
- **CLI completa** de 12 comandos, ideal para scripts y peritajes reproducibles.

---

## 📦 Descargas

| Plataforma | Archivo | Tamaño | SHA-256 |
|---|---|---|---|
| 🐧 Linux (Debian/Ubuntu/Kali) | `nyxrecover_1.0.0_all.deb` | 45,8 KB | `64d514d84fe326dec808d183ee28d10dacc5eb9727a7f19b15e4796280efc437` |
| 🪟 Windows x64 | `NyxRecover-v1.0.0-windows-x64.zip` | 14,3 MB | `daa6a4c64e9a5a2ec9e109c9b15073e5e146946939d2270c0a8152bd51be89d7` |
| 🍎 macOS | `NyxRecover-v1.0.0-macos.zip` | 13,5 MB | `6485cb3dcac2249b14f82ecea5dc9b47e5306ab0dca5684e61e73a9e4204aaa9` |

> Comprueba el hash de tu descarga con `sha256sum <archivo>` (Linux/macOS) o `Get-FileHash <archivo> -Algorithm SHA256` (PowerShell).

---

## 🚀 Primeros pasos

**Linux**
```bash
sudo dpkg -i nyxrecover_1.0.0_all.deb
sudo nyx-tui          # interfaz gráfica
sudo nyx --help       # línea de comandos
```

**Windows**
```
1. Descomprime NyxRecover-v1.0.0-windows-x64.zip
2. Ejecuta NyxRecover.exe (como Administrador para discos físicos)
3. Modo consola: NyxRecover.exe --cli devices
```

**macOS**
```bash
chmod +x NyxRecover
sudo ./NyxRecover --cli recover /dev/disk4s1
```

**Tu primer rescate en 30 segundos**
```bash
sudo nyx devices                     # 1. ¿qué discos hay?
sudo nyx recover /dev/sdb1 -m smart  # 2. recupera lo borrado
sudo nyx timeline /dev/sdb1          # 3. ¿cuándo se borró todo?
```

---

## 📚 Documentación

Guía completa, comando a comando y con ejemplos listos para copiar:
**https://d1se0.github.io/nyxrecover/#docs**

---

## ✅ Calidad

- **52 tests automatizados** en verde sobre filesystems reales (ext4, FAT32 y NTFS creados con mkfs).
- Probado en escenario real: evidencia borrada → recuperada por carving; borrado NIST verificado byte a byte con herramientas independientes; desinstalación del `.deb` sin dejar un solo fichero.

## 📄 Licencia y uso responsable

GPL v3. Usa NyxRecover **solo en discos propios o con autorización explícita** — recuperar datos ajenos sin permiso es ilegal en la mayoría de jurisdicciones.

---

*«Lo que borraste nunca se fue de verdad.»* 🜲
