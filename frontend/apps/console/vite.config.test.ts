import { readFileSync } from "node:fs"
import { describe, expect, it } from "vitest"

import { CONSOLE_DEV_BACKEND, consoleDevServer } from "./vite.config"

describe("console development routing", () => {
  it("uses distinct origins for coordinator and local console traffic", () => {
    const developmentEnvironment = readFileSync(
      new URL(".env.development", import.meta.url),
      "utf8"
    ).trim()

    expect(consoleDevServer.port).toBe(5174)
    expect(consoleDevServer.strictPort).toBe(true)
    expect(developmentEnvironment).toBe(
      "VITE_COORDINATOR_ORIGIN=http://127.0.0.1:8000"
    )
    expect(Object.keys(consoleDevServer.proxy).sort()).toEqual([
      "/api",
      "/health",
    ])
    expect(consoleDevServer.proxy["/api"]).toMatchObject({
      target: CONSOLE_DEV_BACKEND,
      changeOrigin: true,
    })
    expect(consoleDevServer.proxy["/health"]).toMatchObject({
      target: CONSOLE_DEV_BACKEND,
      changeOrigin: true,
    })
  })
})
