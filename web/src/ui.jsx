import React from 'react'
import { useReveal } from './lib.jsx'

export function Section({ id, kicker, title, children }) {
  useReveal()
  return (
    <section id={id} className="relative z-10 mx-auto max-w-6xl px-6 py-24">
      <p className="reveal mb-2 text-xs font-bold uppercase tracking-[0.25em] text-cyan-400">{kicker}</p>
      <h2 className="reveal mb-12 text-4xl font-black tracking-tight sm:text-5xl">{title}</h2>
      {children}
    </section>
  )
}
