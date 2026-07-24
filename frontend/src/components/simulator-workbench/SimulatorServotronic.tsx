import { useMutation } from "@tanstack/react-query"

import { useServotronicAvailability } from "@/components/car-layout/use-servotronic-availability"
import { SteeringCurveEditor } from "@/components/steering-curve-editor"
import { useLiveStore } from "@/live/live-store"
import { notifySimulatorError } from "./utils"
import {
  SimulatedDeviceCard,
  runSimulatedDeviceAction,
  simulatedDeviceActions,
  type SimulatedDeviceAction,
} from "./components/simulated-device-card"

export const SimulatorServotronic = () => {
  const entry = useLiveStore(
    (state) => state.devices.registry.servotronic_controller
  )
  const synchronized = useLiveStore((state) => state.connection.synchronized)
  const steering = useLiveStore((state) => state.steering)
  const vehicle = useLiveStore((state) => state.vehicle)
  const servotronic = useLiveStore((state) => state.steering?.servotronic)
  const availability = useServotronicAvailability()
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
      {synchronized && steering !== null ? (
        <SteeringCurveEditor
          activeCurve={steering.active_curve}
          activationAvailable={availability.activation}
          modeControlAvailable={availability.modeControl}
          mode={steering.mode}
          manualAssistanceLevel={steering.manual_assistance_level}
          manualAssistanceLevelCount={steering.manual_assistance_level_count}
          maximumAssistanceActive={steering.maximum_assistance_active}
          speedKph={vehicle.speed_valid ? vehicle.speed_kph : null}
          activeAssistance={
            !availability.telemetry
              ? null
              : steering.maximum_assistance_active
                ? 1
                : steering.mode === "manual" || vehicle.speed_valid
                  ? (servotronic?.effective_assistance ?? null)
                  : null
          }
        />
      ) : null}
    </SimulatedDeviceCard>
  )
}
