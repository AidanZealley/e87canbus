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
import { Slider } from "@/components/ui/slider"
import type {
  DeviceId,
  DeviceSnapshot,
  DeviceStatus,
  EngineTelemetrySnapshot,
} from "../../types"
import { deviceOrUnavailable } from "../../utils"
import { DeviceStatusControl } from "./DeviceStatusControl"
import { TelemetrySignalControl } from "./TelemetrySignalControl"

const MIN_SPEED_KPH = 0
const MAX_SPEED_KPH = 300

type SimulatedVehicleControlsProps = {
  speedKph: number | null
  engine: EngineTelemetrySnapshot
  devices: DeviceSnapshot[]
  disabled?: boolean
  onSetSpeed: (speedKph: number) => void
  onSilenceSpeed: () => void
  onSetRpm: (rpm: number) => void
  onSilenceRpm: () => void
  onSetOilTemperature: (temperatureC: number) => void
  onSilenceOilTemperature: () => void
  onSetCoolantTemperature: (temperatureC: number) => void
  onSilenceCoolantTemperature: () => void
  onSetDeviceStatus: (deviceId: DeviceId, status: DeviceStatus) => void
}

export const SimulatedVehicleControls = ({
  speedKph,
  engine,
  devices,
  disabled = false,
  onSetSpeed,
  onSilenceSpeed,
  onSetRpm,
  onSilenceRpm,
  onSetOilTemperature,
  onSilenceOilTemperature,
  onSetCoolantTemperature,
  onSilenceCoolantTemperature,
  onSetDeviceStatus,
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

            <Slider
              min={MIN_SPEED_KPH}
              max={MAX_SPEED_KPH}
              step={1}
              value={[draftSpeed === "" ? MIN_SPEED_KPH : draftSpeed]}
              disabled={disabled}
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
                disabled={disabled || speedKph === null}
                onClick={onSilenceSpeed}
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
            disabled={disabled}
            onSet={onSetRpm}
            onSilence={onSilenceRpm}
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
            disabled={disabled}
            onSet={onSetOilTemperature}
            onSilence={onSilenceOilTemperature}
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
            disabled={disabled}
            onSet={onSetCoolantTemperature}
            onSilence={onSilenceCoolantTemperature}
          />

          <div className="grid gap-3 border-t pt-4 sm:grid-cols-2">
            <DeviceStatusControl
              device={deviceOrUnavailable(devices, "button_pad", "Button pad")}
              disabled={disabled}
              onStatusChange={onSetDeviceStatus}
            />
            <DeviceStatusControl
              device={deviceOrUnavailable(
                devices,
                "steering_controller",
                "Steering controller"
              )}
              disabled={disabled}
              onStatusChange={onSetDeviceStatus}
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
