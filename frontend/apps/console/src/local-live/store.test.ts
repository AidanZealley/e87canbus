import { beforeEach, describe, expect, it } from "vitest"

import { consoleSnapshot } from "./test-fixtures"
import { useConsoleLiveStore } from "./store"

beforeEach(() => useConsoleLiveStore.getState().reset())

describe("console live store", () => {
  it("replaces the complete local CAN projection", () => {
    useConsoleLiveStore.getState().applySnapshot(consoleSnapshot(12))
    expect(useConsoleLiveStore.getState()).toMatchObject({
      can: { connected: true, frames_received: 12, fault: null },
      connection: { status: "connected", synchronized: true },
    })

    useConsoleLiveStore
      .getState()
      .applySnapshot(
        consoleSnapshot(0, { connected: false, fault: "reader stopped" })
      )
    expect(useConsoleLiveStore.getState().can).toMatchObject({
      connected: false,
      frames_received: 0,
      fault: "reader stopped",
    })
  })

  it("keeps a CAN fault distinct from local transport failure", () => {
    useConsoleLiveStore.getState().applySnapshot(
      consoleSnapshot(4, {
        connected: false,
        fault: "kcan receive failed",
      })
    )
    useConsoleLiveStore.getState().connectionFailed("network read failed")
    expect(useConsoleLiveStore.getState()).toMatchObject({
      can: { connected: false, fault: "kcan receive failed" },
      connection: {
        status: "disconnected",
        synchronized: false,
        error: "network read failed",
      },
    })
  })
})
