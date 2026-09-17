import type { ConsoleSnapshotData } from "@/api/console-host"

export const consoleSnapshot = (
  framesReceived = 0,
  overrides: Partial<ConsoleSnapshotData["can"]> = {}
): ConsoleSnapshotData => ({
  can: {
    interface: "kcan",
    connected: true,
    frames_received: framesReceived,
    fault: null,
    ...overrides,
  },
})
