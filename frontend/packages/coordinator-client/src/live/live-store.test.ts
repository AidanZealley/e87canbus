import { describe, expect, it } from "vitest"

import { snapshot } from "./test-fixtures"
import { useLiveStore } from "./live-store"

describe("live projection ownership", () => {
  it("atomically replaces a snapshot and updates only the changed projection", () => {
    useLiveStore.getState().reset()
    useLiveStore.getState().applyEvent(snapshot(3))
    const engine = useLiveStore.getState().engine
    const buttons = useLiveStore.getState().buttons

    useLiveStore.getState().applyEvent({
      type: "vehicle",
      data: { speed_kph: 42, speed_valid: true },
    })

    expect(useLiveStore.getState().vehicle.speed_kph).toBe(42)
    expect(useLiveStore.getState().engine).toBe(engine)
    expect(useLiveStore.getState().buttons).toBe(buttons)
  })

  it("requires a fresh snapshot before applying projections after a failure", () => {
    useLiveStore.getState().reset()
    useLiveStore.getState().applyEvent(snapshot(1))
    useLiveStore.getState().connectionFailed("connection lost")

    useLiveStore.getState().applyEvent({
      type: "vehicle",
      data: { speed_kph: 99, speed_valid: true },
    })

    expect(useLiveStore.getState().vehicle.speed_kph).toBe(1)
    expect(useLiveStore.getState().connection).toEqual({
      status: "disconnected",
      synchronized: false,
      error: "connection lost",
    })
    useLiveStore.getState().connectionPending()
    expect(useLiveStore.getState().connection).toMatchObject({
      status: "reconnecting",
      synchronized: false,
      error: "connection lost",
    })
    useLiveStore.getState().applyEvent(snapshot(2))
    expect(useLiveStore.getState().connection).toEqual({
      status: "connected",
      synchronized: true,
      error: null,
    })
  })
})
