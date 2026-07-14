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
  if (frame.session_id !== current.session_id) {
    return current
  }

  const trace = current.trace
  const last = trace.at(-1)
  if (last === undefined) return { ...current, trace: [frame] }
  if (frame.sequence === last.sequence) return current

  if (frame.sequence > last.sequence) {
    return {
      ...current,
      trace:
        trace.length < TRACE_CAPACITY
          ? [...trace, frame]
          : [...trace.slice(1), frame],
    }
  }

  const first = trace[0]
  if (
    trace.length === TRACE_CAPACITY &&
    first !== undefined &&
    frame.sequence <= first.sequence
  ) {
    return current
  }

  let insertionIndex = trace.length - 1
  while (
    insertionIndex >= 0 &&
    (trace[insertionIndex]?.sequence ?? -1) > frame.sequence
  ) {
    insertionIndex -= 1
  }
  if (trace[insertionIndex]?.sequence === frame.sequence) return current

  const nextTrace = [...trace]
  nextTrace.splice(insertionIndex + 1, 0, frame)
  if (nextTrace.length > TRACE_CAPACITY) nextTrace.shift()

  return {
    ...current,
    trace: nextTrace,
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
