import { requestApi } from "./client.ts"

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
