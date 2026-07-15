import type {
  DeviceId,
  DeviceStatus,
  SimulatorSnapshot,
  SimulatorSocketEvent,
} from "@/components/simulator-workbench/types"

import { requestApi } from "./client.ts"

const WS_BASE = import.meta.env.VITE_WS_BASE ?? "ws://127.0.0.1:8000/ws"

const requestSnapshot = async (
  path: string,
  init?: RequestInit
): Promise<SimulatorSnapshot> => {
  return requestApi<SimulatorSnapshot>(path, "Simulator", init)
}

export const getSnapshot = () => requestSnapshot("/api/snapshot")

export const resetSimulator = () =>
  requestSnapshot("/api/dev/simulation/reset", { method: "POST" })

export const pressButton = (index: number) =>
  requestSnapshot(
    `/api/dev/simulation/devices/button-pad/buttons/${index}/press`,
    { method: "POST" }
  )

export const releaseButton = (index: number) =>
  requestSnapshot(
    `/api/dev/simulation/devices/button-pad/buttons/${index}/release`,
    { method: "POST" }
  )

export const stepSimulator = (index: number) =>
  requestSnapshot("/api/dev/simulation/step", {
    method: "POST",
    body: JSON.stringify({ button_index: index }),
  })

export const setVehicleSpeed = (speedKph: number) =>
  requestSnapshot("/api/dev/simulation/vehicle/speed", {
    method: "PUT",
    body: JSON.stringify({ speed_kph: speedKph }),
  })

export const silenceVehicleSpeed = () =>
  requestSnapshot("/api/dev/simulation/vehicle/speed/silence", {
    method: "POST",
  })

export const setEngineRpm = (rpm: number) =>
  requestSnapshot("/api/dev/simulation/vehicle/rpm", {
    method: "PUT",
    body: JSON.stringify({ rpm }),
  })

export const silenceEngineRpm = () =>
  requestSnapshot("/api/dev/simulation/vehicle/rpm/silence", {
    method: "POST",
  })

export const setOilTemperature = (temperatureC: number) =>
  requestSnapshot("/api/dev/simulation/vehicle/oil-temperature", {
    method: "PUT",
    body: JSON.stringify({ temperature_c: temperatureC }),
  })

export const silenceOilTemperature = () =>
  requestSnapshot("/api/dev/simulation/vehicle/oil-temperature/silence", {
    method: "POST",
  })

export const setCoolantTemperature = (temperatureC: number) =>
  requestSnapshot("/api/dev/simulation/vehicle/coolant-temperature", {
    method: "PUT",
    body: JSON.stringify({ temperature_c: temperatureC }),
  })

export const silenceCoolantTemperature = () =>
  requestSnapshot("/api/dev/simulation/vehicle/coolant-temperature/silence", {
    method: "POST",
  })

export const setDeviceStatus = (deviceId: DeviceId, status: DeviceStatus) =>
  requestSnapshot(`/api/dev/simulation/devices/${deviceId}/status`, {
    method: "PUT",
    body: JSON.stringify({ status }),
  })

export const connectSimulatorSocket = (
  onEvent: (event: SimulatorSocketEvent) => void,
  onHeartbeat: () => void
) => {
  const socket = new WebSocket(WS_BASE)

  socket.addEventListener("message", (message) => {
    const event = JSON.parse(message.data) as
      | SimulatorSocketEvent
      | {
          type: "heartbeat"
        }
    if (event.type === "heartbeat") {
      onHeartbeat()
      return
    }
    onEvent(event)
  })

  return socket
}
