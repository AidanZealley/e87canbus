import { useMutation } from "@tanstack/react-query"
import { useShallow } from "zustand/react/shallow"

import { tapButton } from "@/api/simulator"
import { useLiveStore } from "@/live/live-store"
import {
  NeoTrellisPanel,
  type NeoTrellisButtonState,
} from "./components/neo-trellis-panel/NeoTrellisPanel"
import { LED_COUNT, notifySimulatorError } from "./utils"

const unavailableLedColours = Array<number>(LED_COUNT).fill(0)

export const SimulatorNeoTrellis = () => {
  const { mutate: tapButtonMutation } = useMutation({
    mutationFn: (index: number) => tapButton(index),
    onError: notifySimulatorError,
  })
  const desiredLedColours = useLiveStore(
    useShallow((state) => state.buttons.led_colours)
  )
  const sourceMode = useLiveStore(
    useShallow((state) => {
      return state.devices.registry.button_pad.source_mode
    })
  )
  const buttonPadStatus = useLiveStore(
    (state) => state.devices.registry.button_pad.status
  )
  const synchronized = useLiveStore((state) => state.connection.synchronized)
  const displayedSourceMode = synchronized ? sourceMode : "unavailable"
  const emulatorControlsAvailable =
    displayedSourceMode === "emulated" && buttonPadStatus === "active"
  const displayedColours = synchronized ? desiredLedColours : unavailableLedColours
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
      emulatorControlsAvailable={emulatorControlsAvailable}
      onClick={tapButtonMutation}
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
