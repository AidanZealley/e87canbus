import { MousePointerClickIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
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
  sourceMode: "physical" | "emulated" | "observer" | "disabled" | "unavailable"
  observationLabel: string
  emulatorControlsAvailable: boolean
  controllerControlsAvailable: boolean
  maximumAssistanceActive: boolean
  semanticCommandPending: boolean
  onMaximumAssistanceChange: (enabled: boolean) => void
  onPress: (index: number) => void
  onRelease: (index: number) => void
}

export const NeoTrellisPanel = ({
  buttons,
  sourceMode,
  observationLabel,
  emulatorControlsAvailable,
  controllerControlsAvailable,
  maximumAssistanceActive,
  semanticCommandPending,
  onMaximumAssistanceChange,
  onPress,
  onRelease,
}: NeoTrellisPanelProps) => (
  <Card className="min-w-0">
    <CardHeader>
      <CardTitle>Button pad</CardTitle>
      <CardDescription>Controller output and device wire-path exercise</CardDescription>
      <CardAction>
        <MousePointerClickIcon aria-hidden="true" />
      </CardAction>
    </CardHeader>

    <CardContent className="grid gap-4">
      <section className="grid gap-2 rounded-md border p-3" aria-label="Controller operation">
        <div className="flex items-center justify-between gap-2">
          <div>
            <div className="text-sm font-medium">Operate controller</div>
            <div className="text-xs text-muted-foreground">
              Semantic HTTP command; no button frame is fabricated.
            </div>
          </div>
          <Button
            type="button"
            variant={maximumAssistanceActive ? "destructive" : "outline"}
            disabled={!controllerControlsAvailable || semanticCommandPending}
            onClick={() => onMaximumAssistanceChange(!maximumAssistanceActive)}
          >
            {maximumAssistanceActive ? "Disable maximum" : "Enable maximum"}
          </Button>
        </div>
      </section>

      <section className="grid gap-3" aria-label="Button-pad emulator exercise">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div className="text-sm font-medium">Exercise emulator</div>
            <div className="text-xs text-muted-foreground">{observationLabel}</div>
          </div>
          <Badge variant={emulatorControlsAvailable ? "default" : "secondary"}>
            Source: {sourceMode}
          </Badge>
        </div>
        {!emulatorControlsAvailable ? (
          <p className="text-xs text-muted-foreground">
            Wire-level button controls are available only for the emulated role.
          </p>
        ) : null}
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
                disabled={!emulatorControlsAvailable}
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
      </section>
    </CardContent>

    <CardFooter>
      <p className="text-xs text-muted-foreground">
        Emulator buttons encode the generated 0x700 protocol. LED observation
        decodes complete 0x701 snapshots atomically.
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
