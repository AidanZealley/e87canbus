import type { ReactNode } from "react"

import type { DeviceRegistryEntry } from "@/api/live-events"

export type SimulatedDeviceAction =
  | "connect"
  | "disconnect"
  | "reboot"
  | "incompatible"
  | "restore-compatible"
  | "recover-and-incompatible"
  | "fault"
  | "clear-fault"
  | "recover-and-fault"

export type SimulatedDeviceActionAvailability = Record<
  SimulatedDeviceAction,
  boolean
>

export type SimulatedDeviceActionCallbacks = Partial<
  Record<SimulatedDeviceAction, () => void>
>

export type SimulatedDeviceStatusControl = "normal" | "incompatible" | "fault"

export type SimulatedDeviceCardProps = {
  role: DeviceRegistryEntry["role"]
  registryEntry: DeviceRegistryEntry
  availableActions: SimulatedDeviceActionAvailability
  callbacks: SimulatedDeviceActionCallbacks
  pendingAction?: SimulatedDeviceAction | null
  children: ReactNode
}
