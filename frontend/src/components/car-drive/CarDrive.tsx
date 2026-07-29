import { useEffectiveApplicationSettings } from "@/lib/application-settings-query"
import { resolveDashboard } from "./registry"

/**
 * Renders whichever dashboard the persisted settings name. While the settings
 * are loading or unreachable the effective settings supply the default id, so
 * the drive screen always has something to show.
 */
export const CarDrive = () => {
  const { settings } = useEffectiveApplicationSettings()
  const Dashboard = resolveDashboard(settings.dashboard_id).component

  return <Dashboard />
}
