import path from "path"
import type { ClientRequest } from "node:http"
import tailwindcss from "@tailwindcss/vite"
import { tanstackRouter } from "@tanstack/router-plugin/vite"
import babel from "@rolldown/plugin-babel"
import react, { reactCompilerPreset } from "@vitejs/plugin-react"
import { defineConfig, type ProxyOptions } from "vite"

import { CONSOLE_SOCKET_PATH } from "./src/local-live/config"

const COORDINATOR_BACKEND = "http://127.0.0.1:8000"
export const CONSOLE_DEV_BACKEND = "http://127.0.0.1:8001"
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

export const rewriteConsoleDevOrigin = (
  request: Pick<ClientRequest, "setHeader">
) => {
  request.setHeader("origin", CONSOLE_DEV_BACKEND)
}

const consoleSocketProxy: ProxyOptions = {
  target: CONSOLE_DEV_BACKEND,
  changeOrigin: true,
  ws: true,
  configure(proxy) {
    proxy.on("proxyReq", rewriteConsoleDevOrigin)
    proxy.on("proxyReqWs", rewriteConsoleDevOrigin)
  },
}

export const consoleDevServer = {
  port: 5174,
  strictPort: true,
  proxy: {
    "/api": coordinatorProxy(),
    "/health": coordinatorProxy(),
    "/socket.io": coordinatorProxy(true),
    [CONSOLE_SOCKET_PATH]: consoleSocketProxy,
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
