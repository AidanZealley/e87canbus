import { useMutation } from "@tanstack/react-query"

import {
  setSimulatedHotspotClientMutation,
  setSimulatedHotspotFailureMutation,
  setSimulatedPanelLinkMutation,
  tapCoordinatorPanelButtonMutation,
  triggerCoordinatorFailureMutation,
} from "@/api/http/@tanstack/react-query.gen"
import { CoordinatorPanel } from "@/components/coordinator-panel"
import { Button } from "@/components/ui/button"
import { useLiveStore } from "@/live/live-store"
import { notifySimulatorError } from "./utils"

export const SimulatorCoordinatorPanel = () => {
  const synchronized = useLiveStore((state) => state.connection.synchronized)
  const localControls = useLiveStore((state) => state.localControls)
  const coordinatorFatal = useLiveStore((state) => state.health.fatal)
  const tap = useMutation({
    ...tapCoordinatorPanelButtonMutation(),
    onError: notifySimulatorError,
  })
  const setClient = useMutation({
    ...setSimulatedHotspotClientMutation(),
    onError: notifySimulatorError,
  })
  const setLink = useMutation({
    ...setSimulatedPanelLinkMutation(),
    onError: notifySimulatorError,
  })
  const setFailure = useMutation({
    ...setSimulatedHotspotFailureMutation(),
    onError: notifySimulatorError,
  })
  const failCoordinator = useMutation({
    ...triggerCoordinatorFailureMutation(),
    onError: notifySimulatorError,
  })

  if (!synchronized || localControls === null) return null

  const state = localControls.state
  const clientCanConnect = state.hotspot === "active"

  return (
    <section
      aria-labelledby="coordinator-panel-heading"
      className="grid min-w-0 gap-3 rounded-xl border bg-card p-3 text-card-foreground shadow-sm md:grid-cols-[minmax(14rem,1fr)_minmax(20rem,1.5fr)] md:items-center"
    >
      <div>
        <div className="mb-2">
          <h2 id="coordinator-panel-heading" className="text-sm font-semibold">
            Coordinator panel
          </h2>
        </div>
        <CoordinatorPanel
          display={state.effective_display}
          panelLink={state.panel_link}
          onHotspotPress={() => tap.mutate({})}
          pressDisabled={!synchronized}
          pressPending={tap.isPending}
        />
      </div>

      <div className="grid gap-3">
        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-4">
          <div>
            <dt className="text-muted-foreground">Hotspot</dt>
            <dd className="font-medium">{state.hotspot}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Client</dt>
            <dd className="font-medium">
              {state.client_connected ? "Connected" : "Disconnected"}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Panel link</dt>
            <dd className="font-medium">{state.panel_link}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Desired display</dt>
            <dd className="font-medium">{state.desired_display}</dd>
          </div>
        </dl>

        {state.diagnostic !== null ? (
          <p role="status" className="text-xs text-destructive">
            {state.diagnostic}
          </p>
        ) : null}

        <div className="flex flex-wrap gap-2" aria-label="Simulation causes">
          <Button
            size="sm"
            variant="outline"
            disabled={
              setClient.isPending ||
              (!state.client_connected && !clientCanConnect)
            }
            onClick={() =>
              setClient.mutate({
                body: { connected: !state.client_connected },
              })
            }
          >
            {state.client_connected ? "Disconnect laptop" : "Connect laptop"}
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={setLink.isPending}
            onClick={() =>
              setLink.mutate({
                body: { connected: state.panel_link === "disconnected" },
              })
            }
          >
            {state.panel_link === "connected"
              ? "Disconnect panel"
              : "Reconnect panel"}
          </Button>
          <Button
            size="sm"
            variant={state.hotspot === "fault" ? "outline" : "destructive"}
            disabled={setFailure.isPending}
            onClick={() =>
              setFailure.mutate({
                body: { enabled: state.hotspot !== "fault" },
              })
            }
          >
            {state.hotspot === "fault" ? "Recover hotspot" : "Fail hotspot"}
          </Button>
          <Button
            size="sm"
            variant="destructive"
            disabled={coordinatorFatal || failCoordinator.isPending}
            onClick={() => failCoordinator.mutate({})}
          >
            {coordinatorFatal ? "Coordinator failed" : "Fail coordinator"}
          </Button>
        </div>
      </div>
    </section>
  )
}
