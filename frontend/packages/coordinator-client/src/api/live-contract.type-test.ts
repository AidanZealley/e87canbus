import type {
  ClientToServerEvents,
  ServerEventPayload,
  ServerToClientEvents,
  VehicleState,
  SteeringCurveDefinition,
} from "./live-contract.gen"
import type { SteeringCurveDefinitionRequest } from "./http/types.gen"

type Equal<Left, Right> =
  (<Value>() => Value extends Left ? 1 : 2) extends <
    Value,
  >() => Value extends Right ? 1 : 2
    ? true
    : false
type Expect<Value extends true> = Value

type VehiclePayload = ServerEventPayload<"vehicle.state">

export type VehicleEventIsPreciselyEnveloped = Expect<
  Equal<VehiclePayload["data"], VehicleState>
>
export type VehicleEventHasOneArgument = Expect<
  Equal<Parameters<ServerToClientEvents["vehicle.state"]>, [VehiclePayload]>
>
export type ResyncEventHasNoArguments = Expect<
  Equal<Parameters<ClientToServerEvents["controller.resync"]>, []>
>
export type LiveSteeringCurveMatchesHttpRequest = Expect<
  Equal<SteeringCurveDefinition, SteeringCurveDefinitionRequest>
>
