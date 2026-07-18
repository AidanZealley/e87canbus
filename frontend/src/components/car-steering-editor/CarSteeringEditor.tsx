import { steeringDependency } from "@/components/car-layout/car-ui"
import { SteeringCurveEditor } from "@/components/steering-curve-editor"
import { useLiveStore } from "@/live/live-store"

export const CarSteeringEditor = () => {
  const steering = useLiveStore((state) => state.steering)
  const vehicle = useLiveStore((state) => state.vehicle)
  const servotronicRegistry = useLiveStore(
    (state) => state.devices.registry.servotronic_controller
  )
  const connected = useLiveStore((state) => state.connection.synchronized)
  const steeringFault = useLiveStore((state) => state.health.steering.fault)
  const servotronicAdapterFault = useLiveStore(
    (state) =>
      state.health.devices.find(
        (device) => device.role === "servotronic_controller"
      )?.fault ?? null
  )
  const dependency = steeringDependency({
    synchronized: connected,
    status: servotronicRegistry.status,
    steering,
    steeringFault,
    deviceAdapterFault: servotronicAdapterFault,
  })

  if (!dependency.available) {
    return (
      <section className="grid h-full place-items-center overflow-hidden p-4">
        <div className="text-center">
          <h1 className="text-lg font-semibold">Steering</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {dependency.reason}
          </p>
        </div>
      </section>
    )
  }

  const speedKph = vehicle.speed_valid ? vehicle.speed_kph : null
  const activeAssistance = dependency.steering.maximum_assistance_active
    ? 1
    : dependency.steering.mode === "manual" || speedKph !== null
      ? dependency.servotronic.effective_assistance
      : null

  return (
    <section className="grid h-full min-h-0 grid-rows-[auto_minmax(0,1fr)] gap-4 overflow-hidden p-4">
      <h1 className="text-lg font-semibold">Steering</h1>
      <SteeringCurveEditor
        activeCurve={dependency.steering.active_curve}
        mode={dependency.steering.mode}
        speedKph={speedKph}
        activeAssistance={activeAssistance}
        className="min-h-0 grid-rows-[minmax(0,1fr)_auto]"
        chartClassName="h-full min-h-0 sm:h-full"
      />
    </section>
  )
}
