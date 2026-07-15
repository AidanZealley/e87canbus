import {
  NeoTrellisPanel,
  type NeoTrellisButtonState,
} from "./components/neo-trellis-panel/NeoTrellisPanel"
import { useMutation } from "@tanstack/react-query"
import { tapButton } from "@/api/simulator"
import { useLiveStore } from "@/live/live-store"
import { LED_COUNT, notifySimulatorError } from "./utils"

const unavailableLedColours = Array<number>(LED_COUNT).fill(0)

type SimulatorNeoTrellisProps = {
  maximumAssistanceActive: boolean
  semanticCommandPending: boolean
  onMaximumAssistanceChange: (enabled: boolean) => void
}

export const SimulatorNeoTrellis = ({
  maximumAssistanceActive,
  semanticCommandPending,
  onMaximumAssistanceChange,
}: SimulatorNeoTrellisProps) => {
  const tap = useMutation({
    mutationFn: (index: number) => tapButton(index),
    onError: notifySimulatorError,
  })
  const desiredLedColours = useLiveStore((state) => state.buttons.led_colours)
  const device = useLiveStore(
    (state) =>
      state.devices.devices.find(
        (candidate) => candidate.id === "button_pad"
      ) ?? null
  )
  const synchronized = useLiveStore((state) => state.connection.synchronized)
  const sourceMode = synchronized
    ? (device?.source_mode ?? "disabled")
    : "unavailable"
  const emulatorControlsAvailable = sourceMode === "emulated"
  const observedLedColours = device?.observed_led_colours ?? null
  const displayedColours = synchronized
    ? (observedLedColours ?? desiredLedColours)
    : unavailableLedColours
  const observationLabel =
    observedLedColours === null
      ? "Observed LEDs unknown; showing controller desired LEDs."
      : "Showing LEDs decoded by the emulator from the output frame."
  const buttons: NeoTrellisButtonState[] = Array.from(
    { length: LED_COUNT },
    (_, index) => ({
      index,
      rgb: rgbForColourCode(displayedColours[index]),
    })
  )

  return (
    <NeoTrellisPanel
      buttons={buttons}
      sourceMode={sourceMode}
      observationLabel={observationLabel}
      emulatorControlsAvailable={emulatorControlsAvailable}
      controllerControlsAvailable={synchronized}
      maximumAssistanceActive={maximumAssistanceActive}
      semanticCommandPending={semanticCommandPending}
      onMaximumAssistanceChange={onMaximumAssistanceChange}
      onClick={(index) => tap.mutate(index)}
    />
  )
}

const rgbForColourCode = (colourCode: number): NeoTrellisButtonState["rgb"] => {
  switch (colourCode) {
    case 1:
      return [255, 0, 0]
    case 2:
      return [0, 255, 0]
    case 3:
      return [0, 0, 255]
    case 4:
      return [255, 191, 0]
    case 5:
      return [255, 255, 255]
    default:
      return [0, 0, 0]
  }
}
