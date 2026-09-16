import React from 'react'
import { REPO, useReveal, assetFor, fmtBytes } from './lib.jsx'

function detectOSSafe() {
  try {
    const ua = navigator.userAgent
    if (/Windows NT/i.test(ua)) return { id: 'windows', label: 'Windows', icon: '🪟' }
    if (/Mac OS X|Macintosh/i.test(ua)) return { id: 'macos', label: 'macOS', icon: '🍎' }
    if (/Linux/i.test(ua)) return { id: 'linux', label: 'Linux', icon: '🐧' }
    return { id: 'unknown', label: 'tu sistema', icon: '💻' }
  } catch { return { id: 'unknown', label: 'tu sistema', icon: '💻' } }
}

function DownloadButton({ releases, loading, version }) {
  const os = React.useMemo(() => detectOSSafe(), [])
  const [busy, setBusy] = React.useState(false)

  const asset = React.useMemo(() => {
    if (os.id === 'windows') return assetFor(releases, ['windows.*zip', '\\.exe$', 'win'])
    if (os.id === 'macos') return assetFor(releases, ['macos.*zip', 'mac', 'darwin'])
    return assetFor(releases, ['_all\\.deb$', 'linux.*deb', 'deb$'])
  }, [releases, os])

  const url = asset?.browser_download_url
  const label = loading ? 'Buscando la última release…'
    : url ? `Descargar para ${os.label} · ${fmtBytes(asset.size)}`
    : `Descargar v${version} para ${os.label}`

  function go() {
    setBusy(true)
    window.open(url || `https://github.com/${REPO}/releases/latest`, '_blank')
    setTimeout(() => setBusy(false), 1200)
  }

  return (
    <button onClick={go}
      className="group relative inline-flex items-center gap-3 rounded-2xl px-8 py-4 text-lg font-bold
                 bg-gradient-to-r from-cyan-400 via-sky-400 to-violet-400 text-slate-950
                 shadow-[0_0_45px_-8px_rgba(34,211,238,.65)] hover:shadow-[0_0_65px_-6px_rgba(167,139,250,.8)]
                 hover:scale-[1.03] active:scale-[.98] transition-all">
      <span className="text-2xl">{os.icon}</span>
      <span className="flex flex-col items-start leading-tight">
        <span>{busy ? 'Abriendo…' : label}</span>
        <span className="text-xs font-medium opacity-70">
          v{version} · gratis · open source · sin registro
        </span>
      </span>
      <span className="ml-1 text-xl transition-transform group-hover:translate-x-1">→</span>
    </button>
  )
}

export default function Hero({ releases, loading, version = '1.0.0' }) {
  useReveal()
  return (
    <header className="relative min-h-[92vh] overflow-hidden">
      {/* orbes flotantes */}
      <div className="pointer-events-none absolute inset-0 z-0">
        <div className="absolute left-[8%] top-[18%] h-72 w-72 rounded-full bg-cyan-500/15 blur-3xl animate-float" />
        <div className="absolute right-[10%] top-[30%] h-80 w-80 rounded-full bg-violet-500/15 blur-3xl animate-float [animation-delay:-3s]" />
        <div className="absolute bottom-[8%] left-[45%] h-64 w-64 rounded-full bg-emerald-500/10 blur-3xl animate-float [animation-delay:-6s]" />
      </div>

      {/* consola decorativa con línea de escaneo */}
      <div className="pointer-events-none absolute right-[6%] top-[16%] z-0 hidden w-[430px] rotate-2 lg:block">
        <div className="glass-strong overflow-hidden rounded-2xl shadow-2xl">
          <div className="flex items-center gap-2 border-b border-slate-700/50 px-4 py-2">
            <span className="h-3 w-3 rounded-full bg-rose-400" />
            <span className="h-3 w-3 rounded-full bg-amber-300" />
            <span className="h-3 w-3 rounded-full bg-emerald-400" />
            <span className="ml-2 text-xs text-slate-400">nyx — recuperación forense</span>
          </div>
          <div className="relative p-5 font-mono text-[13px] leading-6 text-emerald-300/90">
            <div className="absolute inset-x-0 h-10 bg-gradient-to-b from-cyan-400/10 to-transparent animate-scan" />
            <p className="text-slate-400">$ sudo nyx recover /dev/sdb1 -m smart</p>
            <p>🜲 NyxRecover v{version}</p>
            <p className="text-cyan-300">▸ 12.4 GB escaneados · 71 MB/s</p>
            <p className="text-emerald-400">✔ 3 archivos borrados recuperados</p>
            <p className="text-violet-300">▸ timeline: 1.204 eventos</p>
            <p className="text-amber-300">⚠ LUKS detectado en sda2</p>
            <p className="cursor-blink text-slate-400">_</p>
          </div>
        </div>
      </div>

      <div className="relative z-10 mx-auto flex max-w-6xl flex-col items-start justify-center px-6 pt-36">
        <div className="reveal glass mb-6 inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-xs font-semibold tracking-wide text-cyan-300">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
          </span>
          v{version} · GRATIS y con más funciones que herramientas de pago
        </div>

        <h1 className="reveal max-w-3xl text-5xl font-black leading-[1.05] tracking-tight sm:text-7xl">
          Lo que borraste<br />
          <span className="gradient-text">nunca se fue de verdad.</span>
        </h1>

        <p className="reveal mt-6 max-w-xl text-lg leading-relaxed text-slate-300/90">
          <b className="text-white">NyxRecover</b> rescata archivos eliminados de cualquier disco
          y los reconstruye íntegros — y cuando quieres que <i>desaparezcan para siempre</i>,
          los borra con estándares NIST/DoD y emite un certificado verificable.
        </p>

        <div className="reveal mt-9 flex flex-wrap items-center gap-4">
          <DownloadButton releases={releases} loading={loading} version={version} />
          <a href="#funciones"
             className="rounded-2xl px-6 py-4 font-semibold glass hover:bg-slate-700/30 transition">
            Explorar funciones ↓
          </a>
        </div>

        <div className="reveal mt-14 grid w-full max-w-2xl grid-cols-3 gap-3 text-center">
          {[['71 MB/s', 'escaneo'], ['52', 'tests verdes'], ['0 €', 'para siempre']].map(([n, l]) => (
            <div key={l} className="glass card-glow rounded-2xl px-3 py-4">
              <p className="text-2xl font-black text-cyan-300">{n}</p>
              <p className="text-xs uppercase tracking-widest text-slate-400">{l}</p>
            </div>
          ))}
        </div>
      </div>
    </header>
  )
}
