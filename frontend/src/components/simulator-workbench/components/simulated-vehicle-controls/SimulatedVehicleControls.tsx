import { useState, type FormEvent } from "react"
import { CarFrontIcon } from "lucide-react"

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
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

const MIN_SPEED_KPH = 0
const MAX_SPEED_KPH = 300

type SimulatedVehicleControlsProps = {
  speedKph: number | null
  disabled?: boolean
  onSetSpeed: (speedKph: number) => void
  onSilenceSpeed: () => void
}

export const SimulatedVehicleControls = ({
  speedKph,
  disabled = false,
  onSetSpeed,
  onSilenceSpeed,
}: SimulatedVehicleControlsProps) => {
  const [draftSpeed, setDraftSpeed] = useState<number | "">(speedKph ?? 0)

  const setBoundedDraft = (value: number) => {
    if (Number.isFinite(value)) {
      setDraftSpeed(Math.min(MAX_SPEED_KPH, Math.max(MIN_SPEED_KPH, value)))
    }
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (draftSpeed !== "") {
      onSetSpeed(draftSpeed)
    }
  }

  return (
    <Card className="min-w-0">
      <CardHeader>
        <CardTitle>Simulated vehicle</CardTitle>
        <CardDescription>External vehicle inputs on simulated CAN</CardDescription>
        <CardAction>
          <CarFrontIcon aria-hidden="true" />
        </CardAction>
      </CardHeader>

      <CardContent>
        <form className="grid gap-4" onSubmit={handleSubmit}>
          <div className="flex items-end gap-2">
            <div className="grid min-w-0 flex-1 gap-1.5">
              <Label htmlFor="simulated-speed">Vehicle speed</Label>
              <div className="relative">
                <Input
                  id="simulated-speed"
                  type="number"
                  min={MIN_SPEED_KPH}
                  max={MAX_SPEED_KPH}
                  step={0.1}
                  value={draftSpeed}
                  disabled={disabled}
                  className="pr-14"
                  onChange={(event) => {
                    if (event.target.value === "") {
                      setDraftSpeed("")
                    } else {
                      setBoundedDraft(event.target.valueAsNumber)
                    }
                  }}
                />
                <span className="pointer-events-none absolute inset-y-0 right-2 flex items-center text-xs text-muted-foreground">
                  km/h
                </span>
              </div>
            </div>
            <Button type="submit" disabled={disabled || draftSpeed === ""}>
              Set speed
            </Button>
          </div>

          <input
            type="range"
            min={MIN_SPEED_KPH}
            max={MAX_SPEED_KPH}
            step={1}
            value={draftSpeed === "" ? MIN_SPEED_KPH : draftSpeed}
            disabled={disabled}
            aria-label="Simulated vehicle speed"
            className="w-full accent-primary disabled:opacity-50"
            onChange={(event) => setBoundedDraft(event.target.valueAsNumber)}
          />

          <div className="flex items-center justify-between gap-3">
            <span className="text-xs text-muted-foreground" aria-live="polite">
              {speedKph === null
                ? "No fresh speed signal"
                : `Sending ${speedKph.toFixed(1)} km/h`}
            </span>
            <Button
              type="button"
              variant="outline"
              disabled={disabled || speedKph === null}
              onClick={onSilenceSpeed}
            >
              Stop signal
            </Button>
          </div>
        </form>
      </CardContent>

      <CardFooter>
        <p className="text-xs text-muted-foreground">
          Speed is encoded by the virtual car and received on F-CAN.
        </p>
      </CardFooter>
    </Card>
  )
}
