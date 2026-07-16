import {
  CircleAlertIcon,
  CircleCheckIcon,
  type LucideIcon,
  PlugIcon,
  RotateCcwIcon,
  RouteOff,
  UnplugIcon,
} from "lucide-react"

import type {
  SimulatedDeviceAction,
  SimulatedDeviceStatusControl,
} from "./types"

export const actionLabels: Record<SimulatedDeviceAction, string> = {
  connect: "Connect",
  disconnect: "Disconnect",
  reboot: "Reboot",
  incompatible: "Simulate incompatible",
  "restore-compatible": "Restore compatible",
  "recover-and-incompatible": "Simulate incompatible",
  fault: "Set fault",
  "clear-fault": "Clear fault",
  "recover-and-fault": "Set fault",
}

export const actionIcons: Record<SimulatedDeviceAction, LucideIcon> = {
  connect: PlugIcon,
  disconnect: UnplugIcon,
  reboot: RotateCcwIcon,
  incompatible: RouteOff,
  "restore-compatible": CircleCheckIcon,
  "recover-and-incompatible": RouteOff,
  fault: CircleAlertIcon,
  "clear-fault": CircleCheckIcon,
  "recover-and-fault": CircleAlertIcon,
}

export const statusControls: {
  label: string
  value: SimulatedDeviceStatusControl
  iconAction: SimulatedDeviceAction
}[] = [
  {
    label: "Normal",
    value: "normal",
    iconAction: "restore-compatible",
  },
  {
    label: "Incompatible",
    value: "incompatible",
    iconAction: "incompatible",
  },
  {
    label: "Fault",
    value: "fault",
    iconAction: "fault",
  },
]
