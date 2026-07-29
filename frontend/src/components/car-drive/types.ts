import type { ComponentType } from "react"

/**
 * One dashboard the car display can render. The coordinator persists only the
 * id, so this catalog is the single place that knows which dashboards exist.
 */
export type DashboardDefinition = {
  id: string
  label: string
  description: string
  component: ComponentType
}
