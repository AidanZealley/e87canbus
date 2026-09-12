import type { CoordinatorStatus } from "@e87canbus/coordinator-client/api/http/types.gen"
import { cn } from "@/lib/utils"

const statusLabels: Record<CoordinatorStatus, string> = {
  starting: "Starting",
  ready: "Ready",
  fault: "Fault",
  off: "Off",
}

const pixelAppearance: Record<CoordinatorStatus, string> = {
  starting:
    "bg-foreground/70 shadow-[0_0_0.45rem_rgb(255_255_255/0.2)] animate-panel-travel",
  ready: "bg-foreground/30",
  fault: "bg-destructive/75 shadow-[0_0_0.4rem_rgb(239_68_68/0.25)]",
  off: "bg-muted-foreground/15 shadow-none",
}

type CoordinatorPanelProps = {
  status: CoordinatorStatus
}

export const CoordinatorPanel = ({ status }: CoordinatorPanelProps) => {
  const label = statusLabels[status]

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
              pixelAppearance[status]
            )}
            style={
              status === "starting"
                ? { animationDelay: `${index * 140}ms` }
                : undefined
            }
          />
        ))}
      </div>
    </div>
  )
}
