import type {
  CanTraceEntry,
  SimulatorEvent,
  SimulatorSnapshot,
  SteeringControllerSnapshot,
} from "./types"

const TRACE_CAPACITY = 2_000
export const LED_COUNT = 16
const MAX_LED_COLOUR = 5

export type WorkbenchSnapshot = SimulatorSnapshot & {
  trace: CanTraceEntry[]
}

export const emptySnapshot: WorkbenchSnapshot = {
  session_id: 0,
  revision: 0,
  fatal: false,
  application: {
    vehicle_speed_kph: 0,
    speed_valid: false,
    steering_mode: "auto",
    manual_assistance_level: 0,
    maximum_assistance_active: false,
    active_steering_curve: null,
  },
  steering_controller: {
    effective_assistance: 0,
    last_command_reason: null,
    watchdog_timed_out: false,
  },
  next_pressed: true,
  led_colours: Array(LED_COUNT).fill(0) as number[],
  networks: [],
  trace: [],
}

export const formatSteeringReason = (
  reason: SteeringControllerSnapshot["last_command_reason"]
) => (reason === null ? "No command accepted" : reason.replaceAll("_", " "))

export const mergeSnapshot = (
  current: WorkbenchSnapshot,
  next: SimulatorSnapshot
): WorkbenchSnapshot => {
  if (
    next.session_id < current.session_id ||
    (next.session_id === current.session_id && next.revision < current.revision)
  ) {
    return current
  }
  const ledColours = isCompleteLedSnapshot(next.led_colours)
    ? [...next.led_colours]
    : current.led_colours
  return {
    ...next,
    led_colours: ledColours,
    trace:
      next.trace ??
      (next.session_id === current.session_id ? current.trace : []),
  }
}

export const isCompleteLedSnapshot = (colours: unknown): colours is number[] =>
  Array.isArray(colours) &&
  colours.length === LED_COUNT &&
  colours.every(
    (colour) =>
      Number.isInteger(colour) && colour >= 0 && colour <= MAX_LED_COLOUR
  )

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
