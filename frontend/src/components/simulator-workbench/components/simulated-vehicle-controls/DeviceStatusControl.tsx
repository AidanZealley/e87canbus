import { useMutation } from "@tanstack/react-query"
import type { DevicesState } from "@/api/live-events"

import { setDeviceStatus } from "@/api/simulator"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { PresentedDevice } from "../../utils"

type DeviceStatus = DevicesState["devices"][number]["status"]

const STATUS_ITEMS: { label: string; value: DeviceStatus }[] = [
  { label: "Online", value: "online" },
  { label: "Degraded", value: "degraded" },
  { label: "Offline", value: "offline" },
]

type DeviceStatusControlProps = {
  device: PresentedDevice
}

export const DeviceStatusControl = ({ device }: DeviceStatusControlProps) => {
  const controlId = `simulated-device-${device.id}`
  const mutation = useMutation({
    mutationFn: (status: DeviceStatus) => setDeviceStatus(device.id, status),
  })

  return (
    <div className="grid min-w-0 gap-1.5">
      <Label htmlFor={controlId}>{device.label}</Label>
      <Select
        value={device.status}
        items={STATUS_ITEMS}
        disabled={mutation.isPending}
        onValueChange={(status) => {
          if (status !== null && status !== device.status) {
            mutation.mutate(status)
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
