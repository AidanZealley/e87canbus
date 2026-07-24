import { useLiveStore } from "@/live/live-store"
import { SimulatedVehicleControls } from "./components/simulated-vehicle-controls/SimulatedVehicleControls"

const unavailableEngine = {
  rpm: { value: null, status: "stale" as const },
  oil_temperature_c: { value: null, status: "stale" as const },
  coolant_temperature_c: { value: null, status: "stale" as const },
}

export const LiveSimulatedVehicleControls = () => {
  const synchronized = useLiveStore((state) => state.connection.synchronized)
  const vehicle = useLiveStore((state) => state.vehicle)
  const engine = useLiveStore((state) => state.engine)
  const observedHighBeamEnabled = useLiveStore(
    (state) => state.lighting.observed_high_beam_enabled
  )

  return (
    <SimulatedVehicleControls
      speedKph={synchronized && vehicle.speed_valid ? vehicle.speed_kph : null}
      engine={synchronized ? engine : unavailableEngine}
      observedHighBeamEnabled={synchronized ? observedHighBeamEnabled : null}
    />
  )
}
