import type { ApplicationSettingsValues, TemperatureField } from "../../types"
import { formatTemperature, settingBounds } from "../../utils"
import { SettingsGroup } from "../settings-group"
import { SettingsSlider } from "../settings-slider"

type TemperaturePanelProps = {
  values: ApplicationSettingsValues
  disabled?: boolean
  onCommit: (patch: Partial<ApplicationSettingsValues>) => Promise<void>
}

type TemperatureSlider = { field: TemperatureField; label: string }

const OIL_FIELDS: TemperatureSlider[] = [
  { field: "oilOperatingC", label: "Operating temperature" },
  { field: "oilWarningC", label: "Warning" },
  { field: "oilCriticalC", label: "Critical" },
]

const COOLANT_FIELDS: TemperatureSlider[] = [
  { field: "coolantOperatingC", label: "Operating temperature" },
  { field: "coolantWarningC", label: "Warning" },
  { field: "coolantCriticalC", label: "Critical" },
]

export const TemperaturePanel = ({
  values,
  disabled = false,
  onCommit,
}: TemperaturePanelProps) => {
  const sliders = (fields: TemperatureSlider[], group: string) =>
    fields.map(({ field, label }) => (
      <SettingsSlider
        key={field}
        label={label}
        ariaLabel={`${group} ${label.toLowerCase()}`}
        value={values[field]}
        bounds={settingBounds(values, field)}
        disabled={disabled}
        format={(value) => formatTemperature(value, values.temperatureUnit)}
        onCommit={(value) => onCommit({ [field]: value })}
      />
    ))

  return (
    <>
      <SettingsGroup
        title="Oil"
        description="Gauge banding and warnings for oil temperature."
      >
        {sliders(OIL_FIELDS, "Oil")}
      </SettingsGroup>
      <SettingsGroup
        title="Coolant"
        description="Gauge banding and warnings for coolant temperature."
      >
        {sliders(COOLANT_FIELDS, "Coolant")}
      </SettingsGroup>
    </>
  )
}
