import { useMutation } from "@tanstack/react-query"

import { resetSimulationMutation } from "@e87canbus/coordinator-client/api/http/@tanstack/react-query.gen"
import { ButtonProfileEditor } from "@/components/button-profile-editor"
import { SimulatorToolbar } from "./components/simulator-toolbar"
import { useLiveStore } from "@e87canbus/coordinator-client/live/live-store"
import { SimulatorCoordinatorPanel } from "./SimulatorCoordinatorPanel"
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
        <SimulatorCoordinatorPanel />

        <section className="grid min-w-0 gap-3 rounded-xl border bg-card p-3 text-card-foreground shadow-sm">
          <div>
            <h2 className="text-sm font-semibold">Button profile</h2>
            <p className="text-xs text-muted-foreground">
              Configure the coordinator's button actions and indicators.
            </p>
          </div>
          <ButtonProfileEditor />
        </section>
      </main>
    </div>
  )
}
