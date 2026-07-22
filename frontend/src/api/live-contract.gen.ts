/** Generated from protocol/live-events-v1.schema.json. Do not edit. */

export type ClientToServerEvent = ControllerResyncEvent | TraceSubscribeEvent | TraceUnsubscribeEvent
/**
 * @minItems 0
 * @maxItems 0
 */
export type Args = []
export type Event = "controller.resync"
/**
 * @minItems 0
 * @maxItems 0
 */
export type Args1 = []
export type Event1 = "trace.subscribe"
/**
 * @minItems 0
 * @maxItems 0
 */
export type Args2 = []
export type Event2 = "trace.unsubscribe"
export type ServerToClientEvent =
  | ControllerSnapshotEvent
  | VehicleStateEvent
  | EngineStateEvent
  | SteeringStateEvent
  | ButtonsStateEvent
  | LightingStateEvent
  | DevicesStateEvent
  | ControllerHealthEvent
  | ResourcesChangedEvent
  | TraceBatchEvent
/**
 * @minItems 1
 * @maxItems 1
 */
export type Args3 = [LiveEnvelopeControllerSnapshotData]
export type BootId = string
/**
 * @minItems 1
 * @maxItems 16
 */
export type Commands = [
  [
    number,
    number,
    number,
    number,
    number,
    number,
    number,
    number,
    number,
    number,
    number,
    number,
    number,
    number,
    number,
    number,
  ],
  ...[
    number,
    number,
    number,
    number,
    number,
    number,
    number,
    number,
    number,
    number,
    number,
    number,
    number,
    number,
    number,
    number,
  ][],
]
export type Encoding = "e87-button-pad-v2"
export type Generation = number
export type Bitrate = number
export type Connected = boolean
export type Id = "kcan" | "ptcan" | "fcan"
export type Interface = string
export type Label = string
export type Nodes = string[]
export type Networks = NetworkState[]
export type DeviceId = number
export type DeviceSessionId = number | null
export type Label1 = string
export type LastStatusCode = number | null
export type LastTransitionMonotonicS = number | null
export type ProtocolVersion = number | null
export type Role = "button_pad" | "servotronic_controller"
export type SourceMode = "physical" | "emulated" | "disabled"
export type Status = "disabled" | "not_found" | "pending" | "active" | "stale" | "incompatible" | "fault"
export type Status1 = "valid" | "never_observed" | "stale"
export type Value = number | number | null
export type Kind = "can_reader" | "can_effect_execution" | "steering_actuator" | "inbox_overflow" | "device_adapter"
export type Message = string
export type MonotonicS = number
export type Role1 = "button_pad" | "servotronic_controller"
export type Devices = DeviceHealthState[]
export type Fatal = boolean
export type Capacity = number
export type CurrentLatencyS = number
export type Depth = number
export type LatencyWarning = boolean
export type OverflowLatched = boolean
export type Network = "kcan" | "ptcan" | "fcan"
export type Networks1 = NetworkHealthState[]
export type Available = boolean
export type Fault = string | null
export type Failures = number
export type Fault1 = string | null
export type ResourceChangesDropped = number
export type Running = boolean
export type TraceRowsDropped = number
export type TransportQueueSaturations = number
export type Ready = boolean
export type HighBeamEnabled = boolean
export type HighBeamStrobeActive = boolean
export type HighBeamStrobeCyclesRemaining = number
export type ObservedHighBeamEnabled = boolean | null
export type SimulationSessionId = number | null
export type ActivationRevision = number
/**
 * @minItems 8
 * @maxItems 8
 */
export type Points = [
  SteeringCurvePoint,
  SteeringCurvePoint,
  SteeringCurvePoint,
  SteeringCurvePoint,
  SteeringCurvePoint,
  SteeringCurvePoint,
  SteeringCurvePoint,
  SteeringCurvePoint,
]
export type AssistancePerMille = number
export type SpeedDeciKph = number
export type SchemaVersion = 1
export type Fingerprint = string
export type SavedProfileId = string | null
export type SavedProfileRevision = number | null
export type Status2 = "active" | "activating" | "activation_failed"
export type CurveActivationAvailable = boolean
export type ManualAssistanceLevel = number
export type ManualAssistanceLevelCount = number
export type MaximumAssistanceActive = boolean
export type Mode = "auto" | "manual"
export type ActiveCurveCrc32 = number | null
export type ActiveCurveRevision = number | null
export type ActiveCurveSource = ("builtin_fallback" | "coordinator_ram") | null
export type EffectiveAssistance = number
export type InhibitReason = string | null
export type LastCommandReason =
  | (
      | "auto"
      | "manual"
      | "maximum"
      | "speed_never_observed"
      | "speed_stale"
      | "can_reader_failure"
      | "inbox_overflow"
      | "shutdown"
    )
  | null
