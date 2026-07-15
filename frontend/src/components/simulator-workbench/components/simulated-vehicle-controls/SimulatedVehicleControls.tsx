import { useState, type FormEvent } from "react"
import { useMutation } from "@tanstack/react-query"
import { CarFrontIcon } from "lucide-react"
import type { EngineState } from "@/api/live-events"

import {
  setCoolantTemperature,
  setEngineRpm,
  setOilTemperature,
  setVehicleSpeed,
  silenceCoolantTemperature,
  silenceEngineRpm,
  silenceOilTemperature,
  silenceVehicleSpeed,
} from "@/api/simulator"

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
import { Slider } from "@/components/ui/slider"
import { deviceOrUnavailable, type PresentedDevice } from "../../utils"
import { DeviceStatusControl } from "./DeviceStatusControl"
import { TelemetrySignalControl } from "./TelemetrySignalControl"

const MIN_SPEED_KPH = 0
const MAX_SPEED_KPH = 300

type SimulatedVehicleControlsProps = {
  speedKph: number | null
  engine: EngineState
  devices: PresentedDevice[]
}

export const SimulatedVehicleControls = ({
  speedKph,
  engine,
  devices,
}: SimulatedVehicleControlsProps) => {
  const [draftSpeed, setDraftSpeed] = useState<number | "">(speedKph ?? 0)
  const speedMutation = useMutation({
    mutationFn: (value: number | null) =>
      value === null ? silenceVehicleSpeed() : setVehicleSpeed(value),
  })
  const rpmMutation = useMutation({
    mutationFn: (value: number | null) =>
      value === null ? silenceEngineRpm() : setEngineRpm(value),
  })
  const oilMutation = useMutation({
    mutationFn: (value: number | null) =>
      value === null ? silenceOilTemperature() : setOilTemperature(value),
  })
  const coolantMutation = useMutation({
    mutationFn: (value: number | null) =>
      value === null
        ? silenceCoolantTemperature()
        : setCoolantTemperature(value),
  })

  const setBoundedDraft = (value: number) => {
    if (Number.isFinite(value)) {
      setDraftSpeed(Math.min(MAX_SPEED_KPH, Math.max(MIN_SPEED_KPH, value)))
    }
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (draftSpeed !== "") {
      speedMutation.mutate(draftSpeed)
    }
  }

  return (
    <Card className="min-w-0">
      <CardHeader>
        <CardTitle>Simulated vehicle</CardTitle>
        <CardDescription>
          External vehicle inputs on simulated CAN
        </CardDescription>
        <CardAction>
          <CarFrontIcon aria-hidden="true" />
        </CardAction>
      </CardHeader>

      <CardContent>
        <div className="grid gap-4">
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
                    disabled={speedMutation.isPending}
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
              <Button
                type="submit"
                disabled={speedMutation.isPending || draftSpeed === ""}
              >
                Set speed
              </Button>
            </div>

            <Slider
              min={MIN_SPEED_KPH}
              max={MAX_SPEED_KPH}
              step={1}
              value={[draftSpeed === "" ? MIN_SPEED_KPH : draftSpeed]}
              disabled={speedMutation.isPending}
              aria-label="Simulated vehicle speed"
              onValueChange={(value) =>
                setBoundedDraft(Array.isArray(value) ? value[0] : value)
              }
            />

            <div className="flex items-center justify-between gap-3">
              <span
                className="text-xs text-muted-foreground"
                aria-live="polite"
              >
                {speedKph === null
                  ? "No fresh speed signal"
                  : `Sending ${speedKph.toFixed(1)} km/h`}
              </span>
              <Button
                type="button"
                variant="outline"
                disabled={speedMutation.isPending || speedKph === null}
                onClick={() => speedMutation.mutate(null)}
              >
                Stop signal
              </Button>
            </div>
          </form>

          <TelemetrySignalControl
            id="simulated-rpm"
            label="Engine RPM"
            unit="rpm"
            minimum={0}
            maximum={9000}
            step={100}
            initialDraft={3000}
            telemetry={engine.rpm}
            disabled={rpmMutation.isPending}
            onSet={(value) => rpmMutation.mutate(value)}
            onSilence={() => rpmMutation.mutate(null)}
          />
          <TelemetrySignalControl
            id="simulated-oil-temperature"
            label="Oil temperature"
            unit="°C"
            minimum={-40}
            maximum={200}
            step={1}
            initialDraft={90}
            telemetry={engine.oil_temperature_c}
            disabled={oilMutation.isPending}
            onSet={(value) => oilMutation.mutate(value)}
            onSilence={() => oilMutation.mutate(null)}
          />
          <TelemetrySignalControl
            id="simulated-coolant-temperature"
            label="Coolant temperature"
            unit="°C"
            minimum={-40}
            maximum={200}
            step={1}
            initialDraft={90}
            telemetry={engine.coolant_temperature_c}
            disabled={coolantMutation.isPending}
            onSet={(value) => coolantMutation.mutate(value)}
            onSilence={() => coolantMutation.mutate(null)}
          />

          <div className="grid gap-3 border-t pt-4 sm:grid-cols-2">
            <DeviceStatusControl
              device={deviceOrUnavailable(devices, "button_pad", "Button pad")}
            />
            <DeviceStatusControl
              device={deviceOrUnavailable(
                devices,
                "steering_controller",
                "Steering controller"
              )}
            />
          </div>
        </div>
      </CardContent>

      <CardFooter>
        <p className="text-xs text-muted-foreground">
          Speed uses simulated F-CAN. Engine signals use simulation-only PT-CAN
          frames; none are BMW definitions. Device status is presentation-only
          and does not change simulated behavior.
        </p>
      </CardFooter>
    </Card>
  )
}
