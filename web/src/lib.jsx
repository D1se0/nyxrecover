import React from 'react'

export const REPO = 'D1se0/nyxrecover'

export function useReveal() {
  React.useEffect(() => {
    const io = new IntersectionObserver(es => {
      es.forEach(e => e.isIntersecting && e.target.classList.add('in'))
    }, { threshold: 0.12 })
    document.querySelectorAll('.reveal').forEach(el => io.observe(el))
    return () => io.disconnect()
  }, [])
}

export function detectOS() {
  const ua = navigator.userAgent
  if (/Windows NT/i.test(ua)) return { id: 'windows', label: 'Windows', icon: '🪟' }
  if (/Mac OS X|Macintosh/i.test(ua)) return { id: 'macos', label: 'macOS', icon: '🍎' }
  if (/Android/i.test(ua)) return { id: 'android', label: 'Android', icon: '🤖' }
  if (/Linux/i.test(ua)) return { id: 'linux', label: 'Linux', icon: '🐧' }
  return { id: 'unknown', label: 'tu sistema', icon: '💻' }
}

export function useReleases() {
  const [state, setState] = React.useState({ loading: true, releases: [], error: null })
  React.useEffect(() => {
    fetch(`https://api.github.com/repos/${REPO}/releases?per_page=5`)
      .then(r => {
        if (!r.ok) throw new Error(`GitHub API ${r.status}`)
        return r.json()
      })
      .then(data => setState({ loading: false, releases: data, error: null }))
      .catch(e => setState({ loading: false, releases: [], error: e.message }))
  }, [])
  return state
}

export function assetFor(releases, patterns) {
  if (!releases?.length) return null
  const assets = releases[0].assets || []
  for (const pat of patterns) {
    const hit = assets.find(a => new RegExp(pat, 'i').test(a.name))
    if (hit) return hit
  }
  return null
}

export function fmtBytes(n) {
  if (!n && n !== 0) return ''
  const u = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let x = n
  while (x >= 1024 && i < 3) { x /= 1024; i++ }
  return `${x.toFixed(x >= 10 || i === 0 ? 0 : 1)} ${u[i]}`
}