export type ObservedSpeedKph = number | null
export type PwmDuty = number | null
export type SpeedFresh = boolean | null
export type WatchdogTimedOut = boolean
export type Buttons = number
export type Devices1 = number
export type Engine = number
export type Health = number
export type Lighting = number
export type Steering = number
export type Vehicle = number
export type SpeedKph = number
export type SpeedValid = boolean
export type EmittedAt = string
export type ProtocolVersion1 = 1
export type Revision = number
export type Event3 = "controller.snapshot"
/**
 * @minItems 1
 * @maxItems 1
 */
export type Args4 = [LiveEnvelopeVehicleState]
export type BootId1 = string
export type EmittedAt1 = string
export type ProtocolVersion2 = 1
export type Revision1 = number
export type Event4 = "vehicle.state"
/**
 * @minItems 1
 * @maxItems 1
 */
export type Args5 = [LiveEnvelopeEngineState]
export type BootId2 = string
export type EmittedAt2 = string
export type ProtocolVersion3 = 1
export type Revision2 = number
export type Event5 = "engine.state"
/**
 * @minItems 1
 * @maxItems 1
 */
export type Args6 = [LiveEnvelopeSteeringState]
export type BootId3 = string
export type EmittedAt3 = string
export type ProtocolVersion4 = 1
export type Revision3 = number
export type Event6 = "steering.state"
/**
 * @minItems 1
 * @maxItems 1
 */
export type Args7 = [LiveEnvelopeButtonsState]
export type BootId4 = string
export type EmittedAt4 = string
export type ProtocolVersion5 = 1
export type Revision4 = number
export type Event7 = "buttons.state"
/**
 * @minItems 1
 * @maxItems 1
 */
export type Args8 = [LiveEnvelopeLightingState]
export type BootId5 = string
export type EmittedAt5 = string
export type ProtocolVersion6 = 1
export type Revision5 = number
export type Event8 = "lighting.state"
/**
 * @minItems 1
 * @maxItems 1
 */
export type Args9 = [LiveEnvelopeDevicesState]
export type BootId6 = string
export type EmittedAt6 = string
export type ProtocolVersion7 = 1
export type Revision6 = number
export type Event9 = "devices.state"
/**
 * @minItems 1
 * @maxItems 1
 */
export type Args10 = [LiveEnvelopeControllerHealthState]
export type BootId7 = string
export type EmittedAt7 = string
export type ProtocolVersion8 = 1
export type Revision7 = number
export type Event10 = "controller.health"
/**
 * @minItems 1
 * @maxItems 1
 */
export type Args11 = [ResourceChangedEvent]
export type Id1 = string | null
export type Resource = "settings" | "steering_profile"
export type Revision8 = number
export type Type = "resources.changed"
export type Event11 = "resources.changed"
/**
 * @minItems 1
 * @maxItems 1
 */
export type Args12 = [LiveEnvelopeTraceBatchData]
export type BootId8 = string
export type ArbitrationId = number
export type ArbitrationIdHex = string
export type DataHex = string
export type IsExtendedId = boolean
export type MonotonicS1 = number
export type Network1 = "kcan" | "ptcan" | "fcan"
export type Sequence = number
export type SessionId = number
export type Source = string
export type Type1 = "frame"
export type Rows = TraceRow[]
export type EmittedAt8 = string
export type ProtocolVersion9 = 1
export type Revision9 = number
export type Event12 = "trace.batch"

/**
 * Generated Socket.IO protocol contract. The protocol version is encoded in each server payload envelope and in this document's identifier.
 */
