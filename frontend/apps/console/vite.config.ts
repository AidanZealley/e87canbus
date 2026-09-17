import path from "path"
import tailwindcss from "@tailwindcss/vite"
import { tanstackRouter } from "@tanstack/router-plugin/vite"
import babel from "@rolldown/plugin-babel"
import react, { reactCompilerPreset } from "@vitejs/plugin-react"
import { defineConfig } from "vite"

export const CONSOLE_DEV_BACKEND = "http://127.0.0.1:8001"

export const consoleDevServer = {
  port: 5174,
  strictPort: true,
  proxy: {
    "/api": {
      target: CONSOLE_DEV_BACKEND,
      changeOrigin: true,
    },
    "/health": {
      target: CONSOLE_DEV_BACKEND,
      changeOrigin: true,
    },
  },
} as const

// https://vite.dev/config/
export default defineConfig({
  server: consoleDevServer,
  plugins: [
    tanstackRouter({
      target: "react",
      autoCodeSplitting: true,
    }),
    react(),
    babel({
      presets: [reactCompilerPreset()],
    }),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
})
