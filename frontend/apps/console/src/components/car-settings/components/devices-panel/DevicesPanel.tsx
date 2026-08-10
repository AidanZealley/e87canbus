import { useLiveStore } from "@e87canbus/coordinator-client/live/live-store"
import { DeviceStatusTile } from "../device-status-tile"
import { SettingsGroup } from "../settings-group"

export const DevicesPanel = () => {
  const registry = useLiveStore((state) => state.devices.registry)
  const synchronized = useLiveStore((state) => state.connection.synchronized)
  const devices = [registry.button_pad, registry.servotronic_controller]

  return (
    <SettingsGroup
      title="Devices"
      description={
        synchronized
          ? "Observed state of every device the coordinator tracks."
          : "Live connection unavailable — this is the last state observed."
      }
      className="sm:col-span-2"
    >
      <div
        className="grid gap-3 sm:grid-cols-2"
        role="group"
        aria-label="Device status"
      >
        {devices.map((device) => (
          <DeviceStatusTile key={device.role} device={device} />
        ))}
      </div>
    </SettingsGroup>
  )
}
