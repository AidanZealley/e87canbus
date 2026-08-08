import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  connectSimulationHotspotClientMutation,
  disconnectSimulationHotspotClientMutation,
  failNextSimulationHotspotOperationMutation,
  getSimulationCoordinatorPanelOptions,
  getSimulationCoordinatorPanelQueryKey,
  pressSimulationCoordinatorPanelButtonMutation,
  previewSimulationCoordinatorStatusMutation,
} from "@/api/http/@tanstack/react-query.gen"
import type {
  CoordinatorStatus,
  SimulationCoordinatorPanelState,
} from "@/api/http/types.gen"
import { CoordinatorPanel } from "@/components/coordinator-panel"
import { Button } from "@/components/ui/button"
import { notifySimulatorError } from "./utils"

export const SimulatorCoordinatorPanel = () => {
  const queryClient = useQueryClient()
  const panel = useQuery({
    ...getSimulationCoordinatorPanelOptions(),
    refetchInterval: 500,
  })
  const updatePanel = (state: SimulationCoordinatorPanelState) =>
    queryClient.setQueryData(getSimulationCoordinatorPanelQueryKey(), state)
  const press = useMutation({
    ...pressSimulationCoordinatorPanelButtonMutation(),
    onSuccess: updatePanel,
    onError: notifySimulatorError,
  })
  const connect = useMutation({
    ...connectSimulationHotspotClientMutation(),
    onSuccess: updatePanel,
    onError: notifySimulatorError,
  })
  const disconnect = useMutation({
    ...disconnectSimulationHotspotClientMutation(),
    onSuccess: updatePanel,
    onError: notifySimulatorError,
  })
  const fail = useMutation({
    ...failNextSimulationHotspotOperationMutation(),
    onSuccess: updatePanel,
    onError: notifySimulatorError,
  })
  const preview = useMutation({
    ...previewSimulationCoordinatorStatusMutation(),
    onSuccess: updatePanel,
    onError: notifySimulatorError,
  })
  const mutationPending =
    press.isPending ||
    connect.isPending ||
    disconnect.isPending ||
    fail.isPending ||
    preview.isPending

  return (
    <section
      aria-labelledby="coordinator-panel-heading"
      className="grid min-w-0 gap-4 rounded-xl border bg-card p-3 text-card-foreground shadow-sm"
    >
      <div>
        <h2 id="coordinator-panel-heading" className="text-sm font-semibold">
          Coordinator panel
        </h2>
        <p className="text-xs text-muted-foreground">
          {panel.data
            ? `Coordinator ${panel.data.coordinator_status}; hotspot ${panel.data.hotspot_status}`
            : "Loading shared service state"}
        </p>
      </div>

      {panel.data ? (
        <>
          <CoordinatorPanel
            display={panel.data.display}
            onHotspotPress={() => press.mutate({})}
          />
          <div className="flex flex-wrap gap-2">
            <label className="grid gap-1 text-xs text-muted-foreground">
              Coordinator condition
              <select
                className="h-8 rounded-md border bg-background px-2 text-foreground"
                aria-label="Coordinator condition"
                value={panel.data.coordinator_status_preview ?? "live"}
                disabled={mutationPending}
                onChange={(event) =>
                  preview.mutate({
                    body: {
                      status:
                        event.target.value === "live"
                          ? null
                          : (event.target.value as CoordinatorStatus),
                    },
                  })
                }
              >
                <option value="live">Live controller</option>
                <option value="starting">Starting</option>
                <option value="fault">Fault</option>
                <option value="off">Off</option>
              </select>
            </label>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={mutationPending}
              onClick={() => connect.mutate({})}
            >
              Connect client
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={mutationPending}
              onClick={() => disconnect.mutate({})}
            >
              Disconnect client
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={mutationPending || panel.data.failure_armed}
              onClick={() => fail.mutate({})}
            >
              {panel.data.failure_armed
                ? "Next operation will fail"
                : "Fail next operation"}
            </Button>
          </div>
        </>
      ) : null}
    </section>
  )
}
