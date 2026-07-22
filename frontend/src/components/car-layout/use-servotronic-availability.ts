import { useLiveStore } from "@/live/live-store"
import {
  deriveServotronicAvailability,
  type ServotronicAvailability,
} from "./car-ui"

export const useServotronicAvailability = (): ServotronicAvailability => {
  const synchronized = useLiveStore((state) => state.connection.synchronized)
  const steering = useLiveStore((state) => state.steering)
  const status = useLiveStore(
    (state) => state.devices.registry.servotronic_controller.status
  )
  const steeringFault = useLiveStore((state) => state.health.steering.fault)
  const adapterFault = useLiveStore(
    (state) =>
      state.health.devices.find(
        (device) => device.role === "servotronic_controller"
      )?.fault ?? null
  )
  return deriveServotronicAvailability({
    synchronized,
    status,
    steering,
    steeringFault,
    adapterFault,
  })
}
