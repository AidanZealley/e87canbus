import { useMutation } from "@tanstack/react-query"

import { useLiveStore } from "@/live/live-store"
import { notifySimulatorError } from "./utils"
import {
  SimulatedDeviceCard,
  runSimulatedDeviceAction,
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
      runSimulatedDeviceAction(entry.role, action),
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
        mutation.isPending ? (mutation.variables?.action ?? null) : null
      }
    >
      <SteeringStatus />
    </SimulatedDeviceCard>
  )
}
