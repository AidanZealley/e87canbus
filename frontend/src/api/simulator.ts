import { requestApi } from "./client.ts"
import type { DeviceRegistryEntry } from "./live-events"

const requestSimulationCommand = async (
  path: string,
  init?: RequestInit
): Promise<void> => {
  await requestApi<unknown>(path, "Simulator", init)
}

export const resetSimulator = () =>
  requestSimulationCommand("/api/dev/simulation/reset", { method: "POST" })

export const tapButton = (index: number) =>
  requestSimulationCommand(
    `/api/dev/simulation/devices/button-pad/buttons/${index}/tap`,
    { method: "POST" }
  )

type SimulatedDeviceRole = DeviceRegistryEntry["role"]

const devicePath = (role: SimulatedDeviceRole, action: string) =>
  `/api/dev/simulation/devices/${role}/${action}`

export const connectSimulatedDevice = (role: SimulatedDeviceRole) =>
  requestSimulationCommand(devicePath(role, "connect"), { method: "POST" })

export const disconnectSimulatedDevice = (role: SimulatedDeviceRole) =>
  requestSimulationCommand(devicePath(role, "disconnect"), { method: "POST" })

export const rebootSimulatedDevice = (role: SimulatedDeviceRole) =>
  requestSimulationCommand(devicePath(role, "reboot"), { method: "POST" })

export const setSimulatedDeviceProtocolVersion = (
  role: SimulatedDeviceRole,
  protocolVersion: number
) =>
  requestSimulationCommand(devicePath(role, "protocol-version"), {
    method: "PUT",
    body: JSON.stringify({ protocol_version: protocolVersion }),
  })

export const setSimulatedDeviceStatusCode = (
  role: SimulatedDeviceRole,
  statusCode: number
) =>
  requestSimulationCommand(devicePath(role, "status-code"), {
    method: "PUT",
    body: JSON.stringify({ status_code: statusCode }),
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
