import React from 'react'
import { useReveal } from './lib.jsx'
import { Section } from './ui.jsx'

/* ══════════════════════════════════════════════════════════════════
   Bloques de presentación
   ══════════════════════════════════════════════════════════════════ */

function Code({ children, title }) {
  const [copied, setCopied] = React.useState(false)
  const text = React.useMemo(() => React.Children.toArray(children).join(''), [children])
  function copy() {
    navigator.clipboard?.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1400)
    })
  }
  return (
    <div className="group relative my-4 overflow-hidden rounded-xl border border-slate-700/50 bg-[#0a0e1a]/90">
      <div className="flex items-center justify-between border-b border-slate-700/50 px-4 py-2">
        <span className="font-mono text-xs text-slate-500">{title || 'terminal'}</span>
        <button onClick={copy}
          className="rounded-md px-2 py-1 text-xs font-semibold text-slate-400 opacity-0 transition hover:bg-slate-700/50 hover:text-cyan-300 group-hover:opacity-100">
          {copied ? '✓ copiado' : '⧉ copiar'}
        </button>
      </div>
      <pre className="overflow-x-auto p-4 font-mono text-[13px] leading-6 text-emerald-300/95"><code>{children}</code></pre>
    </div>
  )
}

function Tip({ kind = 'info', children }) {
  const style = {
    info: 'border-cyan-400/30 bg-cyan-400/10 text-cyan-100/90',
    warn: 'border-amber-400/30 bg-amber-400/10 text-amber-100/90',
    danger: 'border-rose-400/30 bg-rose-400/10 text-rose-100/90',
    ok: 'border-emerald-400/30 bg-emerald-400/10 text-emerald-100/90',
  }[kind]
  const icon = { info: '💡', warn: '⚠️', danger: '🛑', ok: '✅' }[kind]
  return (
    <div className={`my-4 rounded-xl border p-4 text-sm leading-relaxed ${style}`}>
      <span className="mr-2">{icon}</span>{children}
    </div>
  )
}

function Arg({ name, desc, req }) {
  return (
    <li className="flex flex-col gap-0.5 border-b border-slate-700/30 py-2 last:border-0 sm:flex-row sm:gap-4">
      <code className="shrink-0 rounded bg-slate-800/80 px-2 py-0.5 font-mono text-xs text-cyan-300 sm:w-56">{name}</code>
      <span className="text-sm text-slate-300/85">{desc}{req && <span className="ml-1 text-rose-300/80">· obligatorio</span>}</span>
    </li>
  )
}

function Doc({ title, id, what, when, children }) {
  return (
    <details id={id} className="reveal group scroll-mt-24 rounded-2xl border border-slate-700/40 bg-slate-900/40 open:border-cyan-400/30 open:bg-slate-900/70">
      <summary className="flex cursor-pointer list-none items-center justify-between px-6 py-4">
        <span className="font-bold text-slate-100 group-open:text-cyan-300">{title}</span>
        <span className="text-slate-500 transition group-open:rotate-45">✚</span>
      </summary>
      <div className="px-6 pb-6">
        {what && <p className="mb-3 text-slate-300/90">{what}</p>}
        {when && <p className="mb-3 text-sm text-slate-400"><b className="text-slate-300">¿Cuándo usarlo?</b> {when}</p>}
        {children}
      </div>
    </details>
  )
}

/* ══════════════════════════════════════════════════════════════════
   Datos de la documentación
   ══════════════════════════════════════════════════════════════════ */

