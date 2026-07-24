import { useState } from "react"
import { useMutation } from "@tanstack/react-query"
import { LightbulbIcon, PowerIcon } from "lucide-react"
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
import { TelemetrySlider } from "./TelemetrySlider"
import {
  IDLE_RPM,
  OPERATING_TEMPERATURE_C,
  setSimulatedVehicleRunning,
} from "../../simulated-vehicle-power"

const MIN_SPEED_KPH = 0
const MAX_SPEED_KPH = 300

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
  const [speed, setSpeed] = useState(speedKph ?? 0)
  const [rpm, setRpm] = useState(engine.rpm.value ?? IDLE_RPM)
  const [oilTemperature, setOilTemperatureDraft] = useState(
    engine.oil_temperature_c.value ?? OPERATING_TEMPERATURE_C
  )
  const [coolantTemperature, setCoolantTemperatureDraft] = useState(
    engine.coolant_temperature_c.value ?? OPERATING_TEMPERATURE_C
  )
  const speedMutation = useMutation(setVehicleSpeedMutation())
  const rpmMutation = useMutation(setEngineRpmMutation())
  const oilMutation = useMutation(setOilTemperatureMutation())
  const coolantMutation = useMutation(setCoolantTemperatureMutation())
  const carMutation = useMutation({
    mutationFn: setSimulatedVehicleRunning,
    onSuccess: (_, running) => {
      if (running) {
        setSpeed(0)
        setRpm(IDLE_RPM)
        setOilTemperatureDraft(OPERATING_TEMPERATURE_C)
        setCoolantTemperatureDraft(OPERATING_TEMPERATURE_C)
      }
    },
  })

  const isRunning = speedKph !== null
  const controlsDisabled = carMutation.isPending

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
          <div className="flex items-center gap-2">
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
                <LightbulbIcon
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
          disabled={!isRunning || controlsDisabled || speedMutation.isPending}
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
          minimum={0}
          maximum={9000}
          step={100}
          value={rpm}
          disabled={!isRunning || controlsDisabled || rpmMutation.isPending}
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
          minimum={-40}
          maximum={200}
          step={1}
          value={oilTemperature}
          disabled={!isRunning || controlsDisabled || oilMutation.isPending}
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
          minimum={-40}
          maximum={200}
          step={1}
          value={coolantTemperature}
          disabled={!isRunning || controlsDisabled || coolantMutation.isPending}
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
