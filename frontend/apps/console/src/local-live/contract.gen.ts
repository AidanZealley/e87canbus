/** Generated from protocol/console-live-v1.schema.json. Do not edit. */

/**
 * @minItems 1
 * @maxItems 1
 */
export type Args = [ConsoleSnapshot]
export type BootId = string
export type Connected = boolean
export type Fault = string | null
export type FramesReceived = number
export type Interface = "kcan"
export type EmittedAt = string
export type ProtocolVersion = 1
export type Revision = number
export type Event = "console.snapshot"

export interface ConsoleLiveSocketContract {
  protocol_version: 1
  server_to_client_event: ConsoleSnapshotEvent
}
export interface ConsoleSnapshotEvent {
  args: Args
  event: Event
}
export interface ConsoleSnapshot {
  boot_id: BootId
  data: ConsoleSnapshotData
  emitted_at: EmittedAt
  protocol_version: ProtocolVersion
  revision: Revision
}
export interface ConsoleSnapshotData {
  can: ConsoleCanState
}
export interface ConsoleCanState {
  connected: Connected
  fault: Fault
  frames_received: FramesReceived
  interface: Interface
}

export const CONSOLE_PROTOCOL_VERSION = 1 as const

type SocketEvent = { event: string; args: unknown[] }
type SocketEventMap<Event extends SocketEvent> = {
  [Name in Event["event"]]: (
    ...args: Extract<Event, { event: Name }>["args"]
  ) => void
}

export type ConsoleServerEvents = SocketEventMap<ConsoleSnapshotEvent>
export type ConsoleSnapshotPayload = Parameters<
  ConsoleServerEvents["console.snapshot"]
>[0]
