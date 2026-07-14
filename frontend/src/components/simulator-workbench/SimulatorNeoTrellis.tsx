import {
  NeoTrellisPanel,
  type NeoTrellisButton,
} from "./components/neo-trellis-panel"
import { useLedColours } from "./query"

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
  const ledColours = useLedColours()
  const buttons: NeoTrellisButton[] = Array.from(
    { length: 16 },
    (_, index) => ({
      index,
      pressed: pressedButtons.has(index),
      rgb: rgbForColourCode(ledColours[index] ?? 0),
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
