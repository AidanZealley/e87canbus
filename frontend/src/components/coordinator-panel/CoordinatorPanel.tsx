import type { EffectiveDisplay, PanelLink } from "@/api/live-contract.gen"
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
    "bg-white/70 shadow-[0_0_0.6rem_rgb(255_255_255/0.35)] animate-panel-travel",
  ready: "bg-white/30 shadow-[0_0_0.35rem_rgb(255_255_255/0.18)]",
  hotspot_waiting:
    "bg-cyan-300/65 shadow-[0_0_0.65rem_rgb(103_232_249/0.35)] animate-panel-pulse",
  hotspot_connected:
    "bg-emerald-400/70 shadow-[0_0_0.55rem_rgb(52_211_153/0.3)]",
  fault: "bg-red-500/70 shadow-[0_0_0.55rem_rgb(239_68_68/0.35)]",
  off: "bg-black/50 shadow-none",
}

type CoordinatorPanelProps = {
  display: EffectiveDisplay
  panelLink: PanelLink
  onHotspotPress: () => void
  pressDisabled?: boolean
  pressPending?: boolean
}

export const CoordinatorPanel = ({
  display,
  panelLink,
  onHotspotPress,
  pressDisabled = false,
  pressPending = false,
}: CoordinatorPanelProps) => {
  const label = displayLabels[display]

  return (
    <div className="relative overflow-hidden rounded-xl border border-white/10 bg-zinc-950 p-4 text-zinc-100 shadow-sm">
      <div className="absolute inset-x-0 top-0 h-px bg-linear-to-r from-transparent via-white/25 to-transparent" />
      <div className="flex items-center gap-4">
        <div className="min-w-0 flex-1">
          <div
            className="flex h-7 items-center justify-between gap-1 rounded-full border border-white/10 bg-black/70 px-3"
            role="img"
            aria-label={`Coordinator indicator: ${label}`}
          >
            {Array.from({ length: 5 }, (_, index) => (
              <span
                key={index}
                aria-hidden="true"
                className={cn(
                  "size-2.5 rounded-full motion-reduce:animate-none",
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
          <p className="mt-2 truncate text-xs font-medium text-zinc-100">
            {label}
          </p>
          <p className="text-[0.6875rem] text-zinc-400">
            Panel link {panelLink}
          </p>
        </div>

        <Button
          type="button"
          size="icon-sm"
          variant="outline"
          className="size-9 shrink-0 rounded-full border-zinc-600 bg-zinc-900 text-zinc-100 hover:bg-zinc-800 hover:text-white"
          aria-label="Press coordinator hotspot button"
          disabled={pressDisabled || pressPending}
          onClick={onHotspotPress}
        >
          <span className="size-2 rounded-full border border-zinc-400 bg-zinc-700 shadow-inner" />
        </Button>
      </div>
    </div>
  )
}
