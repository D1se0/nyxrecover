import React from 'react'
import Hero from './Hero.jsx'
import Docs from './Docs.jsx'
import { REPO, useReleases, useReveal, assetFor, fmtBytes } from './lib.jsx'
import { Section } from './ui.jsx'

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

const STATS = [
  ['71 MB/s', 'velocidad de escaneo'],
  ['45+', 'firmas de archivos'],
  ['12', 'comandos CLI'],
  ['52', 'tests en verde'],
]

const USECASES = [
  { icon: '🗑', t: 'Borrado accidental', d: '«Se me han ido las fotos de la cámara con format c:» — el formateo rápido solo toca tablas: los bytes siguen ahí y el carving los trae de vuelta.' },
  { icon: '💼', t: 'Peritaje forense', d: 'Timeline, keywords, slack y manifiestos con SHA-256 + cadena de custodia verificable: todo lo que un informe necesita, gratis.' },
  { icon: '🔁', t: 'Venta o reciclaje', d: 'Antes de deshacerte de un equipo: wipe certificado NIST/DoD con verificación y el certificado HTML como prueba de la destrucción.' },
  { icon: '🛡', t: 'Respuesta a incidentes', d: 'Detección de LUKS/BitLocker/VeraCrypt, mapa de entropía e inventario completo del disco en segundos.' },
]

