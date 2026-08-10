import type { SpeedUnit, TemperatureUnit } from "@e87canbus/coordinator-client/api/http/types.gen"
import type { ApplicationSettingsValues } from "../../types"
import { SettingsChoice } from "../settings-choice"
import { SettingsGroup } from "../settings-group"

type UnitsPanelProps = {
  values: ApplicationSettingsValues
  disabled?: boolean
  onChange: (patch: Partial<ApplicationSettingsValues>) => void
}

export const UnitsPanel = ({
  values,
  disabled = false,
  onChange,
}: UnitsPanelProps) => (
  <SettingsGroup
    title="Display units"
    description="How speed and temperature are shown across the car display."
  >
    <SettingsChoice<SpeedUnit>
      label="Speed"
      value={values.speedUnit}
      disabled={disabled}
      options={[
        { value: "mph", label: "mph" },
        { value: "kmh", label: "km/h" },
      ]}
      onChange={(speedUnit) => onChange({ speedUnit })}
    />
    <SettingsChoice<TemperatureUnit>
      label="Temperature"
      value={values.temperatureUnit}
      disabled={disabled}
      options={[
        { value: "c", label: "Celsius" },
        { value: "f", label: "Fahrenheit" },
      ]}
      onChange={(temperatureUnit) => onChange({ temperatureUnit })}
    />
  </SettingsGroup>
)
