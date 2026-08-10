import type { ApplicationSettingsValues, RpmField } from "../../types"
import { formatRpm, settingBounds } from "../../utils"
import { SettingsGroup } from "../settings-group"
import { SettingsSlider } from "../settings-slider"

type ShiftPanelProps = {
  values: ApplicationSettingsValues
  disabled?: boolean
  onCommit: (patch: Partial<ApplicationSettingsValues>) => Promise<void>
}

const SHIFT_FIELDS: { field: RpmField; label: string }[] = [
  { field: "shiftStage1Rpm", label: "Stage 1" },
  { field: "shiftStage2Rpm", label: "Stage 2" },
  { field: "redlineRpm", label: "Redline" },
]

export const ShiftPanel = ({
  values,
  disabled = false,
  onCommit,
}: ShiftPanelProps) => (
  <SettingsGroup
    title="Shift light"
    description="Where the RPM bar changes stage on the drive screen."
  >
    {SHIFT_FIELDS.map(({ field, label }) => (
      <SettingsSlider
        key={field}
        label={label}
        ariaLabel={`Shift ${label.toLowerCase()}`}
        value={values[field]}
        bounds={settingBounds(values, field)}
        disabled={disabled}
        format={formatRpm}
        onCommit={(value) => onCommit({ [field]: value })}
      />
    ))}
  </SettingsGroup>
)
