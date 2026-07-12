import { useCallback, useEffect, useMemo, useState } from "react"

import { connectSimulatorSocket, getSnapshot, pressButton, releaseButton, resetSimulator, stepSimulator, toggleButton } from "@/api/simulator"
import { SteeringStatus } from "@/dashboard/SteeringStatus"
import { CanTraceTable } from "@/simulator/CanTraceTable"
import { FrameDetail } from "@/simulator/FrameDetail"
import { LedGrid } from "@/simulator/LedGrid"
import { NeoTrellisPanel } from "@/simulator/NeoTrellisPanel"
import { SimulatorToolbar } from "@/simulator/SimulatorToolbar"
import type { CanTraceEntry, SimulatorEvent, SimulatorSnapshot } from "@/simulator/types"

const emptySnapshot: SimulatorSnapshot = {
  application: {
    vehicle_speed_kph: 0,
    steering_mode: "auto",
    manual_assistance_level: 0,
    strobe_active: false,
  },
  next_pressed: true,
  led_colours: {},
  trace: [],
}

export default function App() {
  const [snapshot, setSnapshot] = useState<SimulatorSnapshot>(emptySnapshot)
  const [selectedFrame, setSelectedFrame] = useState<CanTraceEntry | null>(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [autoScroll, setAutoScroll] = useState(true)
  const [pressedButtons, setPressedButtons] = useState<Set<number>>(new Set())

  const applySnapshot = useCallback((next: SimulatorSnapshot) => {
    const application = next.application ?? emptySnapshot.application
    const normalized = { ...next, application }
    setSnapshot(normalized)
    if (!next.application) {
      setError("The simulator backend is using an older API. Restart it to load application state")
    }
    setSelectedFrame((current) => {
      if (!current) return normalized.trace.at(-1) ?? null
      return normalized.trace.find((entry) => entry.monotonic_s === current.monotonic_s) ?? normalized.trace.at(-1) ?? null
    })
  }, [])

  useEffect(() => {
    void getSnapshot()
      .then((next) => {
        applySnapshot(next)
        if (next.application) setError(null)
      })
      .catch((cause: unknown) => {
        setConnected(false)
        setError(cause instanceof Error ? cause.message : "Could not load the simulator")
      })
  }, [applySnapshot])

  useEffect(() => {
    const socket = connectSimulatorSocket((event: SimulatorEvent) => {
      if (event.type === "snapshot") {
        applySnapshot(event.snapshot)
      }
    })
    socket.addEventListener("open", () => setConnected(true))
    socket.addEventListener("close", () => setConnected(false))
    socket.addEventListener("error", () => setConnected(false))
    return () => socket.close()
  }, [applySnapshot])

  const runCommand = useCallback(
    async (command: () => Promise<SimulatorSnapshot>) => {
      try {
        const next = await command()
        applySnapshot(next)
        if (next.application) setError(null)
      } catch (cause: unknown) {
        setError(cause instanceof Error ? cause.message : "Simulator command failed")
      }
    },
    [applySnapshot],
  )

  const handlePress = (index: number) => {
    setPressedButtons((current) => new Set(current).add(index))
    void runCommand(() => pressButton(index))
  }

  const handleRelease = (index: number) => {
    setPressedButtons((current) => {
      const next = new Set(current)
      next.delete(index)
      return next
    })
    void runCommand(() => releaseButton(index))
  }

  const ledColours = useMemo(() => snapshot.led_colours, [snapshot.led_colours])

  return (
    <div className="min-h-screen">
      <SimulatorToolbar
        connected={connected}
        autoScroll={autoScroll}
        onAutoScrollChange={setAutoScroll}
        onReset={() => {
          setPressedButtons(new Set())
          void runCommand(resetSimulator)
        }}
        onStep={() => void runCommand(() => stepSimulator(0))}
      />
      {error ? (
        <div role="alert" className="border-b border-red-300 bg-red-50 px-4 py-2 text-sm text-red-800">
          {error}. Check that the simulator backend is running on port 8000.
        </div>
      ) : null}
      <main className="grid gap-4 p-4 lg:grid-cols-[minmax(0,2fr)_minmax(280px,1fr)]">
        <section className="grid min-w-0 gap-4 md:grid-cols-2">
          <NeoTrellisPanel
            pressed={pressedButtons}
            onPress={handlePress}
            onRelease={handleRelease}
            onToggle={(index) => void runCommand(() => toggleButton(index))}
          />
          <LedGrid ledColours={ledColours} />
        </section>
        <SteeringStatus application={snapshot.application} />
        <section className="grid min-w-0 gap-4 lg:col-span-2 xl:grid-cols-[minmax(0,1fr)_300px]">
          <CanTraceTable
            trace={snapshot.trace}
            selected={selectedFrame}
            autoScroll={autoScroll}
            onSelect={setSelectedFrame}
          />
          <FrameDetail frame={selectedFrame} />
        </section>
      </main>
    </div>
  )
}
