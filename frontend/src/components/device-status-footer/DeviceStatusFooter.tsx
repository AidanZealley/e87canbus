import type { DevicesState } from "@/api/live-events"
import { cn } from "@/lib/utils"

type Device = DevicesState["devices"][number]

export const DeviceStatusFooter = ({
  devices,
  className,
}: {
  devices: readonly Device[]
  className?: string
}) => (
  <footer
    className={cn(
      "flex min-w-0 flex-wrap items-center gap-x-4 gap-y-1 border-t px-2 py-1 text-xs",
      className
    )}
    aria-label="Device status"
  >
    {devices.length === 0 ? (
      <div className="flex min-w-0 items-center gap-1.5">
        <span
          className="size-2 shrink-0 rounded-full bg-muted-foreground"
          aria-hidden="true"
        />
        <span className="truncate font-medium">Button pad</span>
        <span className="text-muted-foreground">Unavailable</span>
      </div>
    ) : (
      devices.map((device) => (
        <div key={device.id} className="flex min-w-0 items-center gap-1.5">
          <span
            className={cn(
              "size-2 shrink-0 rounded-full",
              device.last_output_fault
                ? "bg-destructive"
                : device.connected === true
                  ? "bg-emerald-500"
                  : "bg-muted-foreground"
            )}
            aria-hidden="true"
          />
          <span className="truncate font-medium">{device.label}</span>
          <span className="text-muted-foreground capitalize">
            {device.source_mode}
          </span>
          <span className="max-w-48 truncate text-muted-foreground">
            — {deviceConnectionLabel(device)}
          </span>
          {device.last_output_fault ? (
            <span className="max-w-48 truncate text-destructive">
              — {device.last_output_fault}
            </span>
          ) : null}
        </div>
      ))
    )}
  </footer>
)

const deviceConnectionLabel = (device: Device) => {
  if (device.connected === true) return "connected"
  if (device.connected === false) return "disconnected"
  return "connection unknown"
}
