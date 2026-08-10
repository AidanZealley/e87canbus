import path from "path"
import type { ClientRequest } from "node:http"
import tailwindcss from "@tailwindcss/vite"
import { tanstackRouter } from "@tanstack/router-plugin/vite"
import babel from "@rolldown/plugin-babel"
import react, { reactCompilerPreset } from "@vitejs/plugin-react"
import { defineConfig, type ProxyOptions } from "vite"

const COORDINATOR_BACKEND = "http://127.0.0.1:8000"
export const COORDINATOR_ALLOWED_DEV_ORIGIN = "http://127.0.0.1:5173"

export const rewriteCoordinatorDevOrigin = (
  request: Pick<ClientRequest, "setHeader">
) => {
  request.setHeader("origin", COORDINATOR_ALLOWED_DEV_ORIGIN)
}

const coordinatorProxy = (websocket = false): ProxyOptions => ({
  target: COORDINATOR_BACKEND,
  changeOrigin: true,
  ws: websocket,
  configure(proxy) {
    proxy.on("proxyReq", rewriteCoordinatorDevOrigin)
    proxy.on("proxyReqWs", rewriteCoordinatorDevOrigin)
  },
})

export const consoleDevServer = {
  port: 5174,
  strictPort: true,
  proxy: {
    "/api": coordinatorProxy(),
    "/health": coordinatorProxy(),
    "/socket.io": coordinatorProxy(true),
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
