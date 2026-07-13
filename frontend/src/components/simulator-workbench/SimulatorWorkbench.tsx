import { useCallback, useEffect, useState } from "react"
import { AlertTriangleIcon } from "lucide-react"

import {
  connectSimulatorSocket,
  getSnapshot,
  pressButton,
  releaseButton,
  resetSimulator,
  stepSimulator,
} from "@/api/simulator"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { CanTraceTable } from "./components/can-trace-table"
import { FrameDetail } from "./components/frame-detail"
import {
  NeoTrellisPanel,
  type NeoTrellisButton,
} from "./components/neo-trellis-panel"
import { SimulatorToolbar } from "./components/simulator-toolbar"
import { SteeringStatus } from "./components/steering-status"
import type { CanTraceEntry, SimulatorEvent, SimulatorSnapshot } from "./types"

const emptySnapshot: SimulatorSnapshot = {
  application: {
    vehicle_speed_kph: 0,
    steering_mode: "auto",
    manual_assistance_level: 0,
    maximum_assistance_active: false,
    strobe_active: false,
  },
  next_pressed: true,
  led_colours: {},
  trace: [],
}

export const SimulatorWorkbench = () => {
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
      setError(
        "The simulator backend is using an older API. Restart it to load application state."
      )
    }

    setSelectedFrame((current) => {
      const latest = normalized.trace.at(-1) ?? null

      if (!current) return latest

      return (
        normalized.trace.find(
          (entry) => entry.monotonic_s === current.monotonic_s
        ) ??
        latest
      )
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
        setError(
          cause instanceof Error
            ? cause.message
            : "Could not load the simulator."
        )
      })
  }, [applySnapshot])

  useEffect(() => {
    let cancelled = false
    const socket = connectSimulatorSocket((event: SimulatorEvent) => {
      if (!cancelled && event.type === "snapshot") applySnapshot(event.snapshot)
    })

    socket.addEventListener("open", () => {
      if (cancelled) {
        socket.close()
        return
      }

      setConnected(true)
    })
    socket.addEventListener("close", () => {
      if (!cancelled) setConnected(false)
    })
    socket.addEventListener("error", () => {
      if (!cancelled) setConnected(false)
    })

    return () => {
      cancelled = true
      if (socket.readyState === WebSocket.OPEN) socket.close()
    }
  }, [applySnapshot])

  const runCommand = useCallback(
    async (command: () => Promise<SimulatorSnapshot>) => {
      try {
        const next = await command()
        applySnapshot(next)
        if (next.application) setError(null)
      } catch (cause: unknown) {
        setError(
          cause instanceof Error ? cause.message : "Simulator command failed."
        )
      }
    },
    [applySnapshot]
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

  const neoTrellisButtons: NeoTrellisButton[] = Array.from(
    { length: 16 },
    (_, index) => ({
      index,
      pressed: pressedButtons.has(index),
      rgb: rgbForColourCode(snapshot.led_colours[String(index)] ?? 0),
    })
  )

  return (
    <div className="min-h-svh bg-muted/30">
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

      <main className="mx-auto flex w-full max-w-[1600px] flex-col gap-4 p-4 lg:p-6">
        {error ? (
          <Alert variant="destructive">
            <AlertTriangleIcon />
            <AlertTitle>Simulator unavailable</AlertTitle>
            <AlertDescription>
              {error} Check that the backend is running on port 8000.
            </AlertDescription>
          </Alert>
        ) : null}

        <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(280px,1fr)_minmax(0,2fr)]">
          <section className="min-w-0">
            <NeoTrellisPanel
              buttons={neoTrellisButtons}
              onPress={handlePress}
              onRelease={handleRelease}
            />
          </section>
          <SteeringStatus application={snapshot.application} />
        </div>

        <section className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
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

const rgbForColourCode = (
  colourCode: number
): NeoTrellisButton["rgb"] => {
  switch (colourCode) {
    case 1:
      return [255, 0, 0]
    case 2:
      return [0, 255, 0]
    case 3:
      return [0, 0, 255]
    case 4:
      return [255, 191, 0]
    case 5:
      return [255, 255, 255]
    default:
      return [0, 0, 0]
  }
}
