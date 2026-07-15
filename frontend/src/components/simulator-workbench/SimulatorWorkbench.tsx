import { useState } from "react"
import { useMutation } from "@tanstack/react-query"

import { resetSimulator } from "@/api/simulator"
import { setMaximumAssistance } from "@/api/commands"
import { NetworkTopology } from "./components/network-topology/NetworkTopology"
import { SimulatorToolbar } from "./components/simulator-toolbar"
import { SimulatedVehicleControls } from "./components/simulated-vehicle-controls/SimulatedVehicleControls"
import { SteeringCurveCard } from "./components/steering-curve-card"
import { SteeringStatus } from "./components/steering-status/SteeringStatus"
import { useLiveStore } from "@/live/live-store"
import { SimulatorNeoTrellis } from "./SimulatorNeoTrellis"
import { SimulatorTrace } from "./SimulatorTrace"
import { notifySimulatorError } from "./utils"

const unavailableEngine = {
  rpm: { value: null, status: "stale" as const },
  oil_temperature_c: { value: null, status: "stale" as const },
  coolant_temperature_c: { value: null, status: "stale" as const },
}
export const SimulatorWorkbench = () => {
  const [autoScroll, setAutoScroll] = useState(true)
  const connection = useLiveStore((state) => state.connection)
  const synchronized = connection.synchronized
  const vehicle = useLiveStore((state) => state.vehicle)
  const engine = useLiveStore((state) => state.engine)
  const steering = useLiveStore((state) => state.steering)
  const steeringController = useLiveStore(
    (state) => state.devices.steering_controller
  )
  const reset = useMutation({
    mutationFn: resetSimulator,
    onError: notifySimulatorError,
  })
  const maximumAssistance = useMutation({
    mutationFn: setMaximumAssistance,
    onError: notifySimulatorError,
  })

  return (
    <div className="min-h-svh bg-muted/30">
      <SimulatorToolbar
        connectionState={connection.status}
        autoScroll={autoScroll}
        onAutoScrollChange={setAutoScroll}
        onReset={() => {
          reset.mutate()
        }}
        resetPending={reset.isPending}
      />

      <main className="mx-auto flex w-full max-w-[1600px] flex-col gap-4 p-4 lg:p-6">
        <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(280px,1fr)_minmax(0,2fr)]">
          <div className="grid min-w-0 gap-4 md:grid-cols-2 xl:grid-cols-1">
            <section className="min-w-0">
              <SimulatorNeoTrellis
                maximumAssistanceActive={
                  synchronized && steering !== null
                    ? steering.maximum_assistance_active
                    : false
                }
                semanticCommandPending={maximumAssistance.isPending}
                onMaximumAssistanceChange={(enabled) =>
                  maximumAssistance.mutate(enabled)
                }
              />
            </section>

            <section className="min-w-0">
              <SimulatedVehicleControls
                speedKph={
                  synchronized && vehicle.speed_valid ? vehicle.speed_kph : null
                }
                engine={synchronized ? engine : unavailableEngine}
              />
            </section>
          </div>

          {synchronized && steering !== null && steeringController !== null ? (
            <section className="min-w-0" aria-label="Steering curve settings">
              <SteeringCurveCard
                activeCurve={steering.active_curve}
                speedKph={vehicle.speed_valid ? vehicle.speed_kph : null}
                activeAssistance={steeringController.effective_assistance}
              />
            </section>
          ) : null}
        </div>

        <div className="grid min-w-0 gap-4 xl:grid-cols-2">
          <SteeringStatus />
          <NetworkTopology />
        </div>

        <SimulatorTrace autoScroll={autoScroll} />
      </main>
    </div>
  )
}
