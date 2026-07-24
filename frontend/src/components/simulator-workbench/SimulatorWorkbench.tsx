import { useMutation } from "@tanstack/react-query"

import { resetSimulationMutation } from "@/api/http/@tanstack/react-query.gen"
import { NetworkTopology } from "./components/network-topology/NetworkTopology"
import { SimulatorToolbar } from "./components/simulator-toolbar"
import { SimulatedVehicleControls } from "./components/simulated-vehicle-controls/SimulatedVehicleControls"
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

          <SimulatorServotronic />
        </div>

        <NetworkTopology />

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
