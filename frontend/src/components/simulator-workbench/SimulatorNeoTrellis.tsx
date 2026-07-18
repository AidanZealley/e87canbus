import { useMutation } from "@tanstack/react-query"
import { useShallow } from "zustand/react/shallow"

import { tapSimulationButtonMutation } from "@/api/http/@tanstack/react-query.gen"
import {
  runSimulatedDeviceAction,
  SimulatedDeviceCard,
  simulatedDeviceActions,
  type SimulatedDeviceAction,
} from "./components/simulated-device-card"
import { useLiveStore } from "@/live/live-store"
import {
  NeoTrellisPanel,
  type NeoTrellisButtonState,
} from "./components/neo-trellis-panel/NeoTrellisPanel"
import { LED_COUNT, notifySimulatorError } from "./utils"

const unavailableLedRgb = Array.from(
  { length: LED_COUNT },
  () => [0, 0, 0] as const
)

export const SimulatorNeoTrellis = () => {
  const { mutate: tapButtonMutation } = useMutation({
    ...tapSimulationButtonMutation(),
    onError: notifySimulatorError,
  })
  const deviceEntry = useLiveStore((state) => state.devices.registry.button_pad)
  const synchronized = useLiveStore((state) => state.connection.synchronized)
  const deviceMutation = useMutation({
    mutationFn: ({ action }: { action: SimulatedDeviceAction }) =>
      runSimulatedDeviceAction(deviceEntry.role, action),
    onError: notifySimulatorError,
  })
  const desiredLedRgb = useLiveStore(
    useShallow((state) => state.buttons.led_rgb)
  )
  const sourceMode = useLiveStore(
    (state) => state.devices.registry.button_pad.source_mode
  )
  const buttonPadStatus = useLiveStore(
    (state) => state.devices.registry.button_pad.status
  )
  const displayedSourceMode = synchronized ? sourceMode : "unavailable"
  const emulatorControlsAvailable =
    displayedSourceMode === "emulated" && buttonPadStatus === "active"
  const displayedRgb = synchronized ? desiredLedRgb : unavailableLedRgb
  const buttons: NeoTrellisButtonState[] = Array.from(
    { length: LED_COUNT },
    (_, index) => ({
      index,
      rgb: displayedRgb[index],
    })
  )
  const actions = simulatedDeviceActions(deviceEntry, synchronized)

  return (
    <SimulatedDeviceCard
      role={deviceEntry.role}
      registryEntry={deviceEntry}
      availableActions={actions}
      callbacks={Object.fromEntries(
        (Object.keys(actions) as SimulatedDeviceAction[]).map((action) => [
          action,
          () => deviceMutation.mutate({ action }),
        ])
      )}
      pendingAction={
        deviceMutation.isPending
          ? (deviceMutation.variables?.action ?? null)
          : null
      }
    >
      <NeoTrellisPanel
        buttons={buttons}
        emulatorControlsAvailable={emulatorControlsAvailable}
        onClick={(index) =>
          tapButtonMutation({ path: { button_index: index } })
        }
      />
    </SimulatedDeviceCard>
  )
}
