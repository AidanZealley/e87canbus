import { createContext, useContext } from "react"

import type { ApplicationSettings } from "@/api/settings"
import type {
  ApplicationSnapshot,
  DeviceSnapshot,
  SteeringControllerSnapshot,
} from "@/components/simulator-workbench/types"
import type { SimulatorConnectionState } from "@/components/simulator-workbench/connection"
import type { TemperatureSeverity } from "./car-ui"

export type CarData = {
  application: ApplicationSnapshot
  steeringController: SteeringControllerSnapshot
  devices: readonly DeviceSnapshot[]
  connectionState: SimulatorConnectionState
  connectionFault: boolean
  settings: ApplicationSettings
  settingsAuthoritative: boolean
  settingsFault: boolean
  settingsError: Error | null
  settingsLoading: boolean
  settingsRefetching: boolean
  settingsRefetch: () => Promise<void>
  oilSeverity: TemperatureSeverity
  coolantSeverity: TemperatureSeverity
}

export const CarDataContext = createContext<CarData | null>(null)

export const useCarData = () => {
  const value = useContext(CarDataContext)
  if (value === null) {
    throw new Error("useCarData must be used inside CarDataProvider")
  }
  return value
}
