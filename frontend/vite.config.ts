import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Fixed port so it always matches the origin the backend allows (http://localhost:5173).
  server: { port: 5173, strictPort: true },
})