export default function App() {
  const { loading, releases, error } = useReleases()
  const latest = releases?.[0]
  const version = latest?.tag_name?.replace(/^v/, '') || '1.0.0'
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
            <a className="hover:text-cyan-300" href="#docs">Docs</a>
            <a className="hover:text-cyan-300" href="#instalar">Instalación</a>
            <a className="hover:text-cyan-300" href="#descargar">Descargar</a>
            <a className="hover:text-cyan-300" href="https://github.com/D1se0/nyxrecover" target="_blank" rel="noreferrer">GitHub ↗</a>
          </div>
          <a href={latest ? `https://github.com/${REPO}/releases/tag/${latest.tag_name}` : `https://github.com/${REPO}/releases`}
             title={latest ? `Release ${latest.tag_name} — publicada el ${new Date(latest.published_at).toLocaleDateString('es', { dateStyle: 'medium' })}` : 'Ir a Releases'}
             className="group flex items-center gap-2 rounded-xl bg-cyan-400/15 px-4 py-2 text-sm font-bold text-cyan-300 border border-cyan-400/30 hover:bg-cyan-400/25 transition">
            <span className={`h-2 w-2 rounded-full ${latest ? 'bg-emerald-400' : 'bg-amber-400 animate-pulse'}`} />
            v{version}
          </a>
        </div>
      </nav>

      <Hero releases={releases} loading={loading} version={version} />

      {/* STATS */}
      <div className="relative z-10 mx-auto -mt-4 mb-4 grid max-w-4xl grid-cols-2 gap-3 px-6 sm:grid-cols-4">
        {STATS.map(([n, l]) => (
          <div key={l} className="reveal glass card-glow rounded-2xl px-3 py-4 text-center">
            <p className="text-2xl font-black text-cyan-300">{n}</p>
            <p className="text-xs uppercase tracking-widest text-slate-400">{l}</p>
          </div>
        ))}
      </div>

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
        <div className="reveal mt-8 rounded-2xl border border-cyan-400/20 bg-cyan-400/5 p-6 text-center">
          <p className="text-slate-200">
            ¿Quieres el detalle de cada comando, con ejemplos listos para copiar?
          </p>
          <a href="#docs" className="mt-3 inline-block rounded-xl bg-cyan-400/15 border border-cyan-400/30 px-6 py-2.5 font-bold text-cyan-300 hover:bg-cyan-400/25 transition">
            📚 Ir a la documentación completa ↓
          </a>
        </div>
      </Section>

      {/* CASOS DE USO */}
      <Section id="casos" kicker="¿Para quién?" title={<>Cuatro momentos donde<br /><span className="gradient-text">NyxRecover marca la diferencia</span></>}>
        <div className="grid gap-5 sm:grid-cols-2">
          {USECASES.map(u => (
            <div key={u.t} className="reveal glass rounded-3xl p-6">
              <div className="mb-3 flex items-center gap-3">
                <span className="text-3xl">{u.icon}</span>
                <h3 className="text-lg font-bold text-white">{u.t}</h3>
              </div>
              <p className="text-sm leading-relaxed text-slate-300/85">{u.d}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* DOCS */}
      <Docs />

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
        <div className="reveal mt-6 grid gap-4 sm:grid-cols-2">
          {[
            ['🔒 Frase de confirmación', 'No hay botón «siguiente-siguiente-fin»: para borrar hay que escribir una frase única generada para ese dispositivo.'],
            ['🚦 Clasificación de riesgo', 'Cada disco se evalúa: sistema (bloqueado), interno, extraíble — con avisos antes de tocar nada.'],
            ['🔐 Lock exclusivo', 'El dispositivo se bloquea durante la operación: ningún otro proceso puede escribir mientras se destruyen los datos.'],
            ['📜 Journal auditable', 'Cada acción queda en un journal con cadena de hashes SHA-256: si alguien lo manipula, se detecta.'],
          ].map(([t, d]) => (
            <div key={t} className="glass rounded-2xl p-5">
              <p className="font-bold text-slate-100">{t}</p>
              <p className="mt-1.5 text-sm text-slate-300/85">{d}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* INSTALAR */}
      <Section id="instalar" kicker="En 30 segundos" title={<>Instalación por<br /><span className="gradient-text">sistema operativo</span></>}>
        <div className="reveal mb-6 flex flex-wrap gap-2">
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
        {/* tarjeta principal: siempre visible */}
        <div className="reveal glass-strong rounded-3xl p-8">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h3 className="text-2xl font-black">
                🜲 NyxRecover <span className="gradient-text">v{version}</span>
                {latest && <span className="ml-3 align-middle rounded-full bg-emerald-400/15 border border-emerald-400/30 px-3 py-0.5 text-xs font-bold text-emerald-300">última release</span>}
              </h3>
              <p className="mt-1 text-sm text-slate-400">
                {latest
                  ? <>publicada el {new Date(latest.published_at).toLocaleDateString('es', { dateStyle: 'long' })} · {latest.assets.length} archivos para Windows, Linux y macOS</>
                  : 'GPL v3 · gratis · sin registro · binarios oficiales en GitHub Releases'}
              </p>
            </div>
            <div className="flex gap-3">
              <a href={`https://github.com/${REPO}/releases/latest`} target="_blank" rel="noreferrer"
                 className="rounded-xl bg-cyan-400/15 border border-cyan-400/30 px-5 py-2.5 font-bold text-cyan-300 hover:bg-cyan-400/25">
                Ver en GitHub ↗
              </a>
              <a href="#instalar"
                 className="rounded-xl glass px-5 py-2.5 font-bold text-slate-300 hover:text-white">
                ¿Cómo se instala?
              </a>
            </div>
          </div>

          {/* assets reales o tarjetas estáticas de fallback */}
          {latest && !error && (
            <div className="mt-6 grid gap-3 sm:grid-cols-2">
              {latest.assets.map(a => (
                <a key={a.id} href={a.browser_download_url}
                   className="group flex items-center justify-between rounded-2xl border border-slate-600/30 bg-slate-800/40 px-5 py-4 transition hover:border-cyan-400/40 hover:bg-slate-700/40">
                  <span className="flex items-center gap-3">
                    <span className="text-2xl">{/\.deb$/i.test(a.name) ? '🐧' : /win/i.test(a.name) ? '🪟' : /mac/i.test(a.name) ? '🍎' : '📦'}</span>
                    <span>
                      <span className="block font-semibold text-slate-100">{a.name}</span>
                      <span className="text-xs text-slate-500">{fmtBytes(a.size)}</span>
                    </span>
                  </span>
                  <span className="text-sm text-slate-400 group-hover:text-cyan-300">↓ descargar</span>
                </a>
              ))}
            </div>
          )}
          {(!latest || error) && (
            <div className="mt-6 grid gap-3 sm:grid-cols-3">
              {[
                ['🪟', 'Windows', `NyxRecover-v${version}-windows-x64.zip`, `https://github.com/${REPO}/releases/latest`],
                ['🐧', 'Linux', `nyxrecover_${version}_all.deb`, `https://github.com/${REPO}/releases/latest`],
                ['🍎', 'macOS', `NyxRecover-v${version}-macos.zip`, `https://github.com/${REPO}/releases/latest`],
              ].map(([ico, so, fichero, url]) => (
                <a key={so} href={url} target="_blank" rel="noreferrer"
                   className="group flex flex-col gap-1 rounded-2xl border border-slate-600/30 bg-slate-800/40 px-5 py-4 transition hover:border-cyan-400/40 hover:bg-slate-700/40">
                  <span className="text-2xl">{ico}</span>
                  <span className="font-semibold text-slate-100">{so}</span>
                  <span className="break-all font-mono text-xs text-slate-500 group-hover:text-cyan-300/80">{fichero}</span>
                  <span className="mt-1 text-sm text-slate-400 group-hover:text-cyan-300">↓ descargar desde GitHub ↗</span>
                </a>
              ))}
            </div>
          )}

          {error && (
            <p className="mt-4 rounded-xl border border-amber-400/20 bg-amber-400/10 p-3 text-xs text-amber-200/80">
              ⚠ GitHub API no disponible ahora mismo ({error}) — usa los botones de arriba: llevan directo a los binarios oficiales.
            </p>
          )}
        </div>

        {/* checksums / verificar */}
        <div className="reveal mt-6 glass rounded-2xl p-6">
          <p className="font-bold text-slate-100">🔐 Verificar la descarga (opcional, para paranoicos bien informados)</p>
          <p className="mt-2 text-sm text-slate-300/85">
            Cada binario de la release tiene su hash SHA-256 publicado junto al fichero.
            Comprueba el que descargues:
          </p>
          <pre className="mt-3 overflow-x-auto rounded-xl border border-slate-700/50 bg-[#0a0e1a]/90 p-4 font-mono text-[13px] text-emerald-300/95"><code>{`# Linux / macOS
sha256sum nyxrecover_${version}_all.deb

# Windows (PowerShell)
Get-FileHash NyxRecover-v${version}-windows-x64.zip -Algorithm SHA256`}</code></pre>
          <p className="mt-3 text-sm text-slate-400">
            Los hashes exactos de esta release:
            <a className="ml-2 text-cyan-300 hover:underline" href={`https://github.com/${REPO}/releases/tag/${latest?.tag_name || 'v' + version}`} target="_blank" rel="noreferrer">
              ver en la página de la release ↗
            </a>
          </p>
        </div>

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
