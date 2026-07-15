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
  onClick: (index: number) => void
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
  onClick,
}: NeoTrellisPanelProps) => (
  <Card className="min-w-0">
    <CardHeader>
      <CardTitle>Button pad</CardTitle>
      <CardDescription>
        Controller output and device wire-path exercise
      </CardDescription>
      <CardAction>
        <MousePointerClickIcon aria-hidden="true" />
      </CardAction>
    </CardHeader>

    <CardContent className="grid gap-4">
      <section
        className="grid gap-2 rounded-md border p-3"
        aria-label="Controller operation"
      >
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
            <div className="text-xs text-muted-foreground">
              {observationLabel}
            </div>
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
          {buttons.map(({ index, rgb }) => (
            <div key={index} className="flex min-w-0 flex-col gap-1">
              <Button
                variant="outline"
                className="aspect-square h-auto min-h-14 rounded-4xl p-1 active:scale-[0.98] active:bg-input/40"
                style={{
                  boxShadow: buttonGlow(rgb),
                }}
                aria-label={`Button ${index}`}
                disabled={!emulatorControlsAvailable}
                onClick={() => onClick(index)}
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

const buttonGlow = (rgb: NeoTrellisButton["rgb"]) => {
  const colour = rgb.join(" ")

  return `inset 0 0 0 4px rgb(${colour}), 0 0 10px rgb(${colour} / 25%)`
}
