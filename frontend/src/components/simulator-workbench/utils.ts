import type { CanTraceEntry, SimulatorEvent, SimulatorSnapshot } from "./types"

const TRACE_CAPACITY = 2_000

export type WorkbenchSnapshot = SimulatorSnapshot & {
  trace: CanTraceEntry[]
}

export const emptySnapshot: WorkbenchSnapshot = {
  session_id: 0,
  revision: 0,
  application: {
    vehicle_speed_kph: 0,
    speed_valid: false,
    steering_mode: "auto",
    manual_assistance_level: 0,
    maximum_assistance_active: false,
  },
  next_pressed: true,
  led_colours: {},
  networks: [],
  trace: [],
}

export const mergeSnapshot = (
  current: WorkbenchSnapshot,
  next: SimulatorSnapshot
): WorkbenchSnapshot => {
  if (
    next.session_id < current.session_id ||
    (next.session_id === current.session_id &&
      next.revision < current.revision)
  ) {
    return current
  }
  return {
    ...next,
    trace:
      next.trace ??
      (next.session_id === current.session_id ? current.trace : []),
  }
}

const appendFrame = (
  current: WorkbenchSnapshot,
  frame: CanTraceEntry
): WorkbenchSnapshot => {
  if (
    frame.session_id !== current.session_id ||
    current.trace.some(
      (entry) =>
        entry.session_id === frame.session_id &&
        entry.sequence === frame.sequence
    )
  ) {
    return current
  }
  return {
    ...current,
    trace: [...current.trace, frame]
      .sort((left, right) => left.sequence - right.sequence)
      .slice(-TRACE_CAPACITY),
  }
}

export const reduceSimulatorEvent = (
  current: WorkbenchSnapshot,
  event: SimulatorEvent
): WorkbenchSnapshot => {
  switch (event.type) {
    case "snapshot":
      return mergeSnapshot(current, event.snapshot)
    case "frame":
      return appendFrame(current, event)
  }
}
