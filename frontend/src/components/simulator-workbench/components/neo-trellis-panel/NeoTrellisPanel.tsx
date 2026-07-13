import { MousePointerClickIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

export type NeoTrellisButton = {
  index: number
  pressed: boolean
  rgb: readonly [red: number, green: number, blue: number]
}

type NeoTrellisPanelProps = {
  buttons: NeoTrellisButton[]
  onPress: (index: number) => void
  onRelease: (index: number) => void
}

export const NeoTrellisPanel = ({
  buttons,
  onPress,
  onRelease,
}: NeoTrellisPanelProps) => (
  <Card className="min-w-0">
    <CardHeader>
      <CardTitle>NeoTrellis</CardTitle>
      <CardDescription>Combined RGB button matrix</CardDescription>
      <CardAction>
        <MousePointerClickIcon aria-hidden="true" />
      </CardAction>
    </CardHeader>

    <CardContent>
      <div className="grid grid-cols-4 gap-2">
        {buttons.map(({ index, pressed, rgb }) => (
          <div key={index} className="flex min-w-0 flex-col gap-1">
            <Button
              variant="outline"
              className="aspect-square h-auto min-h-14 rounded-4xl p-1"
              style={{
                boxShadow: buttonGlow(rgb, pressed),
              }}
              aria-label={`Button ${index}, ${pressed ? "pressed" : "idle"}`}
              aria-pressed={pressed}
              onPointerDown={() => onPress(index)}
              onPointerUp={() => onRelease(index)}
              onPointerCancel={() => {
                if (pressed) onRelease(index)
              }}
              onPointerLeave={() => {
                if (pressed) onRelease(index)
              }}
            >
              <span className="font-heading text-2xl">{index}</span>
            </Button>
          </div>
        ))}
      </div>
    </CardContent>

    <CardFooter>
      <p className="text-xs text-muted-foreground">
        Steering: 0 mode, 1 down, 2 up, 3 maximum override.
      </p>
    </CardFooter>
  </Card>
)

const buttonGlow = (
  rgb: NeoTrellisButton["rgb"],
  pressed: boolean
) => {
  const colour = pressed ? "255 255 255" : rgb.join(" ")

  return `inset 0 0 0 4px rgb(${colour}), 0 0 10px rgb(${colour} / 25%)`
}
