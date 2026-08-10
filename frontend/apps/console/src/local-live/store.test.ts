import { beforeEach, describe, expect, it } from "vitest"

import type { ConsoleSnapshotPayload } from "./contract.gen"
import { consoleSnapshot } from "./test-fixtures"
import { useConsoleLiveStore } from "./store"

beforeEach(() => useConsoleLiveStore.getState().reset())

describe("console live store", () => {
  it("synchronizes from a complete snapshot and replaces state on boot change", () => {
    const store = useConsoleLiveStore.getState()
    store.applySnapshot(consoleSnapshot("boot-a", 4, 12))
    expect(useConsoleLiveStore.getState()).toMatchObject({
      bootId: "boot-a",
      revision: 4,
      can: { connected: true, frames_received: 12, fault: null },
      connection: { status: "connected", synchronized: true },
    })

    useConsoleLiveStore
      .getState()
      .applySnapshot(consoleSnapshot("boot-b", 1, 0))
    expect(useConsoleLiveStore.getState()).toMatchObject({
      bootId: "boot-b",
      revision: 1,
      can: { frames_received: 0 },
    })
  })

  it("ignores stale revisions within one boot", () => {
    const store = useConsoleLiveStore.getState()
    store.applySnapshot(consoleSnapshot("boot-a", 3, 8))
    expect(
      useConsoleLiveStore
        .getState()
        .applySnapshot(consoleSnapshot("boot-a", 2, 99))
    ).toBe(false)
    expect(useConsoleLiveStore.getState().can.frames_received).toBe(8)
  })

  it("keeps a CAN fault distinct from local transport disconnect", () => {
    useConsoleLiveStore.getState().applySnapshot(
      consoleSnapshot("boot-a", 2, 4, {
        connected: false,
        fault: "kcan receive failed",
      })
    )
    useConsoleLiveStore.getState().transportDisconnected()
    expect(useConsoleLiveStore.getState()).toMatchObject({
      can: { connected: false, fault: "kcan receive failed" },
      connection: { status: "reconnecting", synchronized: false },
    })
  })

  it("fails visibly for an incompatible protocol", () => {
    const incompatible = {
      ...consoleSnapshot("boot-a", 1),
      protocol_version: 2,
    }
    useConsoleLiveStore
      .getState()
      .applySnapshot(incompatible as unknown as ConsoleSnapshotPayload)
    expect(useConsoleLiveStore.getState().connection).toMatchObject({
      status: "incompatible",
      synchronized: false,
    })
    expect(useConsoleLiveStore.getState().connection.error).toContain(
      "requires version 1"
    )
  })
})