export interface LiveSocketContract {
  client_to_server_event: ClientToServerEvent
  protocol_version: 1
  server_to_client_event: ServerToClientEvent
}
export interface ControllerResyncEvent {
  args: Args
  event: Event
}
export interface TraceSubscribeEvent {
  args: Args1
  event: Event1
}
export interface TraceUnsubscribeEvent {
  args: Args2
  event: Event2
}
export interface ControllerSnapshotEvent {
  args: Args3
  event: Event3
}
export interface LiveEnvelopeControllerSnapshotData {
  boot_id: BootId
  data: ControllerSnapshotData
  emitted_at: EmittedAt
  protocol_version: ProtocolVersion1
  revision: Revision
}
export interface ControllerSnapshotData {
  buttons: ButtonsState
  devices: DevicesState
  engine: EngineState
  health: ControllerHealthState
  lighting: LightingState
  simulation_session_id: SimulationSessionId
  steering: SteeringState
  topic_revisions: TopicRevisions
  vehicle: VehicleState
}
export interface ButtonsState {
  program: ButtonPadProgramState
}
export interface ButtonPadProgramState {
  commands: Commands
  encoding: Encoding
  generation: Generation
}
export interface DevicesState {
  networks: Networks
  registry: DeviceRegistryState
}
export interface NetworkState {
  bitrate: Bitrate
  connected: Connected
  id: Id
  interface: Interface
  label: Label
  nodes: Nodes
}
export interface DeviceRegistryState {
  button_pad: DeviceRegistryEntryState
  servotronic_controller: DeviceRegistryEntryState
}
export interface DeviceRegistryEntryState {
  device_id: DeviceId
  device_session_id: DeviceSessionId
  label: Label1
  last_status_code: LastStatusCode
  last_transition_monotonic_s: LastTransitionMonotonicS
  protocol_version: ProtocolVersion
  role: Role
  source_mode: SourceMode
  status: Status
}
export interface EngineState {
  coolant_temperature_c: EngineTelemetryValue
  oil_temperature_c: EngineTelemetryValue
  rpm: EngineTelemetryValue
}
export interface EngineTelemetryValue {
  status: Status1
  value: Value
}
export interface ControllerHealthState {
  devices: Devices
  fatal: Fatal
  inbox: InboxHealthState
  networks: Networks1
  persistence: PersistenceHealthState
  publisher: PublisherHealthState
  ready: Ready
  steering: SteeringCapabilityHealthState
}
export interface DeviceHealthState {
  fault: RuntimeFaultState | null
  role: Role1
}
export interface RuntimeFaultState {
  kind: Kind
  message: Message
  monotonic_s: MonotonicS
}
export interface InboxHealthState {
  capacity: Capacity
  current_latency_s: CurrentLatencyS
  depth: Depth
  latency_warning: LatencyWarning
  overflow_latched: OverflowLatched
}
export interface NetworkHealthState {
  fault: RuntimeFaultState | null
  network: Network
}
export interface PersistenceHealthState {
  available: Available
  fault: Fault
}
export interface PublisherHealthState {
  failures: Failures
  fault: Fault1
  resource_changes_dropped: ResourceChangesDropped
  running: Running
  trace_rows_dropped: TraceRowsDropped
  transport_queue_saturations: TransportQueueSaturations
}
export interface SteeringCapabilityHealthState {
  fault: RuntimeFaultState | null
}
export interface LightingState {
  high_beam_enabled: HighBeamEnabled
  high_beam_strobe_active: HighBeamStrobeActive
  high_beam_strobe_cycles_remaining: HighBeamStrobeCyclesRemaining
  observed_high_beam_enabled: ObservedHighBeamEnabled
}
export interface SteeringState {
  active_curve: ActiveSteeringCurveState
  curve_activation_available: CurveActivationAvailable
  manual_assistance_level: ManualAssistanceLevel
  manual_assistance_level_count: ManualAssistanceLevelCount
  maximum_assistance_active: MaximumAssistanceActive
  mode: Mode
  servotronic: ServotronicState | null
}
export interface ActiveSteeringCurveState {
  activation_revision: ActivationRevision
  definition: SteeringCurveDefinition
  fingerprint: Fingerprint
  saved_profile_id: SavedProfileId
  saved_profile_revision: SavedProfileRevision
  status: Status2
}
export interface SteeringCurveDefinition {
  points: Points
  schema_version: SchemaVersion
}
export interface SteeringCurvePoint {
  assistance_per_mille: AssistancePerMille
  speed_deci_kph: SpeedDeciKph
}
export interface ServotronicState {
  active_curve_crc32: ActiveCurveCrc32
  active_curve_revision: ActiveCurveRevision
  active_curve_source: ActiveCurveSource
  effective_assistance: EffectiveAssistance
  inhibit_reason: InhibitReason
  last_command_reason: LastCommandReason
  observed_speed_kph: ObservedSpeedKph
  pwm_duty: PwmDuty
  speed_fresh: SpeedFresh
  watchdog_timed_out: WatchdogTimedOut
}
export interface TopicRevisions {
  buttons: Buttons
  devices: Devices1
  engine: Engine
  health: Health
  lighting: Lighting
  steering: Steering
  vehicle: Vehicle
}
export interface VehicleState {
  speed_kph: SpeedKph
  speed_valid: SpeedValid
}
export interface VehicleStateEvent {
  args: Args4
  event: Event4
}
export interface LiveEnvelopeVehicleState {
  boot_id: BootId1
  data: VehicleState
  emitted_at: EmittedAt1
  protocol_version: ProtocolVersion2
  revision: Revision1
}
export interface EngineStateEvent {
  args: Args5
  event: Event5
}
export interface LiveEnvelopeEngineState {
  boot_id: BootId2
  data: EngineState
  emitted_at: EmittedAt2
  protocol_version: ProtocolVersion3
  revision: Revision2
}
export interface SteeringStateEvent {
  args: Args6
  event: Event6
}
export interface LiveEnvelopeSteeringState {
  boot_id: BootId3
  data: SteeringState
  emitted_at: EmittedAt3
  protocol_version: ProtocolVersion4
  revision: Revision3
}
export interface ButtonsStateEvent {
  args: Args7
  event: Event7
}
export interface LiveEnvelopeButtonsState {
  boot_id: BootId4
  data: ButtonsState
  emitted_at: EmittedAt4
  protocol_version: ProtocolVersion5
  revision: Revision4
}
export interface LightingStateEvent {
  args: Args8
  event: Event8
}
export interface LiveEnvelopeLightingState {
  boot_id: BootId5
  data: LightingState
  emitted_at: EmittedAt5
  protocol_version: ProtocolVersion6
  revision: Revision5
}
export interface DevicesStateEvent {
  args: Args9
  event: Event9
}
export interface LiveEnvelopeDevicesState {
  boot_id: BootId6
  data: DevicesState
  emitted_at: EmittedAt6
  protocol_version: ProtocolVersion7
  revision: Revision6
}
export interface ControllerHealthEvent {
  args: Args10
  event: Event10
}
export interface LiveEnvelopeControllerHealthState {
  boot_id: BootId7
  data: ControllerHealthState
  emitted_at: EmittedAt7
  protocol_version: ProtocolVersion8
  revision: Revision7
}
export interface ResourcesChangedEvent {
  args: Args11
  event: Event11
}
export interface ResourceChangedEvent {
  id: Id1
  resource: Resource
  revision: Revision8
  type: Type
}
export interface TraceBatchEvent {
  args: Args12
  event: Event12
}
export interface LiveEnvelopeTraceBatchData {
  boot_id: BootId8
  data: TraceBatchData
  emitted_at: EmittedAt8
  protocol_version: ProtocolVersion9
  revision: Revision9
}
export interface TraceBatchData {
  rows: Rows
}
export interface TraceRow {
  arbitration_id: ArbitrationId
  arbitration_id_hex: ArbitrationIdHex
  data_hex: DataHex
  is_extended_id: IsExtendedId
  monotonic_s: MonotonicS1
  network: Network1
  sequence: Sequence
  session_id: SessionId
  source: Source
  type: Type1
}

export const LIVE_PROTOCOL_VERSION = 1 as const

type SocketEvent = { event: string; args: unknown[] }

type SocketEventMap<Event extends SocketEvent> = {
  [Name in Event["event"]]: (
    ...args: Extract<Event, { event: Name }>["args"]
  ) => void
}

export type ServerToClientEvents = SocketEventMap<ServerToClientEvent>
export type ClientToServerEvents = SocketEventMap<ClientToServerEvent>
export type ServerEventPayload<Name extends keyof ServerToClientEvents> =
  Parameters<ServerToClientEvents[Name]>[0]
