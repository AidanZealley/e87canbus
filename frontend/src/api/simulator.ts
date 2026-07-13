import type {
  SimulatorEvent,
  SimulatorSnapshot,
} from "@/components/simulator-workbench/types"

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000"
const WS_BASE = import.meta.env.VITE_WS_BASE ?? "ws://127.0.0.1:8000/ws"

const requestSnapshot = async (
  path: string,
  init?: RequestInit
): Promise<SimulatorSnapshot> => {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  })

  if (!response.ok) {
    throw new Error(`Simulator API request failed: ${response.status}`)
  }

  return response.json() as Promise<SimulatorSnapshot>
}

export const getSnapshot = () => requestSnapshot("/api/snapshot")

export const resetSimulator = () =>
  requestSnapshot("/api/reset", { method: "POST" })

export const pressButton = (index: number) =>
  requestSnapshot(`/api/buttons/${index}/press`, { method: "POST" })

export const releaseButton = (index: number) =>
  requestSnapshot(`/api/buttons/${index}/release`, { method: "POST" })

export const stepSimulator = (index: number) =>
  requestSnapshot("/api/step", {
    method: "POST",
    body: JSON.stringify({ button_index: index }),
  })

export const connectSimulatorSocket = (
  onEvent: (event: SimulatorEvent) => void
) => {
  const socket = new WebSocket(WS_BASE)

  socket.addEventListener("message", (message) => {
    onEvent(JSON.parse(message.data) as SimulatorEvent)
  })

  return socket
}
