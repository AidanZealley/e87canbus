import type { DeviceRegistryEntry } from "@/api/live-events"
import { cn } from "@/lib/utils"

export const DeviceStatusFooter = ({
  entries,
  className,
}: {
  entries: readonly DeviceRegistryEntry[]
  className?: string
}) => {
  const observed = entries.filter(
    (entry) => entry.status !== "disabled" && entry.status !== "not_found"
  )
  return (
    <footer
      className={cn(
        "flex min-w-0 flex-wrap items-center gap-x-4 gap-y-1 border-t px-2 py-1 text-xs",
        className
      )}
      aria-label="Device status"
    >
      {observed.map((device) => (
        <div key={device.role} className="flex min-w-0 items-center gap-1.5">
          <span
            className={cn(
              "size-2 shrink-0 rounded-full",
              device.status === "active"
                ? "bg-emerald-500"
                : device.status === "fault" || device.status === "incompatible"
                  ? "bg-destructive"
                  : "bg-amber-500"
            )}
            aria-hidden="true"
          />
          <span className="truncate font-medium">{device.label}</span>
          <span className="text-muted-foreground capitalize">
            {device.source_mode}
          </span>
          <span className="max-w-48 truncate text-muted-foreground">
            — {deviceStatusLabel(device)}
          </span>
          {device.status === "fault" && device.last_status_code !== null ? (
            <span className="max-w-48 truncate text-destructive">
              — status code {device.last_status_code}
            </span>
          ) : null}
        </div>
      ))}
    </footer>
  )
}

const deviceStatusLabel = (device: DeviceRegistryEntry) => {
  switch (device.status) {
    case "pending":
      return "pending — waiting for heartbeat"
    case "active":
      return "active"
    case "stale":
      return "stale — contact lost"
    case "incompatible":
      return "incompatible — unsupported protocol"
    case "fault":
      return "fault"
    case "disabled":
    case "not_found":
      return device.status
  }
}
