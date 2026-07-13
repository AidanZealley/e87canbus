import type { CanTraceEntry, SimulatorEvent, SimulatorSnapshot } from "./types"

const TRACE_CAPACITY = 2_000

export type WorkbenchSnapshot = SimulatorSnapshot & {
  trace: CanTraceEntry[]
}

export const emptySnapshot: WorkbenchSnapshot = {
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
): WorkbenchSnapshot => ({
  ...next,
  trace: next.trace ?? current.trace,
})

const appendFrame = (
  current: WorkbenchSnapshot,
  frame: CanTraceEntry
): WorkbenchSnapshot => {
  if (current.trace.some((entry) => entry.sequence === frame.sequence)) {
    return current
  }
  return {
    ...current,
    trace: [...current.trace, frame].slice(-TRACE_CAPACITY),
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
    case "led_update":
      return {
        ...current,
        led_colours: {
          ...current.led_colours,
          [event.button_index]: event.colour_code,
        },
      }
  }
}
