import { useState } from "react"
import { AlertTriangleIcon } from "lucide-react"

import {
  pressButton,
  releaseButton,
  resetSimulator,
  stepSimulator,
} from "@/api/simulator"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { NetworkTopology } from "./components/network-topology"
import { SimulatorToolbar } from "./components/simulator-toolbar"
import { SteeringStatus } from "./components/steering-status"
import {
  useSimulatorCommand,
  useSimulatorSocket,
  useSimulatorStatus,
} from "./query"
import { SimulatorNeoTrellis } from "./SimulatorNeoTrellis"
import { SimulatorTrace } from "./SimulatorTrace"

export const SimulatorWorkbench = () => {
  const [autoScroll, setAutoScroll] = useState(true)
  const [pressedButtons, setPressedButtons] = useState<Set<number>>(new Set())
  const status = useSimulatorStatus()
  const command = useSimulatorCommand()
  const connectionState = useSimulatorSocket(status.isFetched && !status.isError)
  const error = command.error ?? status.error

  const handlePress = (index: number) => {
    setPressedButtons((current) => new Set(current).add(index))
    command.mutate(() => pressButton(index))
  }

  const handleRelease = (index: number) => {
    setPressedButtons((current) => {
      const next = new Set(current)
      next.delete(index)
      return next
    })
    command.mutate(() => releaseButton(index))
  }

  return (
    <div className="min-h-svh bg-muted/30">
      <SimulatorToolbar
        connectionState={connectionState}
        autoScroll={autoScroll}
        onAutoScrollChange={setAutoScroll}
        onReset={() => {
          setPressedButtons(new Set())
          command.mutate(resetSimulator)
        }}
        onStep={() => command.mutate(() => stepSimulator(0))}
      />

      <main className="mx-auto flex w-full max-w-[1600px] flex-col gap-4 p-4 lg:p-6">
        {error ? (
          <Alert variant="destructive">
            <AlertTriangleIcon />
            <AlertTitle>Simulator unavailable</AlertTitle>
            <AlertDescription>
              {errorMessage(error)} Check that the backend is running on port
              8000.
            </AlertDescription>
          </Alert>
        ) : null}

        <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(280px,1fr)_minmax(0,2fr)]">
          <section className="min-w-0">
            <SimulatorNeoTrellis
              pressedButtons={pressedButtons}
              onPress={handlePress}
              onRelease={handleRelease}
            />
          </section>
          <SteeringStatus />
        </div>

        <NetworkTopology />

        <SimulatorTrace autoScroll={autoScroll} />
      </main>
    </div>
  )
}

const errorMessage = (error: Error) =>
  error.message || "Simulator command failed."