const CLI = [
  {
    id: 'devices', title: '🖥 nyx devices — inventario de discos',
    what: 'Enumera todos los discos y particiones detectados con su tipo, tamaño, modelo, bus, número de serie y clasificación de riesgo (sistema / extraíble). Es SIEMPRE el primer comando que debes ejecutar para identificar el nodo exacto del dispositivo a tratar.',
    when: 'Antes de cualquier operación: necesitas el nodo (/dev/sdb, /dev/sdb1…) para el resto de comandos.',
    code: `$ sudo nyx devices
🜲 NyxRecover v1.0.0 — Recuperación forense y borrado certificado

                    ┌ NyxRecover — dispositivos ┐
│ Nodo        │ Tipo   │ Tamaño │ Modelo            │ Bus  │ Serie        │ Particiones │
│ 🖥 /dev/sda │ system │ 64 GB  │ VMware Virtual    │ sata │ 000000000000 │ sda1…sda3   │
│ 🔌 /dev/sdb │ remov. │ 9.8 GB │ VMware Virtual    │ usb  │ 000000000002 │ sdb1        │`,
    args: [['(sin argumentos)', 'Lista todos los discos con sus particiones y clasifica cada uno por riesgo.']],
    tips: [<Tip key="1" kind="info">El icono indica el riesgo: 🖥 disco del sistema (bloqueado para borrado), 🔌 extraíble, 💾 disco interno no montado.</Tip>],
  },
  {
    id: 'info', title: '🔎 nyx info &lt;disco&gt; — radiografía completa',
    what: 'Ficha técnica completa de un dispositivo: riesgo evaluado por la capa de seguridad, geometría (sectores, tamaño de bloque lógico/físico), datos SMART del fabricante y resumen del sistema de archivos de su primera partición (tipo, versión, tamaños de bloque/inodo, estado del journal…).',
    when: 'Para saber qué contiene un disco antes de tocarlo, verificar que un formateo dejó el FS sano, o coleccionar metadatos para un informe pericial.',
    code: `$ sudo nyx info /dev/sdb
╭─ Dispositivo ─────────────────────────────────────╮
│ /dev/sdb — removable · 9.8 GB                      │
│ modelo: VMware Virtual · serie: 000000000002       │
│ riesgo: BAJO (disco extraíble, sin sistema activo) │
╰────────────────────────────────────────────────────╯
╭─ Filesystem /dev/sdb1 ────────────────────────────╮
│ { "type": "ext4", "block_size": 4096, … }          │
╰────────────────────────────────────────────────────╯`,
    args: [['<disco>', 'Nodo del dispositivo, p. ej. /dev/sdb o una imagen .img.'], ['—', 'Muestra además hardware SMART y filesystem.']],
    tips: [<Tip key="1" kind="info">Funciona igual sobre una imagen de disco: <code>nyx info disco.img</code>. Todo el motor forense acepta tanto nodos de dispositivo como ficheros de imagen.</Tip>],
  },
  {
    id: 'recover', title: '🪄 nyx recover — recuperar archivos borrados',
    what: 'La función estrella. Combina dos técnicas: (1) parser de sistema de archivos, que reconstruye la estructura lógica (inodos/extents de ext4, cadenas FAT, registros MFT de NTFS) incluso de entradas marcadas como eliminadas, y (2) carving por firmas, que rastrea el disco byte a byte buscando cabeceras/final de archivo reales (JPEG, PNG, PDF, ZIP, Office, SQLite…) para rescatar datos aunque el filesystem ya no se acuerde de ellos.',
    when: 'Borrados accidentales (rm, mayús+supr, vaciar papelera), formateos, memorias USB con ficheros desaparecidos, o peritajes donde necesitas los datos aunque la tabla ya no los referencie.',
    code: `$ sudo nyx recover /dev/sdb1 -m smart -o recuperados
🜲 NyxRecover v1.0.0

recuperando ━━━━━━━━━━━━━━━━━━━━━━ 100.0% 0:01:42
╭─ Recuperación completada ─────────────────────────╮
│ ✔ 3 elementos · 1.8 MB                             │
│ sala: recuperados/sdb1-20260916-135544             │
│ manifiesto: …/manifest.json                        │
╰────────────────────────────────────────────────────╯

$ tree recuperados/sdb1-20260916-135544/
├── fs/                          # por parser del FS
│   └── perdidoclas.pdf          # reconstruido por extents
├── carve/                       # por firmas
│   ├── rec_0005187840.jpg
│   └── rec_0005197696.png
└── manifest.json                # hashes SHA-256 + offsets`,
    args: [
      ['<fuente>', 'Partición, disco o imagen: /dev/sdb1, /dev/sdb, disco.img'],
      ['-m, --mode <modo>', 'smart (recomendado): FS + carving · fs: solo estructura del filesystem · carve: solo firmas'],
      ['-o, --out <dir>', 'Carpeta destino (por defecto nyx_recuperados/). Se crea una subcarpeta de sesión con fecha.'],
      ['--only-deleted', 'Ignora archivos vivos; intenta solo los eliminados.'],
      ['--paths <rutas…>', 'Con -m fs: recupera únicamente esas rutas concretas.'],
      ['--min-size N', 'Carving: descarta hallazgos menores de N bytes (defecto 128).'],
    ],
    tips: [
      <Tip key="1" kind="ok">Cada sesión genera <code>manifest.json</code> con SHA-256, offset de origen y hora de cada archivo — la evidencia queda trazada desde el primer minuto.</Tip>,
      <Tip key="2" kind="warn">Empieza por <code>-m smart</code>. Si sabes que el filesystem quedó destruido (p. ej. disco reformateado a otro tipo), ve directo a <code>-m carve</code>. El <code>--only-deleted</code> es ideal para peritajes limpios.</Tip>,
      <Tip key="3" kind="danger">Escribe SIEMPRE la salida en OTRO disco que el origen. Si recuperas sobre el mismo disco, puedes sobrescribir justo los datos que buscas.</Tip>,
    ],
  },
  {
    id: 'timeline', title: '📅 nyx timeline — línea temporal forense',
    what: 'Reconstruye la historia del sistema de archivos: creación, modificación y borrado de cada archivo con marcas de tiempo reales (atime/mtime/ctime de ext, fechas FAT/NTFS). Exporta a CSV listo para anexar a un informe.',
    when: 'Investigaciones: «¿cuándo se creó este documento y cuándo se borró?» · verificar sospechas de manipulación · documentar la actividad de un disco antes de analizar su contenido.',
    code: `$ sudo nyx timeline /dev/sdb1 -o timeline.csv
╭─ Timeline (1204 eventos) ─────────────────────────╮
│ Fecha                │ T │ Acción     │ Ruta        │ Estado   │
│ 2026-09-16 13:52:01  │ f │ borrado    │ informe.pdf │ borrado  │
│ 2026-09-16 13:40:11  │ f │ modificado │ notas.txt   │ -        │
│ 2026-09-16 13:39:58  │ f │ creado     │ notas.txt   │ -        │
╰────────────────────────────────────────────────────╯
CSV → nyx_informes/timeline-20260916-140210.csv`,
    args: [
      ['<fuente>', 'Partición o imagen con filesystem reconocido (ext/FAT/NTFS).'],
      ['-o <csv>', 'Ruta del CSV de salida (defecto: nyx_informes/timeline-*.csv).'],
      ['--limit N', 'Eventos a mostrar en pantalla (el CSV incluye todos).'],
    ],
    tips: [<Tip key="1" kind="info">Abre el CSV en Excel/LibreOffice y ordena por fecha — es el punto de partida clásico de cualquier peritaje.</Tip>],
  },
  {
    id: 'keywords', title: '🧵 nyx keywords — búsqueda en crudo',
    what: 'Busca texto arbitrario (ASCII, UTF-16 y UTF-8) en los bytes crudos del disco — incluye espacio libre, slack y zonas sin asignar. Devuelve coincidencias con offset exacto y contexto legible de ±60 bytes.',
    when: 'Localizar contraseñas, nombres, DNI, correos, «proyecto-x»… sin importar si el archivo que los contenía está borrado o el filesystem está roto.',
    code: `$ sudo nyx keywords /dev/sdb1 -k "NYX-SECRET,DNI,password" -o hits.json
╭─ 5 coincidencias ────────────────────────────────╮
│ Clave       │ Offset      │ Contexto                  │
│ NYX-SECRET  │ 0x51e00400  │ …CLAVE=NYX-SECRET-EXPED… │
│ password    │ 0x51e00490  │ …password=P@ssw0rd2026…  │
╰───────────────────────────────────────────────────╯
JSON → hits.json`,
    args: [
      ['<fuente>', 'Disco, partición o imagen.'],
      ['-k, --keywords', 'Lista separada por comas. Entrecomilla si contienen espacios.'],
      ['-o <json>', 'Volcar todas las coincidencias a JSON.'],
      ['--limit N', 'Coincidencias a mostrar en pantalla.'],
    ],
    tips: [
      <Tip key="1" kind="info">La búsqueda es insensible a mayúsculas y cubre las 3 codificaciones típicas (ASCII/UTF-8/UTF-16LE), por lo que encuentra texto tanto en ext4 como en NTFS/FAT.</Tip>,
      <Tip key="2" kind="warn">Si el disco está cifrado, las keywords solo pueden aparecer en cabeceras/metadatos. Ejecuta antes <code>nyx cipher</code> para comprobarlo.</Tip>,
    ],
  },
  {
    id: 'slack', title: '🕳 nyx slack — espacio slack',
    what: 'Los archivos nunca ocupan exactamente su tamaño: sobran bytes hasta el siguiente bloque. Ese «slack» conserva restos de los ficheros anteriores que ocuparon esos bloques. NyxRecover lo extrae archivo por archivo y te dice cuántos bytes no-cero contiene cada zona.',
    when: 'Peritajes avanzados: recuperar fragmentos de ficheros borrados que ningún explorador muestra, detectar ocultación de datos en slack.',
    code: `$ sudo nyx slack /dev/sdb1 -o slack_out
╭─ 🕳 Slack space ─────────────────────────────────╮
│ 3 zonas extraídas → slack_out (0.4s)              │
╰───────────────────────────────────────────────────╯
  ./informe.pdf · 2048B · no-cero: 512
  ./foto.jpg   · 3072B · no-cero: 2871`,
    args: [
      ['<fuente>', 'Partición con filesystem reconocido.'],
      ['-o <dir>', 'Carpeta destino de las zonas extraídas.'],
    ],
    tips: [<Tip key="1" kind="info">Las zonas con <code>no-cero: 0</code> solo contienen ceros — nada que rescatar ahí. Prioriza las de mayor conteo.</Tip>],
  },
  {
    id: 'cipher', title: '🔐 nyx cipher — detectar cifrado y entropía',
    what: 'Identifica volúmenes cifrados (LUKS1/LUKS2 por su cabecera mágica, BitLocker por su BDE) y aplica heurística de entropía de Shannon para sospechar VeraCrypt/TrueCrypt. Dibuja un mapa de entropía del disco en barras ASCII.',
    when: 'Antes de intentar una recuperación: si el disco está cifrado, el carving no encontrará ficheros «normales» · en peritajes, para documentar la presencia de cifrado.',
    code: `$ sudo nyx cipher /dev/sdb1
╭─ Detección de cifrado ───────────────────────────╮
│ { "luks": false, "bitlocker": false, "veracrypt":  │
│   false, "entropy_mean": 0.08, "zeroed": true }    │
╰───────────────────────────────────────────────────╯
entropía: ▁▁▁▁▁▂▁▁▁▁▁▁▁▁▁▁▂▁▁▁▁▁▁▁▁▁`,
    args: [['<fuente>', 'Disco, partición o imagen.']],
    tips: [
      <Tip key="1" kind="info">Barras bajas (▁▂) = ceros/vacíos · barras altas (█) = datos comprimidos o cifrados. Un disco «vacío» con entropía máxima en toda su superficie es la firma típica de un contenedor cifrado.</Tip>,
    ],
  },
  {
    id: 'wipe', title: '🔥 nyx wipe — borrado IRREVERSIBLE',
    what: 'Sobrescribe la totalidad del dispositivo para que ningún dato sea recuperable, con 4 estándares a elegir, verificación posterior por muestreo y emisión de un certificado HTML auditable con método, pasadas, duración, errores y resultado de verificación.',
    when: 'Vender/regalar/reciclar un disco, devolver equipo, cumplir políticas de destrucción de datos (RGPD, ISO 27001…).',
    code: `$ sudo nyx wipe /dev/sdb --method zero
╭─ ⚠ OPERACIÓN IRREVERSIBLE ───────────────────────╮
│ RIESGO: BAJO — disco extraíble, sin sistema activo │
│ TODOS los datos se perderán PARA SIEMPRE.          │
╰───────────────────────────────────────────────────╯
Escribe ELIMINAR SDB para confirmar: ELIMINAR SDB
borrando ━━━━━━━━━━━━━━━━━━━━━━ 100.0% 0:00:07
╭─ Éxito ──────────────────────────────────────────╮
│ ✔ Borrado completado · verificado: True            │
│ Certificado → nyx_informes/certificado-….html      │
╰───────────────────────────────────────────────────╯`,
    args: [
      ['<disco>', 'Disco completo (recomendado) o partición.'],
      ['--method', 'zero: ceros — NIST SP 800-88 Clear, rápido y suficiente para casi todo · dod5220: 3 pasadas del estándar militar DoD 5220.22-M · random: una pasada CSPRNG · gutmann: 35 pasadas clásicas (muy lento, histórico).'],
      ['--no-verify', 'Salta la verificación por muestreo (no recomendado).'],
      ['--cert <fichero>', 'Ruta alternativa del certificado HTML.'],
    ],
    tips: [
      <Tip key="1" kind="danger">La confirmación exige escribir la frase literal (p. ej. ELIMINAR SDB). La capa de seguridad REFUSA automáticamente borrar el disco del sistema, discos con partición montada activa de sistema o dispositivos en uso.</Tip>,
      <Tip key="2" kind="warn">En SSD modernos <code>zero</code> (NIST Clear) es suficiente y el más sano para la unidad; Gutmann es un estándar de los 90 pensado para discos magnéticos antiguos.</Tip>,
    ],
  },
  {
    id: 'wipe-free', title: '🧽 nyx wipe-free — limpiar espacio libre',
    what: 'Sobrescribe ÚNICAMENTE el espacio libre de una partición montada: tus archivos actuales quedan intactos y todos los ya borrados pasan a ser irrecuperables.',
    when: 'Quitar rastros de ficheros eliminados sin borrar lo que sigue usando · «limpiar» un portátil antes de entregarlo sin tener que reinstalar nada.',
    code: `$ sudo nyx wipe-free /mnt/disco10
╭─ Confirmación ───────────────────────────────────╮
│ 🧽 Se sobrescribirá el espacio libre de            │
│    /mnt/disco10. Los ficheros borrados dejarán     │
│    de ser recuperables.                            │
╰───────────────────────────────────────────────────╯
¿Continuar? (si/NO): si
✔ 9.30 GB sobrescritos`,
    args: [['<montaje>', 'Punto de montaje de la partición (no el nodo /dev).']],
    tips: [<Tip key="1" kind="warn">Tras el wipe-free, cualquier borrado ANTERIOR deja de ser recuperable — ejecuta primero <code>recover</code> si necesitabas rescatar algo.</Tip>],
  },
  {
    id: 'audit', title: '🧾 nyx audit — cadena de custodia',
    what: 'Cada operación (scan, recover, wipe…) queda registrada en un journal diario con una cadena de hashes SHA-256: cada línea incluye el hash de la anterior. <code>nyx audit</code> verifica la cadena completa y detecta cualquier alteración.',
    when: 'Peritajes formales: demostrar que el registro de operaciones no fue manipulado · auditar qué se hizo y cuándo en un equipo.',
    code: `$ nyx audit
✔ Cadena íntegra · 37 eventos · ~/.nyxrecover/audit/2026-09-16.jsonl

# (si alguien edita el journal…)
$ nyx audit
✗ Cadena ALTERADA en línea 14  →  exit code 1`,
    args: [['(sin argumentos)', 'Verifica TODOS los journals del equipo.']],
    tips: [<Tip key="1" kind="ok">Integra el <code>nyx audit</code> en tu cierre de peritaje: un «✔ Cadena íntegra» es evidencia de que el historial está intacto.</Tip>],
  },
  {
    id: 'report', title: '📄 nyx report — informe HTML',
    what: 'Genera un informe autocontenido (un solo .html) con la ficha del dispositivo, evaluación de riesgo y sesiones de auditoría. Los informes de borrado (certificados) usan el mismo generador.',
    when: 'Entregables para clientes, documentación de auditoría, anexos de peritaje.',
    code: `$ sudo nyx report /dev/sdb -o informe.html
✔ Informe → nyx_informes/informe-20260916-142030.html

# Un solo fichero HTML, autocontenido, imprimible a PDF desde el navegador.`,
    args: [
      ['<disco>', 'Dispositivo sobre el que informar.'],
      ['-o <fichero>', 'Ruta del HTML de salida.'],
    ],
    tips: [<Tip key="1" kind="info">El certificado generado por <code>nyx wipe</code> se imprime a PDF (Ctrl+P) para adjuntarlo a contratos o entregas de equipos.</Tip>],
  },
]

