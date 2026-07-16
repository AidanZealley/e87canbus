import type { DeviceRegistryEntry } from "@/api/live-events"
import {
  connectSimulatedDevice,
  disconnectSimulatedDevice,
  rebootSimulatedDevice,
  setSimulatedDeviceProtocolVersion,
  setSimulatedDeviceStatusCode,
} from "@/api/simulator"
import type {
  SimulatedDeviceAction,
  SimulatedDeviceActionAvailability,
  SimulatedDeviceStatusControl,
} from "./types"

type DeviceStatus = DeviceRegistryEntry["status"]
type ActionHandler = (role: DeviceRegistryEntry["role"]) => Promise<void>

const actionHandlers: Record<SimulatedDeviceAction, ActionHandler> = {
  connect: connectSimulatedDevice,
  disconnect: disconnectSimulatedDevice,
  reboot: rebootSimulatedDevice,
  incompatible: (role) => setSimulatedDeviceProtocolVersion(role, 2),
  "restore-compatible": (role) => setSimulatedDeviceProtocolVersion(role, 1),
  "recover-and-incompatible": async (role) => {
    await setSimulatedDeviceStatusCode(role, 0)
    await setSimulatedDeviceProtocolVersion(role, 2)
  },
  fault: (role) => setSimulatedDeviceStatusCode(role, 1),
  "clear-fault": (role) => setSimulatedDeviceStatusCode(role, 0),
  "recover-and-fault": async (role) => {
    await setSimulatedDeviceProtocolVersion(role, 1)
    await setSimulatedDeviceStatusCode(role, 1)
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
  role: DeviceRegistryEntry["role"],
  action: SimulatedDeviceAction
) => actionHandlers[action](role)

export const simulatedDeviceActions = (
  entry: DeviceRegistryEntry,
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

export const formatStatus = (status: DeviceRegistryEntry["status"]) =>
  status
    .replaceAll("_", " ")
    .replace(/^./, (character) => character.toUpperCase())

export const statusBadgeVariant = (
  status: DeviceRegistryEntry["status"]
): "default" | "outline" | "warning" | "destructive" =>
  statusBadgeVariants[status]

export const connectionActionForStatus = (
  status: DeviceRegistryEntry["status"]
): "connect" | "disconnect" => connectionActions[status]

export const statusControlForStatus = (
  status: DeviceRegistryEntry["status"]
): SimulatedDeviceStatusControl => statusControlsForStatus[status]

export const statusActionForControl = (
  status: DeviceRegistryEntry["status"],
  control: SimulatedDeviceStatusControl
): SimulatedDeviceAction | null => statusControlActions[control][status]
