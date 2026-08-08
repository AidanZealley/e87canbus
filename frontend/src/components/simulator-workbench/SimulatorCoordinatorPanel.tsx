import { useState } from "react"

import {
  CoordinatorPanel,
  type CoordinatorPanelDisplay,
} from "@/components/coordinator-panel"

export const SimulatorCoordinatorPanel = () => {
  const [display, setDisplay] = useState<CoordinatorPanelDisplay>("ready")

  return (
    <section
      aria-labelledby="coordinator-panel-heading"
      className="grid min-w-0 gap-4 rounded-xl border bg-card p-3 text-card-foreground shadow-sm"
    >
      <div>
        <h2 id="coordinator-panel-heading" className="text-sm font-semibold">
          Coordinator panel
        </h2>
        <p className="text-xs text-muted-foreground">Local mock state</p>
      </div>

      <CoordinatorPanel
        display={display}
        onHotspotPress={() =>
          setDisplay((current) =>
            current === "ready" ? "hotspot_waiting" : "ready"
          )
        }
      />
    </section>
  )
}