const FAQ = [
  ['¿Es realmente gratis?', 'Sí, 100 %: código abierto GPL v3, sin licencias, cuentas ni telemetría. Sin versión «pro» bloqueada — todo lo que ves funciona.'],
  ['¿Puede recuperar un disco formateado?', 'En la mayoría de los casos sí: el formateo rápido reescribe las tablas, no los datos. Usa -m carve para escanear por firmas aunque el filesystem esté completamente reconstruido.'],
  ['¿Y si el disco está cifrado (BitLocker/LUKS)?', 'NyxRecover lo detecta (nyx cipher) pero no descifra: sin la contraseña el contenido es matemáticamente irrecuperable. La detección te ahorra horas de escaneos inútiles.'],
  ['¿Qué método de borrado elijo?', 'Para cualquier uso normal: zero (NIST 800-88 Clear) — es rápido y suficiente. dod5220 si tu política exige estándar militar. gutmann solo si te lo pide un procedimiento antiguo (y asume el tiempo).'],
  ['¿Por qué necesita sudo/administrador?', 'Porque lee y escribe el dispositivo a nivel de bloque, saltándose el sistema operativo — así es como puede ver datos «eliminados». Sin esos permisos, el SO bloquearía el acceso crudo.'],
  ['¿El borrado garantiza el 100 %?', 'El certificado incluye la verificación por muestreo del resultado. En SSD con wear-leveling, la garantía absoluta solo la ofrece el Secure Erase del firmware (hdparm --security-erase) o el cifrado de disco desde el primer día + destrucción de claves.'],
  ['¿Funciona en SSD y NVMe?', 'Sí para leer y recuperar. Para borrados en NVMe, si puedes, usa además nvme format. En hardware moderno el «cero» a nivel de bloque sigue siendo efectivo porque el SO lo envía a todas las celdas mapeadas.'],
  ['¿Cuánto tarda una recuperación?', 'El escaneo por firmas corre a ~71 MB/s: un disco de 1 TB ≈ 4 h; los 10 GB del ejemplo ≈ 2 min. La recuperación por filesystem es mucho más rápida porque no recorre todo el disco.'],
  ['¿De dónde sale el instalador que descarga la web?', 'Directamente de GitHub Releases de este repo: la web consulta la API pública de GitHub y enlaza el binario de tu sistema operativo. No hay servidores intermedios ni instaladores modificados.'],
]

