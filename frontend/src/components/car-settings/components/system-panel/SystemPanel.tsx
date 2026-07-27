import { LaptopIcon, MoonIcon, SunIcon } from "lucide-react"

import { useTheme } from "@/components/theme-provider"
import { SettingsChoice } from "../settings-choice"
import { SettingsGroup } from "../settings-group"

type Theme = "light" | "dark" | "system"

export const SystemPanel = () => {
  const { theme, setTheme } = useTheme()

  return (
    <SettingsGroup
      title="Appearance"
      description="Applies to this display only; it is not part of the saved settings document."
    >
      <SettingsChoice<Theme>
        label="Colour theme"
        value={theme}
        options={[
          { value: "light", label: "Light", icon: SunIcon },
          { value: "dark", label: "Dark", icon: MoonIcon },
          { value: "system", label: "System", icon: LaptopIcon },
        ]}
        onChange={setTheme}
      />
    </SettingsGroup>
  )
}
