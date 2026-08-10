import { useState } from "react"
import { useMutation } from "@tanstack/react-query"
import { PowerIcon } from "lucide-react"
import type { EngineState } from "@e87canbus/coordinator-client/api/live-contract.gen"

import {
  setCoolantTemperatureMutation,
  setEngineRpmMutation,
  setOilTemperatureMutation,
  setVehicleSweepMutation,
  setVehicleSpeedMutation,
} from "@e87canbus/coordinator-client/api/http/@tanstack/react-query.gen"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { TelemetrySlider } from "./TelemetrySlider"
import {
  COOLANT_MAXIMUM_TEMPERATURE_C,
  OIL_MAXIMUM_TEMPERATURE_C,
} from "../../engine-temperature-scale"
import { useEffectiveApplicationSettings } from "@e87canbus/coordinator-client/application-settings-query"
import { HighBeam } from "@/icons"
import {
  IDLE_RPM,
  setSimulatedVehicleRunning,
} from "../../simulated-vehicle-power"

const MIN_SPEED_KPH = 0
const MAX_SPEED_KPH = 300
const MIN_RPM = 0
const MAX_RPM = 9000
const MIN_TEMPERATURE_C = -40

type SimulatedVehicleControlsProps = {
  speedKph: number | null
  engine: EngineState
  observedHighBeamEnabled: boolean | null
}

