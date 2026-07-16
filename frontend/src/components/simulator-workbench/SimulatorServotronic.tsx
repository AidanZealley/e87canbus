import { useMutation } from "@tanstack/react-query"

import {
  connectSimulatedDevice,
  disconnectSimulatedDevice,
  rebootSimulatedDevice,
  setSimulatedDeviceProtocolVersion,
  setSimulatedDeviceStatusCode,
} from "@/api/simulator"
import type { DeviceRegistryEntry } from "@/api/live-events"
import { useLiveStore } from "@/live/live-store"
import { notifySimulatorError } from "./utils"
import {
  SimulatedDeviceCard,
  simulatedDeviceActions,
  type SimulatedDeviceAction,
} from "./components/simulated-device-card"
import { SteeringStatus } from "./components/steering-status/SteeringStatus"

export const SimulatorServotronic = () => {
  const entry = useLiveStore(
    (state) => state.devices.registry.servotronic_controller
  )
  const synchronized = useLiveStore((state) => state.connection.synchronized)
  const mutation = useMutation({
    mutationFn: ({ action }: { action: SimulatedDeviceAction }) =>
      runDeviceAction(entry.role, action),
    onError: notifySimulatorError,
  })
  const actions = simulatedDeviceActions(entry, synchronized)

  return (
    <SimulatedDeviceCard
      role={entry.role}
      registryEntry={entry}
      availableActions={actions}
      callbacks={Object.fromEntries(
        (Object.keys(actions) as SimulatedDeviceAction[]).map((action) => [
          action,
          () => mutation.mutate({ action }),
        ])
      )}
      pendingAction={
        mutation.isPending ? mutation.variables?.action ?? null : null
      }
      errorMessage={mutation.error instanceof Error ? mutation.error.message : null}
    >
      <SteeringStatus />
    </SimulatedDeviceCard>
  )
}

const runDeviceAction = (
  role: DeviceRegistryEntry["role"],
  action: SimulatedDeviceAction
) => {
  switch (action) {
    case "connect":
      return connectSimulatedDevice(role)
    case "disconnect":
      return disconnectSimulatedDevice(role)
    case "reboot":
      return rebootSimulatedDevice(role)
    case "incompatible":
      return setSimulatedDeviceProtocolVersion(role, 2)
    case "restore-compatible":
      return setSimulatedDeviceProtocolVersion(role, 1)
    case "fault":
      return setSimulatedDeviceStatusCode(role, 1)
    case "clear-fault":
      return setSimulatedDeviceStatusCode(role, 0)
  }
}
