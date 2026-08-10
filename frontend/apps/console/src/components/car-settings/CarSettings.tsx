import {
  CpuIcon,
  GaugeIcon,
  LayoutDashboardIcon,
  MonitorCogIcon,
  RulerIcon,
  ThermometerIcon,
} from "lucide-react"

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useEffectiveApplicationSettings } from "@e87canbus/coordinator-client/application-settings-query"
import { DevicesPanel } from "./components/devices-panel"
import { DisplayPanel } from "./components/display-panel"
import { SettingsUnavailable } from "./components/settings-unavailable"
import { ShiftPanel } from "./components/shift-panel"
import { SystemPanel } from "./components/system-panel"
import { TemperaturePanel } from "./components/temperature-panel"
import { UnitsPanel } from "./components/units-panel"
import { useSettingsCommit } from "./use-settings-commit"
import { settingsToValues } from "./utils"

const TABS = [
  { value: "units", label: "Units", icon: RulerIcon },
  { value: "temperature", label: "Temps", icon: ThermometerIcon },
  { value: "shift", label: "Shift", icon: GaugeIcon },
  { value: "display", label: "Display", icon: LayoutDashboardIcon },
  { value: "devices", label: "Devices", icon: CpuIcon },
  { value: "system", label: "System", icon: MonitorCogIcon },
] as const

const PANEL_CLASS = "grid content-start gap-8 p-4 sm:grid-cols-2"

export const CarSettings = () => {
  const { settings, isAuthoritative, error, isLoading, isRefetching, refetch } =
    useEffectiveApplicationSettings()
  const { commit, canCommit } = useSettingsCommit(settings)
  const values = settingsToValues(settings)

  const unavailable = (
    <SettingsUnavailable
      loading={isLoading}
      error={error}
      refetching={isRefetching}
      onRetry={refetch}
    />
  )

  return (
    <Tabs
      defaultValue="units"
      className="min-h-full gap-0"
      aria-labelledby="settings-title"
    >
      <div className="sticky top-0 z-20 grid gap-3 border-b bg-background/95 pt-4 backdrop-blur">
        <h1 id="settings-title" className="px-4 text-lg font-semibold">
          Settings
        </h1>
        <TabsList
          variant="line"
          className="-mb-px w-full justify-start gap-1 overflow-x-auto p-0 group-data-horizontal/tabs:h-auto"
        >
          {TABS.map(({ value, label, icon: Icon }) => (
            <TabsTrigger
              key={value}
              value={value}
              className="h-10 flex-none gap-2 px-3 pb-3 text-sm group-data-horizontal/tabs:after:bottom-0 group-data-horizontal/tabs:after:h-px [&_svg:not([class*='size-'])]:size-4"
            >
              <Icon aria-hidden="true" />
              {label}
            </TabsTrigger>
          ))}
        </TabsList>
      </div>

      <TabsContent value="units" className={PANEL_CLASS}>
        {isAuthoritative ? (
          <UnitsPanel
            values={values}
            disabled={!canCommit}
            onChange={(patch) => void commit(patch)}
          />
        ) : (
          unavailable
        )}
      </TabsContent>

      <TabsContent value="temperature" className={PANEL_CLASS}>
        {isAuthoritative ? (
          <TemperaturePanel
            values={values}
            disabled={!canCommit}
            onCommit={commit}
          />
        ) : (
          unavailable
        )}
      </TabsContent>

      <TabsContent value="shift" className={PANEL_CLASS}>
        {isAuthoritative ? (
          <ShiftPanel values={values} disabled={!canCommit} onCommit={commit} />
        ) : (
          unavailable
        )}
      </TabsContent>

      <TabsContent value="display" className={PANEL_CLASS}>
        {isAuthoritative ? (
          <DisplayPanel
            values={values}
            disabled={!canCommit}
            onChange={(patch) => void commit(patch)}
          />
        ) : (
          unavailable
        )}
      </TabsContent>

      <TabsContent value="devices" className={PANEL_CLASS}>
        <DevicesPanel />
      </TabsContent>

      <TabsContent value="system" className={PANEL_CLASS}>
        <SystemPanel />
      </TabsContent>
    </Tabs>
  )
}
