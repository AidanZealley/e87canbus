import { describe, expect, it } from "vitest"

import type { TraceRow } from "@/api/live-contract.gen"
import { snapshot } from "./test-fixtures"
import { TRACE_CAPACITY, useTraceStore } from "./trace-store"
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

  it("preserves unchanged registry role references across device updates", () => {
    useLiveStore.getState().reset()
    const initial = snapshot("boot", 3)
    expect(useLiveStore.getState().applySnapshot(initial)).toBe(true)
    const initialButtonPad = useLiveStore.getState().devices.registry.button_pad
    const initialServotronic =
      useLiveStore.getState().devices.registry.servotronic_controller

    const devices = {
      ...initial.data.devices,
      registry: {
        ...initial.data.devices.registry,
        button_pad: {
          ...initial.data.devices.registry.button_pad,
          status: "stale" as const,
        },
      },
    }
    expect(
      useLiveStore.getState().applyDevices({
        ...initial,
        revision: 4,
        data: devices,
      })
    ).toBe("applied")

    const current = useLiveStore.getState().devices.registry
    expect(current.button_pad).not.toBe(initialButtonPad)
    expect(current.button_pad.status).toBe("stale")
    expect(current.servotronic_controller).toBe(initialServotronic)
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

  it("orders local controls independently and hydrates them from reconnect snapshots", () => {
    useLiveStore.getState().reset()
    const initial = snapshot("boot", 3)
    expect(useLiveStore.getState().applySnapshot(initial)).toBe(true)

    expect(
      useLiveStore.getState().applyLocalControls({
        protocol_version: 1,
        boot_id: "boot-local-controls",
        revision: 4,
        emitted_at: "2026-07-15T00:00:01Z",
        data: {
          ...initial.data.local_controls!.state,
          desired_display: "hotspot_waiting",
          effective_display: "hotspot_waiting",
          hotspot: "activating",
        },
      })
    ).toBe("applied")
    expect(useLiveStore.getState().localControls?.revision).toBe(4)
    expect(useLiveStore.getState().topicRevisions).toEqual(
      initial.data.topic_revisions
    )

    const staleLocalSnapshot = snapshot("boot", 5)
    staleLocalSnapshot.data.local_controls!.revision = 3
    expect(useLiveStore.getState().applySnapshot(staleLocalSnapshot)).toBe(true)
    expect(useLiveStore.getState().localControls?.revision).toBe(4)

    const rehydrated = snapshot("boot", 6)
    rehydrated.data.local_controls = {
      boot_id: "replacement-local-controls",
      revision: 1,
      state: {
        ...rehydrated.data.local_controls!.state,
        desired_display: "starting",
        effective_display: "starting",
      },
    }
    expect(useLiveStore.getState().applySnapshot(rehydrated)).toBe(true)
    expect(useLiveStore.getState().localControls).toMatchObject({
      boot_id: "replacement-local-controls",
      revision: 1,
      state: { effective_display: "starting" },
    })
  })

  it("requests a snapshot for local-control events before hydration or after a service reboot", () => {
    useLiveStore.getState().reset()
    const initial = snapshot("boot", 2)
    const event = {
      protocol_version: 1 as const,
      boot_id: "boot-local-controls",
      revision: 3,
      emitted_at: "2026-07-15T00:00:01Z",
      data: initial.data.local_controls!.state,
    }

    expect(useLiveStore.getState().applyLocalControls(event)).toBe("resync")
    useLiveStore.getState().applySnapshot(initial)
    expect(
      useLiveStore
        .getState()
        .applyLocalControls({ ...event, boot_id: "new-local-controls" })
    ).toBe("resync")
  })

  it("bounds and clears diagnostic trace across sessions", () => {
    useTraceStore.getState().clear()
    const rows: TraceRow[] = Array.from(
      { length: TRACE_CAPACITY + 25 },
      (_, sequence) => ({
        type: "frame",
        session_id: 2,
        sequence,
        network: "kcan",
        source: "test",
        arbitration_id: 1,
        arbitration_id_hex: "001",
        data_hex: "00",
        is_extended_id: false,
        monotonic_s: sequence,
      })
    )
    useTraceStore.getState().applyBatch(
      {
        protocol_version: 1,
        boot_id: "boot",
        revision: 10,
        emitted_at: "2026-07-15T00:00:00Z",
        data: { rows },
      },
      "boot"
    )
    expect(useTraceStore.getState().rows).toHaveLength(TRACE_CAPACITY)
    expect(useTraceStore.getState().rows[0]?.sequence).toBe(25)
    useTraceStore.getState().applyBatch(
      {
        protocol_version: 1,
        boot_id: "boot",
        revision: 11,
        emitted_at: "2026-07-15T00:00:00Z",
        data: { rows: [{ ...rows[0]!, session_id: 3 }] },
      },
      "boot"
    )
    expect(useTraceStore.getState().rows).toHaveLength(1)
    expect(useTraceStore.getState().sessionId).toBe(3)
  })
})
