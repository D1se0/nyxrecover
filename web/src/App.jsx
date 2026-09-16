import React from 'react'
import Hero from './Hero.jsx'
import { REPO, useReleases, useReveal, useReleases as useRel, assetFor } from './lib.jsx'

const FEATURES = [
  { icon: '🧠', title: 'Recuperación inteligente', color: 'cyan',
    desc: 'Combina parsers de filesystem (ext2/3/4, FAT12/16/32, NTFS) con carving por firmas. Elige entre modo inteligente, árbol completo o solo carving.' },
  { icon: '🪄', title: 'Carving por firmas', color: 'violet',
    desc: '45+ firmas (JPG, PNG, PDF, ZIP, SQLite, MP4, LUKS…). Detección de footer real y sanity-checks para no exportar basura. Rápido: ~71 MB/s.' },
  { icon: '📅', title: 'Timeline forense', color: 'emerald',
    desc: 'Reconstruye el historial: cuándo se creó, modificó y borró cada archivo. Exporta CSV listo para tu informe pericial.' },
  { icon: '🕳', title: 'Slack space', color: 'amber',
    desc: 'Extrae los bytes ocultos tras el final lógico de cada archivo — donde sobreviven fragmentos "borrados" que nadie más mira.' },
  { icon: '🔎', title: 'Búsqueda de keywords', color: 'sky',
    desc: 'Busca contraseñas, DNI, correos o texto arbitrario en crudo sobre el disco completo, con contexto y offsets exactos.' },
  { icon: '🔐', title: 'Detección de cifrado', color: 'rose',
    desc: 'Reconoce LUKS1/2, BitLocker y heurística de entropía para VeraCrypt/TrueCrypt. Mapa de entropía visual del disco entero.' },
  { icon: '🔥', title: 'Borrado certificado', color: 'red',
    desc: 'Ceros (NIST 800-88), DoD 5220.22-M, Gutmann 35 pasadas o CSPRNG. Verificación por muestreo y certificado HTML auditable.' },
  { icon: '🧾', title: 'Cadena de custodia', color: 'teal',
    desc: 'Journal diario con hash-chain SHA-256: cualquier manipulación del registro queda detectada. Manifiesto por sesión con hashes.' },
  { icon: '🧽', title: 'Limpieza de espacio libre', color: 'lime',
    desc: 'Sobrescribe solo el espacio libre de una partición montada: tus archivos intactos, los borrados irrecuperables.' },
]

const CMAP = {
  cyan: 'text-cyan-300 border-cyan-400/30 hover:shadow-cyan-400/20',
  violet: 'text-violet-300 border-violet-400/30 hover:shadow-violet-400/20',
  emerald: 'text-emerald-300 border-emerald-400/30 hover:shadow-emerald-400/20',
  amber: 'text-amber-300 border-amber-400/30 hover:shadow-amber-400/20',
  sky: 'text-sky-300 border-sky-400/30 hover:shadow-sky-400/20',
  rose: 'text-rose-300 border-rose-400/30 hover:shadow-rose-400/20',
  red: 'text-red-300 border-red-400/30 hover:shadow-red-400/20',
  teal: 'text-teal-300 border-teal-400/30 hover:shadow-teal-400/20',
  lime: 'text-lime-300 border-lime-400/30 hover:shadow-lime-400/20',
}

const INSTALL = {
  linux: {
    icon: '🐧', label: 'Linux (Debian/Ubuntu/Kali)',
    steps: [
      ['1', 'Descarga el .deb desde la última release (botón de arriba).'],
      ['2', 'Instala: sudo dpkg -i nyxrecover_*_all.deb (o doble clic).'],
      ['3', 'Lanza la interfaz: sudo nyx-tui — o la CLI: sudo nyx --help.'],
    ],
    note: 'También tienes ./packaging/install.sh para instalar en ~/.nyxrecover sin root.',
  },
  windows: {
    icon: '🪟', label: 'Windows',
    steps: [
      ['1', 'Descarga NyxRecover-*-windows-x64.zip de la release.'],
      ['2', 'Descomprime y ejecuta NyxRecover.exe — no necesita instalación.'],
      ['3', 'Modo consola: NyxRecover.exe --cli devices'],
    ],
    note: 'Para rescatar discos físicos ejecuta como Administrador.',
  },
  macos: {
    icon: '🍎', label: 'macOS',
    steps: [
      ['1', 'Descarga NyxRecover-*-macos.zip de la release.'],
      ['2', 'Descomprime, chmod +x NyxRecover y ejecútalo con sudo.'],
      ['3', 'discos: ls /dev/disk* — recuperación: sudo ./NyxRecover --cli recover /dev/disk4s1'],
    ],
    note: 'Primer arranque: clic derecho → Abrir para saltarte Gatekeeper.',
  },
}

