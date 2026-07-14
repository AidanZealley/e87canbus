import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { DeviceId, DeviceSnapshot, DeviceStatus } from "../../types"

const STATUS_ITEMS: { label: string; value: DeviceStatus }[] = [
  { label: "Online", value: "online" },
  { label: "Degraded", value: "degraded" },
  { label: "Offline", value: "offline" },
]

type DeviceStatusControlProps = {
  device: DeviceSnapshot
  disabled: boolean
  onStatusChange: (deviceId: DeviceId, status: DeviceStatus) => void
}

export const DeviceStatusControl = ({
  device,
  disabled,
  onStatusChange,
}: DeviceStatusControlProps) => {
  const controlId = `simulated-device-${device.id}`

  return (
    <div className="grid min-w-0 gap-1.5">
      <Label htmlFor={controlId}>{device.label}</Label>
      <Select
        value={device.status}
        items={STATUS_ITEMS}
        disabled={disabled}
        onValueChange={(status) => {
          if (status !== null && status !== device.status) {
            onStatusChange(device.id, status)
          }
        }}
      >
        <SelectTrigger id={controlId} className="w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {STATUS_ITEMS.map((item) => (
            <SelectItem key={item.value} value={item.value}>
              {item.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <span className="truncate text-xs text-muted-foreground">
        {device.reason === null
          ? "Simulation input only"
          : device.reason.replaceAll("_", " ")}
      </span>
    </div>
  )
}
