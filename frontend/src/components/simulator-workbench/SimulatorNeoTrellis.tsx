import {
  NeoTrellisPanel,
  type NeoTrellisButton,
} from "./components/neo-trellis-panel"
import { useLiveStore } from "@/live/live-store"
import { LED_COUNT } from "./utils"

const unavailableLedColours = Array<number>(LED_COUNT).fill(0)

type SimulatorNeoTrellisProps = {
  pressedButtons: Set<number>
  onPress: (index: number) => void
  onRelease: (index: number) => void
}

export const SimulatorNeoTrellis = ({
  pressedButtons,
  onPress,
  onRelease,
}: SimulatorNeoTrellisProps) => {
  const ledColours = useLiveStore((state) => state.buttons.led_colours)
  const synchronized = useLiveStore((state) => state.connection.synchronized)
  const displayedColours = synchronized ? ledColours : unavailableLedColours
  const buttons: NeoTrellisButton[] = Array.from(
    { length: LED_COUNT },
    (_, index) => ({
      index,
      pressed: pressedButtons.has(index),
      rgb: rgbForColourCode(displayedColours[index]),
    })
  )

  return (
    <NeoTrellisPanel
      buttons={buttons}
      onPress={onPress}
      onRelease={onRelease}
    />
  )
}

const rgbForColourCode = (colourCode: number): NeoTrellisButton["rgb"] => {
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
