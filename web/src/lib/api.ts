import type { SimulatorEvent, SimulatorSnapshot } from "@/lib/simulatorTypes"

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000"
const WS_BASE = import.meta.env.VITE_WS_BASE ?? "ws://127.0.0.1:8000/ws"

async function requestSnapshot(path: string, init?: RequestInit): Promise<SimulatorSnapshot> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  })
  if (!response.ok) {
    throw new Error(`Simulator API request failed: ${response.status}`)
  }
  return response.json() as Promise<SimulatorSnapshot>
}

export function getSnapshot() {
  return requestSnapshot("/api/snapshot")
}

export function resetSimulator() {
  return requestSnapshot("/api/reset", { method: "POST" })
}

export function pressButton(index: number) {
  return requestSnapshot(`/api/buttons/${index}/press`, { method: "POST" })
}

export function releaseButton(index: number) {
  return requestSnapshot(`/api/buttons/${index}/release`, { method: "POST" })
}

export function toggleButton(index: number) {
  return requestSnapshot(`/api/buttons/${index}/toggle`, { method: "POST" })
}

export function stepSimulator(index: number) {
  return requestSnapshot("/api/step", {
    method: "POST",
    body: JSON.stringify({ button_index: index }),
  })
}

export function connectSimulatorSocket(onEvent: (event: SimulatorEvent) => void) {
  const socket = new WebSocket(WS_BASE)
  socket.addEventListener("message", (message) => {
    onEvent(JSON.parse(message.data) as SimulatorEvent)
  })
  return socket
}