function Section({ id, kicker, title, children }) {
  useReveal()
  return (
    <section id={id} className="relative z-10 mx-auto max-w-6xl px-6 py-24">
      <p className="reveal mb-2 text-xs font-bold uppercase tracking-[0.25em] text-cyan-400">{kicker}</p>
      <h2 className="reveal mb-12 text-4xl font-black tracking-tight sm:text-5xl">{title}</h2>
      {children}
    </section>
  )
}

export default function App() {
  const { loading, releases, error } = useReleases()
  const latest = releases?.[0]
  const [tab, setTab] = React.useState(() => {
    const ua = navigator.userAgent
    return /Windows/i.test(ua) ? 'windows' : /Mac/i.test(ua) ? 'macos' : 'linux'
  })

  return (
    <div className="relative">
      {/* NAV */}
      <nav className="fixed inset-x-0 top-0 z-50 glass-strong">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          <a href="#" className="flex items-center gap-2 text-lg font-black">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-cyan-400/30 to-violet-400/30 text-xl">🜲</span>
            Nyx<span className="gradient-text">Recover</span>
          </a>
          <div className="hidden gap-6 text-sm text-slate-300 md:flex">
            <a className="hover:text-cyan-300" href="#funciones">Funciones</a>
            <a className="hover:text-cyan-300" href="#instalar">Instalación</a>
            <a className="hover:text-cyan-300" href="#descargar">Descargar</a>
            <a className="hover:text-cyan-300" href="https://github.com/D1se0/nyxrecover" target="_blank" rel="noreferrer">GitHub ↗</a>
          </div>
          <a href={latest ? `https://github.com/${REPO}/releases/latest` : '#descargar'}
             className="rounded-xl bg-cyan-400/15 px-4 py-2 text-sm font-bold text-cyan-300 border border-cyan-400/30 hover:bg-cyan-400/25 transition">
            v{latest?.tag_name?.replace(/^v/, '') || '1.0.0'}
          </a>
        </div>
      </nav>

      <Hero releases={releases} loading={loading} />

      {/* FUNCIONES */}
      <Section id="funciones" kicker="Arsenal completo" title={<>Todo lo que hace —<br /><span className="gradient-text">y lo que las de pago no.</span></>}>
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(f => (
            <div key={f.title}
                 className={`reveal glass card-glow rounded-3xl border p-6 ${CMAP[f.color]}`}>
              <div className="mb-3 text-3xl">{f.icon}</div>
              <h3 className="mb-2 text-lg font-bold text-white">{f.title}</h3>
              <p className="text-sm leading-relaxed text-slate-300/85">{f.desc}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* SEGURIDAD */}
      <Section id="seguridad" kicker="Sin sustos" title={<>Alertas antes de<br /><span className="gradient-text">cada acción destructiva</span></>}>
        <div className="reveal glass rounded-3xl p-8 font-mono text-sm leading-7 text-slate-300">
          <p className="text-amber-300">╭─ 🔥 Confirmar borrado ─────────────────────────╮</p>
          <p>│ Dispositivo: <b className="text-white">/dev/sdb</b> (10.0 GB) · VMware Virtual S</p>
          <p>│ Método: zero (NIST SP 800-88 Rev.1 Clear)</p>
          <p className="text-rose-300">│ TODOS los datos se perderán PARA SIEMPRE.</p>
          <p className="text-amber-300">╰──────────────────────────────────────────────╯</p>
          <p className="mt-2">Escribe <b className="text-cyan-300">ELIMINAR SDB</b> para confirmar: <span className="cursor-blink">_</span></p>
        </div>
        <p className="reveal mt-6 max-w-3xl text-slate-300/85">
          Además de la frase de confirmación: bloqueo exclusivo del dispositivo (lock),
          clasificación de riesgo (sistema / interno / extraíble), detección de montajes activos,
          desmontaje seguro automático y journal de auditoría de cada operación.
        </p>
      </Section>

      {/* INSTALAR */}
      <Section id="instalar" kicker="En 30 segundos" title={<>Instalación por<br /><span className="gradient-text">sistema operativo</span></>}>
        <div className="reveal mb-6 flex gap-2">
          {Object.entries(INSTALL).map(([k, v]) => (
            <button key={k} onClick={() => setTab(k)}
              className={`rounded-xl px-5 py-2.5 text-sm font-bold transition ${
                tab === k ? 'bg-cyan-400/20 text-cyan-300 border border-cyan-400/40'
                          : 'glass text-slate-300 hover:text-white'}`}>
              {v.icon} {v.label.split(' (')[0]}
            </button>
          ))}
        </div>
        <div className="reveal glass rounded-3xl p-8">
          <h3 className="mb-5 text-xl font-bold">{INSTALL[tab].icon} {INSTALL[tab].label}</h3>
          <ol className="space-y-4">
            {INSTALL[tab].steps.map(([n, txt]) => (
              <li key={n} className="flex gap-4">
                <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-gradient-to-br from-cyan-400/30 to-violet-400/30 font-black text-cyan-300">{n}</span>
                <span className="pt-1 text-slate-200">{txt}</span>
              </li>
            ))}
          </ol>
          <p className="mt-5 rounded-xl border border-emerald-400/20 bg-emerald-400/10 p-4 text-sm text-emerald-200/90">
            💡 {INSTALL[tab].note}
          </p>
        </div>
      </Section>

      {/* DESCARGAR */}
      <Section id="descargar" kicker="Sin trucos" title={<>Descarga la<br /><span className="gradient-text">última release</span></>}>
        {loading && <p className="reveal glass rounded-2xl p-6">Consultando GitHub Releases…</p>}
        {error && (
          <div className="reveal glass rounded-2xl p-6">
            <p className="text-amber-300">⚠ No pude consultar GitHub ({error}).</p>
            <p className="mt-2 text-slate-300">Si el repo aún no tiene releases, crea la primera:
              <code className="mx-2 rounded bg-slate-800 px-2 py-1 text-cyan-300">gh release create v1.0.0 dist/*</code>
              o desde la web de GitHub → Releases → Draft new release.</p>
            <a className="mt-4 inline-block rounded-xl bg-cyan-400/20 px-5 py-2.5 font-bold text-cyan-300"
               href={`https://github.com/${REPO}/releases`} target="_blank" rel="noreferrer">
              Ir a Releases ↗
            </a>
          </div>
        )}
        {!loading && !error && latest && (
          <div className="reveal glass-strong rounded-3xl p-8">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h3 className="text-2xl font-black">{latest.name || latest.tag_name}</h3>
                <p className="text-sm text-slate-400">
                  {new Date(latest.published_at).toLocaleDateString('es', { dateStyle: 'long' })} · {latest.assets.length} archivos
                </p>
              </div>
              <a href={`https://github.com/${REPO}/releases/tag/${latest.tag_name}`}
                 target="_blank" rel="noreferrer"
                 className="rounded-xl bg-cyan-400/15 border border-cyan-400/30 px-5 py-2.5 font-bold text-cyan-300 hover:bg-cyan-400/25">
                Ver en GitHub ↗
              </a>
            </div>
            <div className="mt-6 grid gap-3 sm:grid-cols-2">
              {latest.assets.map(a => (
                <a key={a.id} href={a.browser_download_url}
                   className="group flex items-center justify-between rounded-2xl border border-slate-600/30 bg-slate-800/40 px-5 py-4 transition hover:border-cyan-400/40 hover:bg-slate-700/40">
                  <span className="flex items-center gap-3">
                    <span className="text-2xl">{/\.deb$/i.test(a.name) ? '🐧' : /win/i.test(a.name) ? '🪟' : /mac/i.test(a.name) ? '🍎' : '📦'}</span>
                    <span className="font-semibold text-slate-100">{a.name}</span>
                  </span>
                  <span className="text-sm text-slate-400 group-hover:text-cyan-300">↓ descargar</span>
                </a>
              ))}
            </div>
          </div>
        )}
        <p className="reveal mt-8 text-center text-sm text-slate-400">
          ¿Prefieres compilarlo tú?
          <a className="ml-2 text-cyan-300 hover:underline"
             href={`https://github.com/${REPO}#instalación-desde-código`} target="_blank" rel="noreferrer">
            Código fuente en GitHub ↗
          </a>
        </p>
      </Section>

      <footer className="relative z-10 border-t border-slate-700/40 py-10 text-center text-sm text-slate-500">
        <p>🜲 <b className="text-slate-300">NyxRecover</b> — GPL v3 · hecho con 💜 y cero telemetría</p>
        <p className="mt-1">Usa la herramienta solo en discos propios o con autorización explícita.</p>
      </footer>
    </div>
  )
}
