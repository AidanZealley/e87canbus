import type { DeviceRegistryEntryState } from "@/api/live-contract.gen"
import {
  connectSimulationDevice,
  disconnectSimulationDevice,
  rebootSimulationDevice,
  setSimulationDeviceProtocolVersion,
  setSimulationDeviceStatusCode,
} from "@/api/http/sdk.gen"
import type {
  SimulatedDeviceAction,
  SimulatedDeviceActionAvailability,
  SimulatedDeviceStatusControl,
} from "./types"

type DeviceStatus = DeviceRegistryEntryState["status"]
type ActionHandler = (
  role: DeviceRegistryEntryState["role"]
) => Promise<unknown>

const actionHandlers: Record<SimulatedDeviceAction, ActionHandler> = {
  connect: (role) => connectSimulationDevice({ path: { role } }),
  disconnect: (role) => disconnectSimulationDevice({ path: { role } }),
  reboot: (role) => rebootSimulationDevice({ path: { role } }),
  incompatible: (role) =>
    setSimulationDeviceProtocolVersion({
      path: { role },
      body: { protocol_version: 2 },
    }),
  "restore-compatible": (role) =>
    setSimulationDeviceProtocolVersion({
      path: { role },
      body: { protocol_version: 1 },
    }),
  "recover-and-incompatible": async (role) => {
    await setSimulationDeviceStatusCode({
      path: { role },
      body: { status_code: 0 },
    })
    await setSimulationDeviceProtocolVersion({
      path: { role },
      body: { protocol_version: 2 },
    })
  },
  fault: (role) =>
    setSimulationDeviceStatusCode({
      path: { role },
      body: { status_code: 1 },
    }),
  "clear-fault": (role) =>
    setSimulationDeviceStatusCode({
      path: { role },
      body: { status_code: 0 },
    }),
  "recover-and-fault": async (role) => {
    await setSimulationDeviceProtocolVersion({
      path: { role },
      body: { protocol_version: 1 },
    })
    await setSimulationDeviceStatusCode({
      path: { role },
      body: { status_code: 1 },
    })
  },
}

const actionAvailableStatuses: Record<SimulatedDeviceAction, DeviceStatus[]> = {
  connect: ["not_found", "stale"],
  disconnect: ["pending", "active", "stale", "incompatible", "fault"],
  reboot: ["pending", "active", "stale", "incompatible", "fault"],
  incompatible: ["disabled", "pending", "active", "stale", "fault"],
  "restore-compatible": ["incompatible"],
  "recover-and-incompatible": ["fault"],
  fault: ["active"],
  "clear-fault": ["fault"],
  "recover-and-fault": ["incompatible"],
}

const statusBadgeVariants: Record<
  DeviceStatus,
  "default" | "outline" | "warning" | "destructive"
> = {
  active: "default",
  disabled: "outline",
  not_found: "outline",
  pending: "warning",
  fault: "destructive",
  incompatible: "destructive",
  stale: "destructive",
}

const connectionActions: Record<DeviceStatus, "connect" | "disconnect"> = {
  disabled: "disconnect",
  not_found: "connect",
  pending: "disconnect",
  active: "disconnect",
  stale: "connect",
  incompatible: "disconnect",
  fault: "disconnect",
}

const statusControlsForStatus: Record<
  DeviceStatus,
  SimulatedDeviceStatusControl
> = {
  disabled: "normal",
  not_found: "normal",
  pending: "normal",
  active: "normal",
  stale: "normal",
  incompatible: "incompatible",
  fault: "fault",
}

const statusControlActions: Record<
  SimulatedDeviceStatusControl,
  Record<DeviceStatus, SimulatedDeviceAction | null>
> = {
  normal: {
    disabled: null,
    not_found: null,
    pending: null,
    active: null,
    stale: null,
    incompatible: "restore-compatible",
    fault: "clear-fault",
  },
  incompatible: {
    disabled: "incompatible",
    not_found: "incompatible",
    pending: "incompatible",
    active: "incompatible",
    stale: "incompatible",
    incompatible: null,
    fault: "recover-and-incompatible",
  },
  fault: {
    disabled: "fault",
    not_found: "fault",
    pending: "fault",
    active: "fault",
    stale: "fault",
    incompatible: "recover-and-fault",
    fault: null,
  },
}

export const runSimulatedDeviceAction = (
  role: DeviceRegistryEntryState["role"],
  action: SimulatedDeviceAction
) => actionHandlers[action](role)

export const simulatedDeviceActions = (
  entry: DeviceRegistryEntryState,
  synchronized: boolean
): SimulatedDeviceActionAvailability => {
  const controllable = synchronized && entry.source_mode === "emulated"
  return Object.fromEntries(
    Object.entries(actionAvailableStatuses).map(([action, statuses]) => [
      action,
      controllable && statuses.includes(entry.status),
    ])
  ) as SimulatedDeviceActionAvailability
}

export const formatStatus = (status: DeviceRegistryEntryState["status"]) =>
  status
    .replaceAll("_", " ")
    .replace(/^./, (character) => character.toUpperCase())

export const statusBadgeVariant = (
  status: DeviceRegistryEntryState["status"]
): "default" | "outline" | "warning" | "destructive" =>
  statusBadgeVariants[status]

export const connectionActionForStatus = (
  status: DeviceRegistryEntryState["status"]
): "connect" | "disconnect" => connectionActions[status]

export const statusControlForStatus = (
  status: DeviceRegistryEntryState["status"]
): SimulatedDeviceStatusControl => statusControlsForStatus[status]

export const statusActionForControl = (
  status: DeviceRegistryEntryState["status"],
  control: SimulatedDeviceStatusControl
): SimulatedDeviceAction | null => statusControlActions[control][status]
