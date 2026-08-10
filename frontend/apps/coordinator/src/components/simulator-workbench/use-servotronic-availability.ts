import { useLiveStore } from "@e87canbus/coordinator-client/live/live-store"
import type {
  DeviceRegistryEntryState,
  RuntimeFaultState,
  SteeringState,
} from "@e87canbus/coordinator-client/api/live-contract.gen"

type ServotronicAvailability = {
  telemetry: boolean
  modeControl: boolean
  activation: boolean
  reason: string
}

const deriveServotronicAvailability = ({
  synchronized,
  status,
  steering,
  steeringFault,
  adapterFault,
}: {
  synchronized: boolean
  status: DeviceRegistryEntryState["status"]
  steering: SteeringState | null
  steeringFault: RuntimeFaultState | null
  adapterFault: RuntimeFaultState | null
}): ServotronicAvailability => {
  const unavailable = (reason: string): ServotronicAvailability => ({
    telemetry: false,
    modeControl: false,
    activation: false,
    reason,
  })
  if (!synchronized || steering === null) {
    return unavailable("live steering state unavailable")
  }
  if (steeringFault !== null || adapterFault !== null) {
    return unavailable("servotronic output adapter is faulted")
  }
  if (status !== "active") {
    return unavailable(`servotronic controller is ${status}`)
  }
  return {
    telemetry: steering.servotronic !== null,
    modeControl: true,
    activation: steering.curve_activation_available,
    reason: "",
  }
}

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
