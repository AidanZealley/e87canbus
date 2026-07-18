import { useMutation } from "@tanstack/react-query"

import { resetSimulationMutation } from "@/api/http/@tanstack/react-query.gen"
import { NetworkTopology } from "./components/network-topology/NetworkTopology"
import { SimulatorToolbar } from "./components/simulator-toolbar"
import { SimulatedVehicleControls } from "./components/simulated-vehicle-controls/SimulatedVehicleControls"
import { SteeringCurveCard } from "./components/steering-curve-card"
import { LightingStatus } from "./components/lighting-status/LightingStatus"
import { useLiveStore } from "@/live/live-store"
import { SimulatorNeoTrellis } from "./SimulatorNeoTrellis"
import { SimulatorServotronic } from "./SimulatorServotronic"
import { SimulatorTrace } from "./SimulatorTrace"
import { notifySimulatorError } from "./utils"

const unavailableEngine = {
  rpm: { value: null, status: "stale" as const },
  oil_temperature_c: { value: null, status: "stale" as const },
  coolant_temperature_c: { value: null, status: "stale" as const },
}
export const SimulatorWorkbench = () => {
  const connection = useLiveStore((state) => state.connection)
  const reset = useMutation({
    ...resetSimulationMutation(),
    onError: notifySimulatorError,
  })

  return (
    <div className="min-h-svh bg-muted/30">
      <SimulatorToolbar
        connectionState={connection.status}
        onReset={() => {
          reset.mutate({})
        }}
        resetPending={reset.isPending}
      />

      <main className="mx-auto flex w-full max-w-[1600px] flex-col gap-4 p-4 lg:p-6">
        <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(280px,1fr)_minmax(0,2fr)]">
          <div className="grid min-w-0 gap-4 md:grid-cols-2 xl:grid-cols-1">
            <section className="min-w-0">
              <SimulatorNeoTrellis />
            </section>

            <section className="min-w-0">
              <LiveSimulatedVehicleControls />
            </section>
          </div>

          <LiveSteeringCurveCard />
        </div>

        <div className="grid min-w-0 gap-4 xl:grid-cols-2">
          <SimulatorServotronic />
          <LightingStatus />
          <NetworkTopology />
        </div>

        <SimulatorTrace />
      </main>
    </div>
  )
}

const LiveSimulatedVehicleControls = () => {
  const synchronized = useLiveStore((state) => state.connection.synchronized)
  const vehicle = useLiveStore((state) => state.vehicle)
  const engine = useLiveStore((state) => state.engine)
  const observedHighBeamEnabled = useLiveStore(
    (state) => state.lighting.observed_high_beam_enabled
  )

  return (
    <SimulatedVehicleControls
      speedKph={synchronized && vehicle.speed_valid ? vehicle.speed_kph : null}
      engine={synchronized ? engine : unavailableEngine}
      observedHighBeamEnabled={synchronized ? observedHighBeamEnabled : null}
    />
  )
}

const LiveSteeringCurveCard = () => {
  const synchronized = useLiveStore((state) => state.connection.synchronized)
  const steering = useLiveStore((state) => state.steering)
  const vehicle = useLiveStore((state) => state.vehicle)
  const servotronic = useLiveStore((state) => state.steering?.servotronic)

  if (
    !synchronized ||
    steering === null ||
    servotronic === undefined ||
    servotronic === null
  )
    return null

  return (
    <section className="min-w-0" aria-label="Steering curve settings">
      <SteeringCurveCard
        activeCurve={steering.active_curve}
        mode={steering.mode}
        speedKph={vehicle.speed_valid ? vehicle.speed_kph : null}
        activeAssistance={
          steering.maximum_assistance_active
            ? 1
            : steering.mode === "manual" || vehicle.speed_valid
              ? servotronic.effective_assistance
              : null
        }
      />
    </section>
  )
}
