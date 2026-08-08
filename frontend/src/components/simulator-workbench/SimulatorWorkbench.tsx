import { useMutation } from "@tanstack/react-query"
import { useState } from "react"

import { resetSimulationMutation } from "@/api/http/@tanstack/react-query.gen"
import { ButtonProfileEditor } from "@/components/button-profile-editor"
import { Button } from "@/components/ui/button"
import { NetworkTopology } from "./components/network-topology/NetworkTopology"
import { SimulatorToolbar } from "./components/simulator-toolbar"
import { useLiveStore } from "@/live/live-store"
import { SimulatorNeoTrellis } from "./SimulatorNeoTrellis"
import { SimulatorServotronic } from "./SimulatorServotronic"
import { SimulatorTrace } from "./SimulatorTrace"
import { notifySimulatorError } from "./utils"

export const SimulatorWorkbench = () => {
  const [editingButtons, setEditingButtons] = useState(false)
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
          <section className="grid min-w-0 content-start gap-2">
            <div className="flex justify-end">
              <Button
                size="sm"
                variant={editingButtons ? "default" : "outline"}
                aria-pressed={editingButtons}
                onClick={() => setEditingButtons((editing) => !editing)}
              >
                {editingButtons ? "Use button pad" : "Edit button profile"}
              </Button>
            </div>
            {editingButtons ? <ButtonProfileEditor /> : <SimulatorNeoTrellis />}
          </section>

          <SimulatorServotronic />
        </div>

        <NetworkTopology />

        <SimulatorTrace />
      </main>
    </div>
  )
}
