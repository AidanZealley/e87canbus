import { useEffect, useState } from "react"
import { useMutation } from "@tanstack/react-query"
import { PowerIcon } from "lucide-react"
import type { EngineState } from "@/api/live-contract.gen"

import {
  setCoolantTemperatureMutation,
  setEngineRpmMutation,
  setOilTemperatureMutation,
  setVehicleSpeedMutation,
} from "@/api/http/@tanstack/react-query.gen"
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
  SWEEP_INTERVAL_MS,
  SWEEP_PERIOD_MS,
  sweepPhase,
  sweptValue,
} from "./utils"
import {
  COOLANT_MAXIMUM_TEMPERATURE_C,
  OIL_MAXIMUM_TEMPERATURE_C,
} from "@/components/car-layout/engine-temperature-scale"
import { useEffectiveApplicationSettings } from "@/lib/application-settings-query"
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
  const controlsDisabled = carMutation.isPending
  const sweeping = isSweeping && isRunning

  const { mutate: mutateSpeed } = speedMutation
  const { mutate: mutateRpm } = rpmMutation
  const { mutate: mutateOil } = oilMutation
  const { mutate: mutateCoolant } = coolantMutation

  useEffect(() => {
    if (!sweeping) return

    const startedAt = Date.now()
    const interval = window.setInterval(() => {
      const phase = sweepPhase(Date.now() - startedAt, SWEEP_PERIOD_MS)

      const nextSpeed = sweptValue(MIN_SPEED_KPH, MAX_SPEED_KPH, 1, phase)
      const nextRpm = sweptValue(MIN_RPM, MAX_RPM, 100, phase)
      const nextOil = sweptValue(
        MIN_TEMPERATURE_C,
        OIL_MAXIMUM_TEMPERATURE_C,
        1,
        phase
      )
      const nextCoolant = sweptValue(
        MIN_TEMPERATURE_C,
        COOLANT_MAXIMUM_TEMPERATURE_C,
        1,
        phase
      )

      setSpeed(nextSpeed)
      setRpm(nextRpm)
      setOilTemperatureDraft(nextOil)
      setCoolantTemperatureDraft(nextCoolant)

      mutateSpeed({ body: { speed_kph: nextSpeed } })
      mutateRpm({ body: { rpm: nextRpm } })
      mutateOil({ body: { temperature_c: nextOil } })
      mutateCoolant({ body: { temperature_c: nextCoolant } })
    }, SWEEP_INTERVAL_MS)

    return () => window.clearInterval(interval)
  }, [sweeping, mutateSpeed, mutateRpm, mutateOil, mutateCoolant])

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
                onCheckedChange={(checked) => setIsSweeping(checked)}
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
          value={speed}
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
          value={rpm}
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
          value={oilTemperature}
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
          value={coolantTemperature}
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
