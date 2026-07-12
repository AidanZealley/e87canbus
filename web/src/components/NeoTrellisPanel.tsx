import { MousePointerClick } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

type Props = {
  pressed: Set<number>
  onPress: (index: number) => void
  onRelease: (index: number) => void
  onToggle: (index: number) => void
}

export function NeoTrellisPanel({ pressed, onPress, onRelease, onToggle }: Props) {
  return (
    <Card className="min-w-0">
      <CardHeader>
        <CardTitle>NeoTrellis Buttons</CardTitle>
        <MousePointerClick className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-4 gap-2">
          {Array.from({ length: 16 }, (_, index) => {
            const isPressed = pressed.has(index)
            return (
              <div key={index} className="grid gap-1">
                <Button
                  variant={isPressed ? "default" : "outline"}
                  className="aspect-square h-auto min-h-12 flex-col gap-1 p-1"
                  onPointerDown={() => onPress(index)}
                  onPointerUp={() => onRelease(index)}
                  onPointerLeave={() => {
                    if (isPressed) onRelease(index)
                  }}
                >
                  <span className="text-base font-semibold">{index}</span>
                  <span className="text-[10px] uppercase text-current opacity-70">
                    {isPressed ? "pressed" : "idle"}
                  </span>
                </Button>
                <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => onToggle(index)}>
                  Toggle
                </Button>
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}
