import { readFileSync } from "node:fs"
import { describe, expect, it, vi } from "vitest"

import {
  CONSOLE_DEV_BACKEND,
  COORDINATOR_ALLOWED_DEV_ORIGIN,
  consoleDevServer,
  rewriteCoordinatorDevOrigin,
  rewriteConsoleDevOrigin,
} from "./vite.config"
import { CONSOLE_SOCKET_PATH } from "./src/local-live/config"

describe("console coordinator development proxy", () => {
  it("keeps browser traffic same-origin on the fixed console port", () => {
    const developmentEnvironment = readFileSync(
      new URL(".env.development", import.meta.url),
      "utf8"
    ).trim()

    expect(consoleDevServer.port).toBe(5174)
    expect(consoleDevServer.strictPort).toBe(true)
    expect(developmentEnvironment).toBe(
      "VITE_COORDINATOR_ORIGIN=http://localhost:5174"
    )
  })

  it("keeps coordinator and local console Socket.IO on distinct backends", () => {
    expect(Object.keys(consoleDevServer.proxy).sort()).toEqual([
      "/api",
      CONSOLE_SOCKET_PATH,
      "/health",
      "/socket.io",
    ])
    expect(consoleDevServer.proxy["/socket.io"].ws).toBe(true)
    expect(consoleDevServer.proxy["/socket.io"].target).toBe(
      "http://127.0.0.1:8000"
    )
    expect(consoleDevServer.proxy[CONSOLE_SOCKET_PATH]).toMatchObject({
      target: CONSOLE_DEV_BACKEND,
      ws: true,
    })
    for (const path of ["/api", "/health"] as const)
      expect(consoleDevServer.proxy[path].target).toBe("http://127.0.0.1:8000")

    const coordinatorRequest = { setHeader: vi.fn() }
    rewriteCoordinatorDevOrigin(coordinatorRequest)
    expect(coordinatorRequest.setHeader).toHaveBeenCalledWith(
      "origin",
      COORDINATOR_ALLOWED_DEV_ORIGIN
    )
    const consoleRequest = { setHeader: vi.fn() }
    rewriteConsoleDevOrigin(consoleRequest)
    expect(consoleRequest.setHeader).toHaveBeenCalledWith(
      "origin",
      CONSOLE_DEV_BACKEND
    )
  })
})
