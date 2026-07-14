import { useState } from "react"
import { AlertTriangleIcon } from "lucide-react"

import {
  pressButton,
  releaseButton,
  resetSimulator,
  setVehicleSpeed,
  silenceVehicleSpeed,
  stepSimulator,
} from "@/api/simulator"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { NetworkTopology } from "./components/network-topology"
import { SimulatorToolbar } from "./components/simulator-toolbar"
import { SimulatedVehicleControls } from "./components/simulated-vehicle-controls"
import { SteeringCurveCard } from "./components/steering-curve-card"
import { SteeringStatus } from "./components/steering-status"
import {
  useSimulatorCommand,
  useSimulatorSocket,
  useSimulatorStatus,
  useActiveSteeringCurve,
  useApplicationSnapshot,
  useSteeringControllerSnapshot,
} from "./query"
import { SimulatorNeoTrellis } from "./SimulatorNeoTrellis"
import { SimulatorTrace } from "./SimulatorTrace"

export const SimulatorWorkbench = () => {
  const [autoScroll, setAutoScroll] = useState(true)
  const [pressedButtons, setPressedButtons] = useState<Set<number>>(new Set())
  const status = useSimulatorStatus()
  const application = useApplicationSnapshot()
  const activeCurve = useActiveSteeringCurve()
  const steeringController = useSteeringControllerSnapshot()
  const command = useSimulatorCommand()
  const connectionState = useSimulatorSocket(
    status.isFetched && !status.isError
  )
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
        connectionState={status.isError ? "disconnected" : connectionState}
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

        <div className="grid min-w-0 gap-4 lg:grid-cols-2 xl:grid-cols-[minmax(260px,0.8fr)_minmax(280px,1fr)_minmax(0,1.5fr)]">
          <section className="min-w-0">
            <SimulatorNeoTrellis
              pressedButtons={pressedButtons}
              onPress={handlePress}
              onRelease={handleRelease}
            />
          </section>
          <section className="min-w-0">
            <SimulatedVehicleControls
              speedKph={
                application.speed_valid ? application.vehicle_speed_kph : null
              }
              disabled={command.isPending}
              onSetSpeed={(speedKph) =>
                command.mutate(() => setVehicleSpeed(speedKph))
              }
              onSilenceSpeed={() => command.mutate(silenceVehicleSpeed)}
            />
          </section>
          <SteeringStatus />
        </div>

        {activeCurve ? (
          <section aria-label="Steering curve settings">
            <SteeringCurveCard
              activeCurve={activeCurve}
              speedKph={
                application.speed_valid ? application.vehicle_speed_kph : null
              }
              activeAssistance={
                application.speed_valid &&
                steeringController.last_command_reason === "auto"
                  ? steeringController.effective_assistance
                  : null
              }
            />
          </section>
        ) : null}

        <NetworkTopology />

        <SimulatorTrace autoScroll={autoScroll} />
      </main>
    </div>
  )
}

const errorMessage = (error: Error) =>
  error.message || "Simulator command failed."
