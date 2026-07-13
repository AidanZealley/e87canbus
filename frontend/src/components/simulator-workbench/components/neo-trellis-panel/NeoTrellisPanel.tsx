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

type NeoTrellisPanelProps = {
  pressed: Set<number>
  onPress: (index: number) => void
  onRelease: (index: number) => void
  onToggle: (index: number) => void
}

export const NeoTrellisPanel = ({
  pressed,
  onPress,
  onRelease,
  onToggle,
}: NeoTrellisPanelProps) => (
  <Card className="min-w-0">
    <CardHeader>
      <CardTitle>NeoTrellis buttons</CardTitle>
      <CardDescription>Press, hold, release, or latch a key</CardDescription>
      <CardAction>
        <MousePointerClickIcon aria-hidden="true" />
      </CardAction>
    </CardHeader>

    <CardContent>
      <div className="grid grid-cols-4 gap-2">
        {Array.from({ length: 16 }, (_, index) => {
          const isPressed = pressed.has(index)

          return (
            <div key={index} className="flex min-w-0 flex-col gap-1">
              <Button
                variant={isPressed ? "default" : "outline"}
                className="aspect-square h-auto min-h-14 flex-col gap-0.5 p-1"
                aria-label={`Button ${index}, ${isPressed ? "pressed" : "idle"}`}
                aria-pressed={isPressed}
                onPointerDown={() => onPress(index)}
                onPointerUp={() => onRelease(index)}
                onPointerCancel={() => {
                  if (isPressed) onRelease(index)
                }}
                onPointerLeave={() => {
                  if (isPressed) onRelease(index)
                }}
              >
                <span className="font-heading text-base font-semibold">
                  {index}
                </span>
                <span className="text-[0.625rem] uppercase opacity-70">
                  {isPressed ? "pressed" : "idle"}
                </span>
              </Button>
              <Button variant="ghost" size="xs" onClick={() => onToggle(index)}>
                Toggle
              </Button>
            </div>
          )
        })}
      </div>
    </CardContent>

    <CardFooter>
      <p className="text-xs text-muted-foreground">
        Button 0 toggles steering mode in the current milestone.
      </p>
    </CardFooter>
  </Card>
)
