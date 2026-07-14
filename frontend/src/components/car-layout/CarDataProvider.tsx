import { useState, type ReactNode } from "react"

import type { ApplicationSnapshot } from "@/components/simulator-workbench/types"
import {
  useSimulatorSnapshot,
  useSimulatorSocket,
} from "@/components/simulator-workbench/query"
import { emptySnapshot } from "@/components/simulator-workbench/utils"
import { useEffectiveApplicationSettings } from "@/lib/application-settings-query"
import {
  maskDisconnectedTelemetry,
  transitionTemperatureSeverity,
  type TemperatureSeverity,
  type TemperatureThresholds,
} from "./car-ui"
import { CarDataContext } from "./car-data-context"

const thresholdKey = (thresholds: TemperatureThresholds) =>
  `${thresholds.warningC}:${thresholds.criticalC}`

type TemperatureSeverityMemory = {
  valueC: number | null
  status: ApplicationSnapshot["engine"]["oil_temperature_c"]["status"]
  connected: boolean
  thresholdKey: string
  severity: TemperatureSeverity
}

const useTemperatureSeverity = ({
  valueC,
  status,
  connected,
  thresholds,
}: {
  valueC: number | null
  status: ApplicationSnapshot["engine"]["oil_temperature_c"]["status"]
  connected: boolean
  thresholds: TemperatureThresholds
}) => {
  const { warningC, criticalC } = thresholds
  const currentThresholdKey = thresholdKey({ warningC, criticalC })
  const [memory, setMemory] = useState<TemperatureSeverityMemory>(() => ({
    valueC,
    status,
    connected,
    thresholdKey: currentThresholdKey,
    severity: transitionTemperatureSeverity({
      previous: "unavailable",
      valueC,
      status,
      connected,
      thresholds: { warningC, criticalC },
    }),
  }))
  const inputsChanged =
    memory.valueC !== valueC ||
    memory.status !== status ||
    memory.connected !== connected ||
    memory.thresholdKey !== currentThresholdKey
  if (!inputsChanged) return memory.severity

  const derivedSeverity = transitionTemperatureSeverity({
    previous: memory.severity,
    valueC,
    status,
    connected,
    thresholds: { warningC, criticalC },
    thresholdsChanged: memory.thresholdKey !== currentThresholdKey,
  })
  setMemory({
    valueC,
    status,
    connected,
    thresholdKey: currentThresholdKey,
    severity: derivedSeverity,
  })

  return derivedSeverity
}

export const CarDataProvider = ({ children }: { children: ReactNode }) => {
  const snapshot = useSimulatorSnapshot()
  const socketState = useSimulatorSocket(
    snapshot.isFetched && !snapshot.isError
  )
  const effectiveSettings = useEffectiveApplicationSettings()
  const connected = !snapshot.isError && socketState === "connected"
  const snapshotData = snapshot.data ?? emptySnapshot
  const application = maskDisconnectedTelemetry(
    snapshotData.application,
    connected
  )
  const settings = effectiveSettings.settings
  const oilSeverity = useTemperatureSeverity({
    valueC: application.engine.oil_temperature_c.value,
    status: application.engine.oil_temperature_c.status,
    connected,
    thresholds: {
      warningC: settings.oil_warning_c,
      criticalC: settings.oil_critical_c,
    },
  })
  const coolantSeverity = useTemperatureSeverity({
    valueC: application.engine.coolant_temperature_c.value,
    status: application.engine.coolant_temperature_c.status,
    connected,
    thresholds: {
      warningC: settings.coolant_warning_c,
      criticalC: settings.coolant_critical_c,
    },
  })

  const connectionState = snapshot.isError ? "disconnected" : socketState

  return (
    <CarDataContext
      value={{
        application,
        steeringController: snapshotData.steering_controller,
        devices: connected ? snapshotData.devices : [],
        connectionState,
        connectionFault: connectionState !== "connected",
        settings,
        settingsAuthoritative: effectiveSettings.isAuthoritative,
        settingsFault: effectiveSettings.persistenceFault,
        settingsError: effectiveSettings.error,
        settingsLoading: effectiveSettings.isLoading,
        oilSeverity,
        coolantSeverity,
      }}
    >
      {children}
    </CarDataContext>
  )
}