/* ══════════════════════════════════════════════════════════════════
   Sección raíz
   ══════════════════════════════════════════════════════════════════ */

export default function Docs() {
  useReveal()
  return (
    <Section id="docs" kicker="Documentación completa" title={<>Documentación<br /><span className="gradient-text">de la A a la Z.</span></>}>
      <p className="reveal -mt-6 mb-8 max-w-3xl text-slate-300/90">
        Todo lo que NyxRecover sabe hacer, explicado para cualquiera: qué hace cada opción,
        cuándo usarla y con ejemplos reales listos para copiar. Los bloques se despliegan
        al pulsar sobre ellos.
      </p>

      {/* ── Empezar en 1 minuto ── */}
      <div className="reveal mb-10 grid gap-5 lg:grid-cols-3">
        <div className="glass rounded-2xl p-6">
          <h3 className="mb-3 font-bold text-cyan-300">1 · Tu primer rescate</h3>
          <Code title="recuperar lo borrado">{`# ver qué discos hay
sudo nyx devices

# recuperar del USB (partición sdb1)
sudo nyx recover /dev/sdb1 -m smart`}</Code>
          <p className="text-sm text-slate-400">Los archivos rescatados quedan en <code>nyx_recuperados/…</code> con manifiesto SHA-256.</p>
        </div>
        <div className="glass rounded-2xl p-6">
          <h3 className="mb-3 font-bold text-violet-300">2 · Con interfaz gráfica</h3>
          <Code title="TUI interactiva">{`sudo nyx-tui

# ⟲ Recuperar → eliges disco y modo
# 🔍 Analizar  → timeline/keywords/slack
# 🔥 Borrar    → confirmación por frase`}</Code>
          <p className="text-sm text-slate-400">5 pestañas: Panel, Recuperar, Analizar, Borrar y Registro con todo lo que pasa.</p>
        </div>
        <div className="glass rounded-2xl p-6">
          <h3 className="mb-3 font-bold text-rose-300">3 · Despedir un disco</h3>
          <Code title="borrado certificado">{`sudo nyx wipe /dev/sdb --method zero

# escribe ELIMINAR SDB para confirmar
# verifica y genera el certificado HTML`}</Code>
          <p className="text-sm text-slate-400">El disco queda con bytes a cero reales, verificado y documentado.</p>
        </div>
      </div>

      {/* ── La interfaz gráfica (TUI) ── */}
      <h3 className="reveal mb-4 mt-12 text-2xl font-black">La interfaz gráfica (TUI)</h3>
      <p className="reveal mb-4 max-w-3xl text-slate-300/90">
        Ejecuta <code className="rounded bg-slate-800 px-2 py-0.5 text-cyan-300">sudo nyx-tui</code> y verás
        un panel oscuro con 5 pestañas. Todo lo de la CLI está ahí, con barras de progreso en vivo,
        evaluación de riesgo en el momento y alertas antes de cada acción destructiva.
      </p>
      <div className="reveal mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {[
          ['◧ Panel', 'Lista de dispositivos con su riesgo, tarjeta de detalles del seleccionado y registro de actividad en vivo.'],
          ['⟲ Recuperar', 'Elige disco, modo (smart/fs/carve), carpeta destino y lanza la recuperación con progreso en tiempo real.'],
          ['🔍 Analizar', 'Escaneo de firmas, timeline forense, búsqueda de keywords y detección de cifrado — todo desde un menú.'],
          ['🔥 Borrar', 'Selección de método (zero/DoD/random/Gutmann), evaluación de riesgo, frase de confirmación escrita y certificado.'],
          ['▤ Registro', 'Todo lo que ha pasado: cada operación, cada alerta, cada resultado — con la cadena de auditoría al día.'],
        ].map(([t, d]) => (
          <div key={t} className="glass rounded-2xl p-5">
            <p className="font-mono font-bold text-cyan-300">{t}</p>
            <p className="mt-2 text-sm text-slate-300/85">{d}</p>
          </div>
        ))}
      </div>

      {/* ── Los 12 comandos CLI ── */}
      <h3 className="reveal mb-4 mt-12 text-2xl font-black">Los 12 comandos de la CLI</h3>
      <p className="reveal mb-6 max-w-3xl text-slate-300/90">
        Toda la potencia también en terminal — ideal para scripts, servidores y peritajes reproducibles.
      </p>
      <div className="reveal space-y-4">
        {CLI.map(c => (
          <Doc key={c.id} id={`cli-${c.id}`} title={c.title} what={c.what} when={c.when}>
            <Code>{c.code}</Code>
            <p className="mb-2 mt-5 text-xs font-bold uppercase tracking-widest text-slate-500">Argumentos</p>
            <ul>{c.args.map(([n, d]) => <Arg key={n} name={n} desc={d} />)}</ul>
            {c.tips}
          </Doc>
        ))}
      </div>

      {/* ── Formatos y capacidades ── */}
      <h3 className="reveal mb-4 mt-12 text-2xl font-black">Formatos y capacidades</h3>
      <div className="reveal grid gap-5 md:grid-cols-2">
        <div className="glass rounded-2xl p-6">
          <h4 className="mb-3 font-bold text-cyan-300">Sistemas de archivos (parser lógico)</h4>
          <ul className="space-y-2 text-sm text-slate-300/85">
            <li>🐧 <b>ext2 / ext3 / ext4</b> — superbloque, grupos de bloques, inodos, extents, entradas de directorio eliminadas, journal</li>
            <li>🪟 <b>NTFS</b> — MFT completa, atributos residentes y no residentes, runs de datos, $I30</li>
            <li>💾 <b>FAT12 / FAT16 / FAT32</b> — BPB, cadenas de clusters, entradas LFN y borradas</li>
          </ul>
        </div>
        <div className="glass rounded-2xl p-6">
          <h4 className="mb-3 font-bold text-violet-300">Familias de firmas para carving (45+)</h4>
          <p className="text-sm text-slate-300/85">
            JPEG, PNG, GIF, BMP, WebP, PDF, ZIP, RAR, 7z, gzip, Office (docx/xlsx/pptx OLE+OOXML),
            MP4, MOV, AVI, MKV, MP3, WAV, FLAC, OGG, SQLite, ELF, LNK, PCAP, LUKS, BitLocker,
            VeraCrypt, PGP… con footers reales y validación para minimizar falsos positivos.
          </p>
        </div>
        <div className="glass rounded-2xl p-6">
          <h4 className="mb-3 font-bold text-emerald-300">Fuentes de datos admitidas</h4>
          <ul className="space-y-2 text-sm text-slate-300/85">
            <li>Discos y particiones (<code>/dev/sdX</code>, <code>/dev/nvme0n1pN</code>, <code>/dev/disk*</code>)</li>
            <li>Imágenes de disco crudas (<code>.img</code>, <code>.dd</code>, <code>.raw</code>)</li>
            <li>USB, tarjetas SD y cualquier dispositivo de bloque</li>
          </ul>
        </div>
        <div className="glass rounded-2xl p-6">
          <h4 className="mb-3 font-bold text-amber-300">Cifrado detectado</h4>
          <ul className="space-y-2 text-sm text-slate-300/85">
            <li><b>LUKS1 / LUKS2</b> — por cabecera mágica</li>
            <li><b>BitLocker</b> — por tabla BDE</li>
            <li><b>VeraCrypt / TrueCrypt</b> — heurística de entropía</li>
            <li>Mapa visual de entropía de toda la superficie</li>
          </ul>
        </div>
      </div>

      {/* ── Qué queda dónde ── */}
      <h3 className="reveal mb-4 mt-12 text-2xl font-black">¿Dónde queda todo? (cero basura)</h3>
      <div className="reveal glass rounded-2xl p-6">
        <ul className="space-y-2 font-mono text-sm text-slate-300/85">
          <li><span className="text-cyan-300">~/nyx_recuperados/</span> — archivos rescatados, una sala por sesión</li>
          <li><span className="text-violet-300">~/nyx_informes/</span> — timeline CSV, certificados de borrado e informes HTML</li>
          <li><span className="text-emerald-300">~/.nyxrecover/</span> — journals de auditoría (y la app entera si instalaste con install.sh)</li>
          <li><span className="text-slate-500">desinstalador:</span> <code>sudo dpkg -r nyxrecover</code> o <code>~/.nyxrecover/uninstall.sh</code> — elimina TODO, sin restos</li>
        </ul>
      </div>

      {/* ── Flujos de trabajo ── */}
      <h3 className="reveal mb-4 mt-12 text-2xl font-black">Flujos de trabajo completos</h3>
      <div className="reveal grid gap-5 lg:grid-cols-2">
        <div className="glass rounded-2xl p-6">
          <h4 className="mb-3 font-bold text-cyan-300">Caso: «borré las fotos de la USB»</h4>
          <Code title="paso a paso">{`# 1. NO escribas nada en la USB desde ahora
sudo nyx devices                 # localízala (p.ej. sdb)
sudo nyx recover /dev/sdb1 -m smart
# 2. Revisa nyx_recuperados/carve/
# 3. ¿Falta algo? prueba solo carving:
sudo nyx recover /dev/sdb1 -m carve --min-size 64`}</Code>
        </div>
        <div className="glass rounded-2xl p-6">
          <h4 className="mb-3 font-bold text-rose-300">Caso: «vendo mi portátil»</h4>
          <Code title="paso a paso">{`# 1. Copia lo que necesites
# 2. Limpia rastros de lo borrado (sin perder nada):
sudo nyx wipe-free /home
# 3. O destruye TODO el disco si va entero:
sudo nyx wipe /dev/sda --method zero
# 4. Guarda el certificado HTML que genera`}</Code>
        </div>
        <div className="glass rounded-2xl p-6">
          <h4 className="mb-3 font-bold text-violet-300">Caso: «peritaje con garantías»</h4>
          <Code title="paso a paso">{`# imagen primero (trabaja sobre la copia):
sudo dd if=/dev/sdb of=evidencia.img bs=4M status=progress
sudo nyx info evidencia.img
sudo nyx timeline evidencia.img -o t.csv
sudo nyx keywords evidencia.img -k "dni,email"
sudo nyx recover evidencia.img -m smart
nyx audit                        # cadena íntegra ✔`}</Code>
        </div>
        <div className="glass rounded-2xl p-6">
          <h4 className="mb-3 font-bold text-emerald-300">Caso: «¿me han cifrado el disco?»</h4>
          <Code title="paso a paso">{`sudo nyx cipher /dev/sdb1
# → ¿LUKS? ¿BitLocker? ¿entropía sospechosa?
# con entropía alta en TODO el disco:
#   contenedor cifrado — sin clave, sin rescate
# con entropía baja: disco normal, sigue el plan:
sudo nyx recover /dev/sdb1 -m smart`}</Code>
        </div>
      </div>

      {/* ── FAQ ── */}
      <h3 className="reveal mb-6 mt-12 text-2xl font-black">Preguntas frecuentes</h3>
      <div className="reveal space-y-3">
        {FAQ.map(([q, a]) => (
          <details key={q} className="group rounded-xl border border-slate-700/40 bg-slate-900/40 open:border-cyan-400/30">
            <summary className="flex cursor-pointer list-none items-center justify-between px-5 py-3.5 font-semibold text-slate-200 group-open:text-cyan-300">
              {q}<span className="text-slate-500 transition group-open:rotate-45">✚</span>
            </summary>
            <p className="px-5 pb-4 text-sm leading-relaxed text-slate-300/85">{a}</p>
          </details>
        ))}
      </div>
    </Section>
  )
}
