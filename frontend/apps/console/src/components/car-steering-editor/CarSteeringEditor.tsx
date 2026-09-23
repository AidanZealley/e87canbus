import { SteeringCurveEditor } from "@/components/steering-curve-editor"
import { useLiveStore } from "@e87canbus/coordinator-client/live/live-store"

export const CarSteeringEditor = () => {
  const steering = useLiveStore((state) => state.steering)
  const connected = useLiveStore((state) => state.connection.synchronized)
  if (!connected || steering === null) {
    return (
      <section className="grid h-full place-items-center overflow-hidden p-4">
        <div className="text-center">
          <h1 className="text-lg font-semibold">Steering</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Live steering state unavailable
          </p>
        </div>
      </section>
    )
  }

  return (
    <section className="grid h-full min-h-0 grid-rows-[auto_minmax(0,1fr)] gap-3 overflow-hidden p-4">
      <h1 className="text-lg font-semibold">Steering settings</h1>
      <SteeringCurveEditor
        activeCurve={steering.active_curve}
        mode={steering.mode}
        manualAssistanceLevel={steering.manual_assistance_level}
        manualAssistanceLevelCount={steering.manual_assistance_level_count}
        maximumAssistanceActive={steering.maximum_assistance_active}
        className="min-h-0 grid-rows-[minmax(0,1fr)_auto]"
        chartClassName="h-full min-h-0 sm:h-full"
      />
    </section>
  )
}
