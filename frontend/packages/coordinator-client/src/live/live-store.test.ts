import { describe, expect, it } from "vitest"

import { snapshot } from "./test-fixtures"
import { useLiveStore } from "./live-store"

describe("live ownership", () => {
  it("atomically replaces snapshots, rejects stale topics, and requires a snapshot for a new boot", () => {
    useLiveStore.getState().reset()
    expect(useLiveStore.getState().applySnapshot(snapshot("boot-a", 3))).toBe(
      true
    )
    const engineReference = useLiveStore.getState().engine
    const vehicle = {
      ...snapshot("boot-a", 4),
      data: { speed_kph: 42, speed_valid: true },
    }
    expect(useLiveStore.getState().applyVehicle(vehicle)).toBe("applied")
    expect(useLiveStore.getState().engine).toBe(engineReference)
    expect(useLiveStore.getState().vehicle.speed_kph).toBe(42)
    expect(useLiveStore.getState().applyVehicle(vehicle)).toBe("ignored")
    expect(
      useLiveStore
        .getState()
        .applyVehicle({ ...vehicle, boot_id: "boot-b", revision: 5 })
    ).toBe("resync")
    expect(useLiveStore.getState().bootId).toBe("boot-a")
    expect(useLiveStore.getState().applySnapshot(snapshot("boot-b", 1))).toBe(
      true
    )
    expect(useLiveStore.getState().bootId).toBe("boot-b")
    expect(useLiveStore.getState().vehicle.speed_kph).toBe(1)
  })

  it("keeps connection unsynchronized until a complete compatible snapshot", () => {
    useLiveStore.getState().reset()
    useLiveStore.getState().transportConnected(false)
    expect(useLiveStore.getState().connection.status).toBe("synchronizing")
    useLiveStore.getState().transportDisconnected()
    expect(useLiveStore.getState().connection.synchronized).toBe(false)
    const incompatible = { ...snapshot("boot", 1), protocol_version: 2 as 1 }
    expect(useLiveStore.getState().applySnapshot(incompatible)).toBe(false)
    expect(useLiveStore.getState().connection.status).toBe("incompatible")
  })

  it("applies a newer service-only health revision after synchronization", () => {
    useLiveStore.getState().reset()
    const initial = snapshot("boot", 3)
    expect(useLiveStore.getState().applySnapshot(initial)).toBe(true)

    const health = {
      ...initial,
      revision: 4,
      data: {
        ...initial.data.health,
        ready: false,
        persistence: { available: false, fault: "database unavailable" },
      },
    }

    expect(useLiveStore.getState().applyHealth(health)).toBe("applied")
    expect(useLiveStore.getState().topicRevisions.health).toBe(4)
    expect(useLiveStore.getState().health.persistence).toEqual({
      available: false,
      fault: "database unavailable",
    })
    expect(useLiveStore.getState().applyHealth(health)).toBe("ignored")
  })

  it("applies lighting separately from the button and steering state", () => {
    useLiveStore.getState().reset()
    const initial = snapshot("boot", 3)
    expect(useLiveStore.getState().applySnapshot(initial)).toBe(true)
    const buttons = useLiveStore.getState().buttons
    const lighting = {
      ...initial,
      revision: 4,
      data: {
        high_beam_enabled: true,
        high_beam_strobe_active: true,
        high_beam_strobe_cycles_remaining: 2,
        observed_high_beam_enabled: true,
      },
    }

    expect(useLiveStore.getState().applyLighting(lighting)).toBe("applied")
    expect(useLiveStore.getState().buttons).toBe(buttons)
    expect(useLiveStore.getState().lighting).toMatchObject({
      high_beam_enabled: true,
      high_beam_strobe_cycles_remaining: 2,
      observed_high_beam_enabled: true,
    })
  })
})
