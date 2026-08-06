import { WifiIcon } from "lucide-react"

import type { EffectiveDisplay } from "@/api/live-contract.gen"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

const displayLabels: Record<EffectiveDisplay, string> = {
  starting: "Starting",
  ready: "Ready",
  hotspot_waiting: "Hotspot waiting for a client",
  hotspot_connected: "Hotspot client connected",
  fault: "Fault",
  off: "Off",
}

const pixelAppearance: Record<EffectiveDisplay, string> = {
  starting:
    "bg-foreground/70 shadow-[0_0_0.45rem_rgb(255_255_255/0.2)] animate-panel-travel",
  ready: "bg-foreground/30",
  hotspot_waiting:
    "bg-cyan-400/70 shadow-[0_0_0.45rem_rgb(34_211_238/0.25)] animate-panel-pulse",
  hotspot_connected:
    "bg-emerald-500/75 shadow-[0_0_0.4rem_rgb(16_185_129/0.25)]",
  fault: "bg-destructive/75 shadow-[0_0_0.4rem_rgb(239_68_68/0.25)]",
  off: "bg-muted-foreground/15 shadow-none",
}

type CoordinatorPanelProps = {
  display: EffectiveDisplay
  onHotspotPress: () => void
  pressDisabled?: boolean
  pressPending?: boolean
}

export const CoordinatorPanel = ({
  display,
  onHotspotPress,
  pressDisabled = false,
  pressPending = false,
}: CoordinatorPanelProps) => {
  const label = displayLabels[display]

  return (
    <div className="grid max-w-xl gap-3">
      <div
        className="grid grid-cols-5 gap-1.5"
        role="img"
        aria-label={`Coordinator indicator: ${label}`}
      >
        {Array.from({ length: 5 }, (_, index) => (
          <span
            key={index}
            data-panel-light
            aria-hidden="true"
            className={cn(
              "h-1.5 rounded-full motion-reduce:animate-none",
              pixelAppearance[display]
            )}
            style={
              display === "starting"
                ? { animationDelay: `${index * 140}ms` }
                : undefined
            }
          />
        ))}
      </div>

      <Button
        type="button"
        size="sm"
        variant="outline"
        className="w-fit"
        aria-label="Press coordinator hotspot button"
        disabled={pressDisabled || pressPending}
        onClick={onHotspotPress}
      >
        <WifiIcon data-icon="inline-start" aria-hidden="true" />
        Hotspot
      </Button>
    </div>
  )
}
