import { readFileSync } from "node:fs"
import { describe, expect, it, vi } from "vitest"

import {
  COORDINATOR_ALLOWED_DEV_ORIGIN,
  consoleDevServer,
  rewriteCoordinatorDevOrigin,
} from "./vite.config"

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

  it("proxies the complete coordinator client surface and rewrites its origin", () => {
    expect(Object.keys(consoleDevServer.proxy).sort()).toEqual([
      "/api",
      "/health",
      "/socket.io",
    ])
    expect(consoleDevServer.proxy["/socket.io"].ws).toBe(true)
    for (const proxy of Object.values(consoleDevServer.proxy)) {
      expect(proxy.target).toBe("http://127.0.0.1:8000")
    }

    const request = { setHeader: vi.fn() }
    rewriteCoordinatorDevOrigin(request)
    expect(request.setHeader).toHaveBeenCalledWith(
      "origin",
      COORDINATOR_ALLOWED_DEV_ORIGIN
    )
  })
})
