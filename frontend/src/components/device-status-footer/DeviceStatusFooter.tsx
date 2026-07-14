import type {
  DeviceId,
  DeviceSnapshot,
} from "@/components/simulator-workbench/types"
import { deviceOrUnavailable } from "@/components/simulator-workbench/utils"
import { cn } from "@/lib/utils"

const devicesInDisplayOrder: readonly { id: DeviceId; label: string }[] = [
  { id: "button_pad", label: "Button pad" },
  { id: "steering_controller", label: "Steering controller" },
]

export const DeviceStatusFooter = ({
  devices,
  className,
}: {
  devices: readonly DeviceSnapshot[]
  className?: string
}) => (
  <footer
    className={cn(
      "flex min-w-0 flex-wrap items-center gap-x-4 gap-y-1 border-t px-2 py-1 text-xs",
      className
    )}
    aria-label="Device status"
  >
    {devicesInDisplayOrder.map(({ id, label }) => {
      const device = deviceOrUnavailable(devices, id, label)
      const unavailable =
        device.status === "offline" && device.reason === "unavailable"
      const indicatorClass =
        device.status === "online"
          ? "bg-emerald-500"
          : device.status === "degraded"
            ? "bg-amber-500"
            : unavailable
              ? "bg-muted-foreground"
              : "bg-destructive"
      return (
        <div key={id} className="flex min-w-0 items-center gap-1.5">
          <span
            className={cn("size-2 shrink-0 rounded-full", indicatorClass)}
            aria-hidden="true"
          />
          <span className="truncate font-medium">{device.label}</span>
          <span
            className={cn(
              "capitalize",
              device.status === "offline" && !unavailable
                ? "text-destructive"
                : "text-muted-foreground"
            )}
          >
            {device.status}
          </span>
          {device.reason ? (
            <span className="max-w-40 truncate text-muted-foreground">
              — {device.reason}
            </span>
          ) : null}
        </div>
      )
    })}
  </footer>
)
