import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  getSimulationCoordinatorPanelOptions,
  getSimulationCoordinatorPanelQueryKey,
  previewSimulationCoordinatorStatusMutation,
} from "@e87canbus/coordinator-client/api/http/@tanstack/react-query.gen"
import type {
  CoordinatorStatus,
  SimulationCoordinatorPanelState,
} from "@e87canbus/coordinator-client/api/http/types.gen"
import { CoordinatorPanel } from "@/components/coordinator-panel"
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
  const preview = useMutation({
    ...previewSimulationCoordinatorStatusMutation(),
    onSuccess: updatePanel,
    onError: notifySimulatorError,
  })
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
            ? `Coordinator ${panel.data.coordinator_status}`
            : "Loading shared service state"}
        </p>
      </div>

      {panel.data ? (
        <>
          <CoordinatorPanel status={panel.data.coordinator_status} />
          <div className="grid gap-1">
            <Label
              htmlFor="coordinator-condition"
              className="text-xs text-muted-foreground"
            >
              Coordinator condition
            </Label>
            <Select
              value={panel.data.coordinator_status_preview ?? "live"}
              disabled={preview.isPending}
              onValueChange={(value) =>
                preview.mutate({
                  body: {
                    status:
                      value === "live" ? null : (value as CoordinatorStatus),
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
        </>
      ) : null}
    </section>
  )
}
