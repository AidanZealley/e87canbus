import { useMutation } from "@tanstack/react-query"
import {
  CableIcon,
  CircleCheckIcon,
  CircleOffIcon,
  CircleXIcon,
  LaptopIcon,
  TriangleAlertIcon,
  UnplugIcon,
  WifiIcon,
  WifiOffIcon,
  type LucideIcon,
} from "lucide-react"

import type { EffectiveDisplay, Hotspot } from "@/api/live-contract.gen"
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
import { CoordinatorStatus } from "./components/coordinator-status"
import { notifySimulatorError } from "./utils"

const hotspotPresentation: Record<
  Hotspot,
  {
    icon?: LucideIcon
    label: string
    ongoing?: boolean
    tone: "positive" | "caution" | "negative" | "neutral"
  }
> = {
  disabled: { icon: WifiOffIcon, label: "Disabled", tone: "neutral" },
  activating: { label: "Activating", ongoing: true, tone: "caution" },
  active: { icon: WifiIcon, label: "Active", tone: "positive" },
  deactivating: { label: "Deactivating", ongoing: true, tone: "caution" },
  fault: { icon: CircleXIcon, label: "Fault", tone: "negative" },
}

const displayPresentation: Record<
  EffectiveDisplay,
  {
    icon?: LucideIcon
    label: string
    ongoing?: boolean
    tone: "positive" | "caution" | "negative" | "neutral" | "info"
  }
> = {
  starting: { label: "Starting", ongoing: true, tone: "caution" },
  ready: { icon: CircleCheckIcon, label: "Ready", tone: "positive" },
  hotspot_waiting: {
    label: "Waiting for client",
    ongoing: true,
    tone: "info",
  },
  hotspot_connected: {
    icon: WifiIcon,
    label: "Client connected",
    tone: "positive",
  },
  fault: { icon: TriangleAlertIcon, label: "Fault", tone: "negative" },
  off: { icon: CircleOffIcon, label: "Off", tone: "neutral" },
}

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
  const hotspot = hotspotPresentation[state.hotspot]
  const display = displayPresentation[state.desired_display]

  return (
    <section
      aria-labelledby="coordinator-panel-heading"
      className="grid min-w-0 gap-4 rounded-xl border bg-card p-3 text-card-foreground shadow-sm"
    >
      <h2 id="coordinator-panel-heading" className="text-sm font-semibold">
        Coordinator panel
      </h2>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <CoordinatorStatus
          label="Hotspot"
          value={hotspot.label}
          tone={hotspot.tone}
          icon={hotspot.icon}
          ongoing={hotspot.ongoing}
        />
        <CoordinatorStatus
          label="Client"
          value={state.client_connected ? "Connected" : "Disconnected"}
          tone={state.client_connected ? "positive" : "neutral"}
          icon={state.client_connected ? LaptopIcon : UnplugIcon}
        />
        <CoordinatorStatus
          label="Panel link"
          value={
            state.panel_link === "connected" ? "Connected" : "Disconnected"
          }
          tone={state.panel_link === "connected" ? "positive" : "negative"}
          icon={state.panel_link === "connected" ? CableIcon : UnplugIcon}
        />
        <CoordinatorStatus
          label="Desired display"
          value={display.label}
          tone={display.tone}
          icon={display.icon}
          ongoing={display.ongoing}
        />
      </div>

      {state.diagnostic !== null ? (
        <p role="status" className="text-xs text-destructive">
          {state.diagnostic}
        </p>
      ) : null}

      <CoordinatorPanel
        display={state.effective_display}
        onHotspotPress={() => tap.mutate({})}
        pressDisabled={!synchronized}
        pressPending={tap.isPending}
      />

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
    </section>
  )
}
