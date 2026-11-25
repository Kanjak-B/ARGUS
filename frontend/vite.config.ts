import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // En développement, l'API est servie par « argus serve »
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
  build: {
    // Cytoscape dépasse à lui seul le seuil par défaut ; l'application reste locale
    chunkSizeWarningLimit: 800,
  },
})
