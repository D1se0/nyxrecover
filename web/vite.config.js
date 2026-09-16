import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// base relativo → funciona en GitHub Pages bajo /nyxrecover/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: './',
})
