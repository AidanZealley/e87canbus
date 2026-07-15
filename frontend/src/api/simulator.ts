import type { DevicesState } from "./live-events.ts"

import { requestApi } from "./client.ts"

const requestSimulationCommand = async (
  path: string,
  init?: RequestInit
): Promise<void> => {
  await requestApi<unknown>(path, "Simulator", init)
}

export const resetSimulator = () =>
  requestSimulationCommand("/api/dev/simulation/reset", { method: "POST" })

export const pressButton = (index: number) =>
  requestSimulationCommand(
    `/api/dev/simulation/devices/button-pad/buttons/${index}/press`,
    { method: "POST" }
  )

export const releaseButton = (index: number) =>
  requestSimulationCommand(
    `/api/dev/simulation/devices/button-pad/buttons/${index}/release`,
    { method: "POST" }
  )

export const stepSimulator = (index: number) =>
  requestSimulationCommand("/api/dev/simulation/step", {
    method: "POST",
    body: JSON.stringify({ button_index: index }),
  })

export const setVehicleSpeed = (speedKph: number) =>
  requestSimulationCommand("/api/dev/simulation/vehicle/speed", {
    method: "PUT",
    body: JSON.stringify({ speed_kph: speedKph }),
  })

export const silenceVehicleSpeed = () =>
  requestSimulationCommand("/api/dev/simulation/vehicle/speed/silence", {
    method: "POST",
  })

export const setEngineRpm = (rpm: number) =>
  requestSimulationCommand("/api/dev/simulation/vehicle/rpm", {
    method: "PUT",
    body: JSON.stringify({ rpm }),
  })

export const silenceEngineRpm = () =>
  requestSimulationCommand("/api/dev/simulation/vehicle/rpm/silence", {
    method: "POST",
  })

export const setOilTemperature = (temperatureC: number) =>
  requestSimulationCommand("/api/dev/simulation/vehicle/oil-temperature", {
    method: "PUT",
    body: JSON.stringify({ temperature_c: temperatureC }),
  })

export const silenceOilTemperature = () =>
  requestSimulationCommand(
    "/api/dev/simulation/vehicle/oil-temperature/silence",
    {
      method: "POST",
    }
  )

export const setCoolantTemperature = (temperatureC: number) =>
  requestSimulationCommand("/api/dev/simulation/vehicle/coolant-temperature", {
    method: "PUT",
    body: JSON.stringify({ temperature_c: temperatureC }),
  })

export const silenceCoolantTemperature = () =>
  requestSimulationCommand(
    "/api/dev/simulation/vehicle/coolant-temperature/silence",
    {
      method: "POST",
    }
  )

type Device = DevicesState["devices"][number]

export const setDeviceStatus = (
  deviceId: Device["id"],
  status: Device["status"]
) =>
  requestSimulationCommand(`/api/dev/simulation/devices/${deviceId}/status`, {
    method: "PUT",
    body: JSON.stringify({ status }),
  })
