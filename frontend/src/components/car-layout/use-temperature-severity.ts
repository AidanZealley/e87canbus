import { useState } from "react"

import type { EngineTelemetryValue } from "@/api/live-events"
import {
  transitionTemperatureSeverity,
  type TemperatureSeverity,
  type TemperatureThresholds,
} from "./car-ui"

type SeverityMemory = {
  valueC: number | null
  status: EngineTelemetryValue["status"]
  connected: boolean
  thresholdsKey: string
  severity: TemperatureSeverity
}

export const useTemperatureSeverity = ({
  telemetry,
  connected,
  thresholds,
}: {
  telemetry: EngineTelemetryValue
  connected: boolean
  thresholds: TemperatureThresholds
}) => {
  const thresholdsKey = `${thresholds.warningC}:${thresholds.criticalC}`
  const [memory, setMemory] = useState<SeverityMemory>(() => ({
    valueC: telemetry.value,
    status: telemetry.status,
    connected,
    thresholdsKey,
    severity: transitionTemperatureSeverity({
      previous: "unavailable",
      valueC: telemetry.value,
      status: telemetry.status,
      connected,
      thresholds,
    }),
  }))
  if (
    memory.valueC === telemetry.value &&
    memory.status === telemetry.status &&
    memory.connected === connected &&
    memory.thresholdsKey === thresholdsKey
  ) {
    return memory.severity
  }
  const severity = transitionTemperatureSeverity({
    previous: memory.severity,
    valueC: telemetry.value,
    status: telemetry.status,
    connected,
    thresholds,
    thresholdsChanged: memory.thresholdsKey !== thresholdsKey,
  })
  setMemory({
    valueC: telemetry.value,
    status: telemetry.status,
    connected,
    thresholdsKey,
    severity,
  })
  return severity
}
