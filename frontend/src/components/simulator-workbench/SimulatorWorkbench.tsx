import { useMutation } from "@tanstack/react-query"

import { resetSimulationMutation } from "@/api/http/@tanstack/react-query.gen"
import { NetworkTopology } from "./components/network-topology/NetworkTopology"
import { SimulatorToolbar } from "./components/simulator-toolbar"
import { useLiveStore } from "@/live/live-store"
import { SimulatorNeoTrellis } from "./SimulatorNeoTrellis"
import { SimulatorServotronic } from "./SimulatorServotronic"
import { SimulatorTrace } from "./SimulatorTrace"
import { notifySimulatorError } from "./utils"

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
        <div className="grid min-w-0 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
          <section className="min-w-0">
            <SimulatorNeoTrellis />
          </section>

          <SimulatorServotronic />
        </div>

        <NetworkTopology />

        <SimulatorTrace />
      </main>
    </div>
  )
}
