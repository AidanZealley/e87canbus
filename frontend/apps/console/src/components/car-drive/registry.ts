import { ClassicDashboard } from "./components/classic-dashboard"
import { ClusterDashboard } from "./components/cluster-dashboard"
import type { DashboardDefinition } from "./types"

export const DEFAULT_DASHBOARD_ID = "classic"

/**
 * Keyed by plain string rather than a union of the known ids: the stored
 * choice is an arbitrary string the coordinator never validates against this
 * catalog, and lookups have to stay honest about that.
 */
export const DASHBOARDS: Record<string, DashboardDefinition> = {
  [DEFAULT_DASHBOARD_ID]: {
    id: DEFAULT_DASHBOARD_ID,
    label: "Classic",
    description: "Full indicator strip, RPM bar, speed and both temperatures.",
    component: ClassicDashboard,
  },
  cluster: {
    id: "cluster",
    label: "Cluster",
    description:
      "Ruled tachometer strip, one large speed readout, and oil and coolant modules on a dark binnacle.",
    component: ClusterDashboard,
  },
}

export const DASHBOARD_OPTIONS: readonly DashboardDefinition[] =
  Object.values(DASHBOARDS)

/**
 * A dashboard that was removed, renamed, or that only a newer build knows
 * about must not blank the drive screen, so anything unrecognized falls back.
 */
export const resolveDashboard = (id: string): DashboardDefinition =>
  DASHBOARDS[id] ?? DASHBOARDS[DEFAULT_DASHBOARD_ID]
