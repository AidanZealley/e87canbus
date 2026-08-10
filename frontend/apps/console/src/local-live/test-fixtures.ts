import type { ConsoleSnapshotPayload } from "./contract.gen"

export const consoleSnapshot = (
  bootId: string,
  revision: number,
  framesReceived = 0,
  overrides: Partial<ConsoleSnapshotPayload["data"]["can"]> = {}
): ConsoleSnapshotPayload => ({
  protocol_version: 1,
  boot_id: bootId,
  revision,
  emitted_at: "2026-08-10T12:00:00Z",
  data: {
    can: {
      interface: "kcan",
      connected: true,
      frames_received: framesReceived,
      fault: null,
      ...overrides,
    },
  },
})
