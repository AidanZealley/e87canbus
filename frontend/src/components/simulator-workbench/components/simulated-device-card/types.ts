import type { ReactNode } from "react"

import type { DeviceRegistryEntryState } from "@/api/live-contract.gen"

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
  role: DeviceRegistryEntryState["role"]
  registryEntry: DeviceRegistryEntryState
  availableActions: SimulatedDeviceActionAvailability
  callbacks: SimulatedDeviceActionCallbacks
  pendingAction?: SimulatedDeviceAction | null
  children: ReactNode
}
