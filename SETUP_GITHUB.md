# 🚀 Guía de publicación en GitHub — NyxRecover

Sigue estos pasos **en orden**. Tiempo total: ~5 minutos.

---

## 1. Crear el repositorio

El nombre recomendado es **`nyxrecover`** (en minúsculas; así lo espera la web y los instaladores):

> 👉 <https://github.com/new>
>
> - **Repository name:** `nyxrecover`
> - **Description:** `🜲 Recuperación forense de datos borrados y borrado seguro — gratis y open source`
> - Visibilidad: **Public** (necesario para GitHub Pages gratuito y Releases públicas)
> - ⚠️ **NO** marques "Add a README" ni "Add .gitignore" (ya los tenemos)

## 2. Añadir la clave SSH

Copia esta clave pública en **GitHub → Settings → SSH and GPG keys → New SSH key**:

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIKxixD9gOCvxX4wWqQgFp3fDuerUiiY+rdLHu+m5M82f kali-nyxrecover
```

## 3. Conectar y subir

Sustituye `D1se0` por tu usuario de GitHub en estos comandos y ejecútalos
desde la carpeta del proyecto (`~/Desktop/AppExtractDataAlmacenamiento`):

```bash
git init
git add -A
git commit -m "🜲 NyxRecover v1.0.0 — suite forense de recuperación y borrado seguro"

git branch -M main
git remote add origin git@github.com:D1se0/nyxrecover.git
git push -u origin main
```

> Después del primer push, actualiza estos 4 archivos con tu usuario real
> (busca-reescribe `D1se0/nyxrecover` → `D1se0/nyxrecover`):
> `nyx/nyxcore/version.py`, `web/src/lib.jsx`, `web/src/Hero.jsx`, `README.md`
> y haz `git push`. (O dímelo y lo hago yo.)

## 4. Activar GitHub Pages (la web)

1. En el repo: **Settings → Pages**
2. **Source:** `GitHub Actions`
3. Listo: el workflow `pages.yml` ya incluido despliega la web en cada push a `main`.
   Quedará en: `https://D1se0.github.io/nyxrecover/`

## 5. Crear la Release (genera .deb, .exe y .zip automáticos)

Los builds para Windows y macOS los compila GitHub en la nube. Solo tienes que:

```bash
git tag v1.0.0
git push origin v1.0.0
```

En 5–10 minutos aparecerá la release **v1.0.0 «Fénix»** en
`https://github.com/D1se0/nyxrecover/releases` con:

- `nyxrecover_1.0.0_all.deb` (Linux)
- `NyxRecover-v1.0.0-windows-x64.zip` (Windows portable .exe)
- `NyxRecover-v1.0.0-macos.zip` (macOS)

### Título y descripción de la release

Ve a **Releases → edita la release generada** y pon:

- **Title:** `🜲 v1.0.0 «Fénix» — Recuperación forense + borrado certificado`
- **Description:** pega el contenido de [`RELEASE_NOTES.md`](RELEASE_NOTES.md)
- Marca ✅ **Set as the latest release**

> Alternativa por terminal (si tienes `gh`): `gh release create v1.0.0 dist/* --title "..." --notes-file RELEASE_NOTES.md`

## 6. Comprobar que todo quedó perfecto

| Comprobación | Dónde |
|---|---|
| Web publicada y con botón de descarga vivo | `https://D1se0.github.io/nyxrecover/` |
| Release con 3 binarios | pestaña **Releases** |
| Workflows en verde | pestaña **Actions** |
| Descarga del .deb funciona en una VM limpia | `sudo dpkg -i …` |

---

## 🔄 Flujo para futuras versiones

```bash
# 1. editar nyx/nyxcore/version.py → VERSION = "1.1.0"
# 2. commitear y:
git tag v1.1.0 && git push origin main v1.1.0
```
