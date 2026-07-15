import { useState } from "react"
import { useMutation } from "@tanstack/react-query"
import { CarFrontIcon, PowerIcon } from "lucide-react"
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
import { TelemetrySlider } from "./TelemetrySlider"

const MIN_SPEED_KPH = 0
const MAX_SPEED_KPH = 300
const IDLE_RPM = 600
const OPERATING_TEMPERATURE_C = 90

type SimulatedVehicleControlsProps = {
  speedKph: number | null
  engine: EngineState
}

export const SimulatedVehicleControls = ({
  speedKph,
  engine,
}: SimulatedVehicleControlsProps) => {
  const [speed, setSpeed] = useState(speedKph ?? 0)
  const [rpm, setRpm] = useState(engine.rpm.value ?? IDLE_RPM)
  const [oilTemperature, setOilTemperatureDraft] = useState(
    engine.oil_temperature_c.value ?? OPERATING_TEMPERATURE_C
  )
  const [coolantTemperature, setCoolantTemperatureDraft] = useState(
    engine.coolant_temperature_c.value ?? OPERATING_TEMPERATURE_C
  )
  const speedMutation = useMutation({ mutationFn: setVehicleSpeed })
  const rpmMutation = useMutation({ mutationFn: setEngineRpm })
  const oilMutation = useMutation({ mutationFn: setOilTemperature })
  const coolantMutation = useMutation({ mutationFn: setCoolantTemperature })
  const carMutation = useMutation({
    mutationFn: (running: boolean) =>
      running
        ? Promise.all([
            setVehicleSpeed(0),
            setEngineRpm(IDLE_RPM),
            setOilTemperature(OPERATING_TEMPERATURE_C),
            setCoolantTemperature(OPERATING_TEMPERATURE_C),
          ])
        : Promise.all([
            silenceVehicleSpeed(),
            silenceEngineRpm(),
            silenceOilTemperature(),
            silenceCoolantTemperature(),
          ]),
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
        <CardDescription>External vehicle inputs on simulated CAN</CardDescription>
        <CardAction>
          <CarFrontIcon aria-hidden="true" />
        </CardAction>
      </CardHeader>

      <CardContent className="grid gap-5">
        <Button
          type="button"
          variant={isRunning ? "outline" : "default"}
          disabled={controlsDisabled}
          onClick={() => carMutation.mutate(!isRunning)}
        >
          <PowerIcon aria-hidden="true" />
          {isRunning ? "Stop car" : "Start car"}
        </Button>

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
            speedMutation.mutate(value)
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
            rpmMutation.mutate(value)
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
            oilMutation.mutate(value)
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
            coolantMutation.mutate(value)
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
