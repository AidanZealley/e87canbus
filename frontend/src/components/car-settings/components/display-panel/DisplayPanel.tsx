import { DASHBOARD_OPTIONS, resolveDashboard } from "@/components/car-drive"
import type { ApplicationSettingsValues } from "../../types"
import { SettingsChoice } from "../settings-choice"
import { SettingsGroup } from "../settings-group"

type DisplayPanelProps = {
  values: ApplicationSettingsValues
  disabled?: boolean
  onChange: (patch: Partial<ApplicationSettingsValues>) => void
}

export const DisplayPanel = ({
  values,
  disabled = false,
  onChange,
}: DisplayPanelProps) => {
  // Options come from the dashboard catalog itself, so a new dashboard appears
  // here without this panel changing. A stored id no build recognizes shows as
  // the fallback, matching what the drive screen is actually rendering.
  const selected = resolveDashboard(values.dashboardId)

  return (
    <SettingsGroup
      title="Dashboard"
      description="Which dashboard the drive screen shows, and what it puts on it."
    >
      <SettingsChoice
        label="Layout"
        value={selected.id}
        disabled={disabled}
        options={DASHBOARD_OPTIONS.map(({ id, label }) => ({
          value: id,
          label,
        }))}
        onChange={(dashboardId) => onChange({ dashboardId })}
      />
      <p className="text-sm text-muted-foreground">{selected.description}</p>
    </SettingsGroup>
  )
}
