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
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
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
            <div className="grid gap-1">
              <Label
                htmlFor="coordinator-condition"
                className="text-xs text-muted-foreground"
              >
                Coordinator condition
              </Label>
              <Select
                value={panel.data.coordinator_status_preview ?? "live"}
                disabled={mutationPending}
                onValueChange={(value) =>
                  preview.mutate({
                    body: {
                      status:
                        value === "live"
                          ? null
                          : (value as CoordinatorStatus),
                    },
                  })
                }
              >
                <SelectTrigger id="coordinator-condition" className="w-40">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="live">Live controller</SelectItem>
                  <SelectItem value="starting">Starting</SelectItem>
                  <SelectItem value="fault">Fault</SelectItem>
                  <SelectItem value="off">Off</SelectItem>
                </SelectContent>
              </Select>
            </div>
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