export const SimulatedVehicleControls = ({
  speedKph,
  engine,
  observedHighBeamEnabled,
}: SimulatedVehicleControlsProps) => {
  const settings = useEffectiveApplicationSettings().settings
  const [speed, setSpeed] = useState(speedKph ?? 0)
  const [rpm, setRpm] = useState(engine.rpm.value ?? IDLE_RPM)
  const [oilTemperature, setOilTemperatureDraft] = useState(
    engine.oil_temperature_c.value ?? settings.oil_operating_c
  )
  const [coolantTemperature, setCoolantTemperatureDraft] = useState(
    engine.coolant_temperature_c.value ?? settings.coolant_operating_c
  )
  const [isSweeping, setIsSweeping] = useState(false)
  const speedMutation = useMutation(setVehicleSpeedMutation())
  const rpmMutation = useMutation(setEngineRpmMutation())
  const oilMutation = useMutation(setOilTemperatureMutation())
  const coolantMutation = useMutation(setCoolantTemperatureMutation())
  const sweepMutation = useMutation(setVehicleSweepMutation())
  const carMutation = useMutation({
    mutationFn: (running: boolean) =>
      setSimulatedVehicleRunning(running, {
        oilOperatingC: settings.oil_operating_c,
        coolantOperatingC: settings.coolant_operating_c,
      }),
    onSuccess: (_, running) => {
      if (running) {
        setSpeed(0)
        setRpm(IDLE_RPM)
        setOilTemperatureDraft(settings.oil_operating_c)
        setCoolantTemperatureDraft(settings.coolant_operating_c)
      } else {
        setIsSweeping(false)
      }
    },
  })

  const isRunning = speedKph !== null
  const controlsDisabled = carMutation.isPending || sweepMutation.isPending
  const sweeping = isSweeping && isRunning

  return (
    <Card className="min-w-0">
      <CardHeader>
        <CardTitle>Simulated vehicle</CardTitle>
        <CardDescription>
          External vehicle inputs on simulated CAN
        </CardDescription>
      </CardHeader>

      <CardContent className="grid gap-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <Button
              type="button"
              variant={isRunning ? "outline" : "default"}
              disabled={controlsDisabled}
              onClick={() => carMutation.mutate(!isRunning)}
            >
              <PowerIcon aria-hidden="true" />
              {isRunning ? "Stop car" : "Start car"}
            </Button>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Label htmlFor="simulated-sweep">Sweep</Label>
              <Switch
                id="simulated-sweep"
                checked={sweeping}
                disabled={!isRunning || controlsDisabled}
                onCheckedChange={(checked) =>
                  sweepMutation.mutate(
                    { body: { enabled: checked } },
                    {
                      onSuccess: () => {
                        if (!checked) {
                          if (speedKph !== null) setSpeed(speedKph)
                          if (engine.rpm.value !== null) {
                            setRpm(engine.rpm.value)
                          }
                          if (engine.oil_temperature_c.value !== null) {
                            setOilTemperatureDraft(
                              engine.oil_temperature_c.value
                            )
                          }
                          if (engine.coolant_temperature_c.value !== null) {
                            setCoolantTemperatureDraft(
                              engine.coolant_temperature_c.value
                            )
                          }
                        }
                        setIsSweeping(checked)
                      },
                    }
                  )
                }
              />
            </div>
            <div>
              <span
                role="img"
                aria-label={
                  observedHighBeamEnabled === null
                    ? "Virtual-car high beam unavailable"
                    : observedHighBeamEnabled
                      ? "Virtual-car high beam on"
                      : "Virtual-car high beam off"
                }
              >
                <HighBeam
                  aria-hidden="true"
                  className={
                    observedHighBeamEnabled
                      ? "text-blue-500"
                      : "text-muted-foreground opacity-50"
                  }
                />
              </span>
            </div>
          </div>
        </div>

        <TelemetrySlider
          id="simulated-speed"
          label="Vehicle speed"
          unit="km/h"
          minimum={MIN_SPEED_KPH}
          maximum={MAX_SPEED_KPH}
          step={1}
          value={sweeping && speedKph !== null ? speedKph : speed}
          disabled={
            !isRunning ||
            controlsDisabled ||
            sweeping ||
            speedMutation.isPending
          }
          onValueChange={setSpeed}
          onCommit={(value) => {
            setSpeed(value)
            speedMutation.mutate({ body: { speed_kph: value } })
          }}
        />
        <TelemetrySlider
          id="simulated-rpm"
          label="Engine RPM"
          unit="rpm"
          minimum={MIN_RPM}
          maximum={MAX_RPM}
          step={100}
          value={sweeping && engine.rpm.value !== null ? engine.rpm.value : rpm}
          disabled={
            !isRunning || controlsDisabled || sweeping || rpmMutation.isPending
          }
          onValueChange={setRpm}
          onCommit={(value) => {
            setRpm(value)
            rpmMutation.mutate({ body: { rpm: value } })
          }}
        />
        <TelemetrySlider
          id="simulated-oil-temperature"
          label="Oil temperature"
          unit="°C"
          minimum={MIN_TEMPERATURE_C}
          maximum={OIL_MAXIMUM_TEMPERATURE_C}
          step={1}
          value={
            sweeping && engine.oil_temperature_c.value !== null
              ? engine.oil_temperature_c.value
              : oilTemperature
          }
          disabled={
            !isRunning || controlsDisabled || sweeping || oilMutation.isPending
          }
          onValueChange={setOilTemperatureDraft}
          onCommit={(value) => {
            setOilTemperatureDraft(value)
            oilMutation.mutate({ body: { temperature_c: value } })
          }}
        />
        <TelemetrySlider
          id="simulated-coolant-temperature"
          label="Coolant temperature"
          unit="°C"
          minimum={MIN_TEMPERATURE_C}
          maximum={COOLANT_MAXIMUM_TEMPERATURE_C}
          step={1}
          value={
            sweeping && engine.coolant_temperature_c.value !== null
              ? engine.coolant_temperature_c.value
              : coolantTemperature
          }
          disabled={
            !isRunning ||
            controlsDisabled ||
            sweeping ||
            coolantMutation.isPending
          }
          onValueChange={setCoolantTemperatureDraft}
          onCommit={(value) => {
            setCoolantTemperatureDraft(value)
            coolantMutation.mutate({ body: { temperature_c: value } })
          }}
        />
      </CardContent>

      <CardFooter>
        <p className="text-xs text-muted-foreground">
          Speed uses simulated F-CAN. Engine signals use simulation-only PT-CAN
          frames; none are BMW definitions.
        </p>
      </CardFooter>
    </Card>
  )
}
