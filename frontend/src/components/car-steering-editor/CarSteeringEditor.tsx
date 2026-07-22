import { useServotronicAvailability } from "@/components/car-layout/use-servotronic-availability"
import { SteeringCurveEditor } from "@/components/steering-curve-editor"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { useLiveStore } from "@/live/live-store"

export const CarSteeringEditor = () => {
  const steering = useLiveStore((state) => state.steering)
  const vehicle = useLiveStore((state) => state.vehicle)
  const servotronicRegistry = useLiveStore(
    (state) => state.devices.registry.servotronic_controller
  )
  const connected = useLiveStore((state) => state.connection.synchronized)
  const availability = useServotronicAvailability()
  const steeringFault = useLiveStore((state) => state.health.steering.fault)
  const servotronicAdapterFault = useLiveStore(
    (state) =>
      state.health.devices.find(
        (device) => device.role === "servotronic_controller"
      )?.fault ?? null
  )
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

  const speedKph = vehicle.speed_valid ? vehicle.speed_kph : null
  const faultsPresent =
    steeringFault !== null || servotronicAdapterFault !== null
  const activeAssistance = !availability.telemetry
    ? null
    : steering.maximum_assistance_active
      ? 1
      : steering.mode === "manual" || speedKph !== null
        ? (steering.servotronic?.effective_assistance ?? null)
        : null
  const operation = controllerOperation(
    servotronicRegistry.status,
    steering.servotronic?.inhibit_reason ?? null,
    steering.mode,
    steering.maximum_assistance_active,
    faultsPresent,
    steering.servotronic !== null
  )

  return (
    <section className="grid h-full min-h-0 grid-rows-[auto_auto_minmax(0,1fr)] gap-3 overflow-hidden p-4">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-lg font-semibold">Steering</h1>
        <div className="flex gap-2">
          <Badge variant={operation.variant}>{operation.label}</Badge>
          {steering.servotronic ? (
            <Badge variant="outline">
              {steering.servotronic.active_curve_source === "coordinator_ram"
                ? "Coordinator curve"
                : "Built-in fallback"}
            </Badge>
          ) : null}
        </div>
      </div>
      <Alert
        variant={
          operation.variant === "destructive" ? "destructive" : "default"
        }
      >
        <AlertTitle>{operation.label}</AlertTitle>
        <AlertDescription>{operation.detail}</AlertDescription>
      </Alert>
      <SteeringCurveEditor
        activeCurve={steering.active_curve}
        mode={steering.mode}
        manualAssistanceLevel={steering.manual_assistance_level}
        maximumAssistanceActive={steering.maximum_assistance_active}
        speedKph={speedKph}
        activeAssistance={activeAssistance}
        activationAvailable={availability.activation}
        modeControlAvailable={availability.modeControl}
        className="min-h-0 grid-rows-[minmax(0,1fr)_auto]"
        chartClassName="h-full min-h-0 sm:h-full"
      />
    </section>
  )
}

const controllerOperation = (
  status:
    | "disabled"
    | "not_found"
    | "pending"
    | "active"
    | "stale"
    | "incompatible"
    | "fault",
  inhibit: string | null,
  mode: "auto" | "manual",
  maximum: boolean,
  faulted: boolean,
  telemetryAvailable: boolean
): {
  label: string
  detail: string
  variant: "default" | "secondary" | "destructive"
} => {
  if (faulted || status === "fault") {
    return {
      label: "Controller fault",
      detail:
        "Servotronic reported a controller or adapter fault. Curve editing and manual controls are disabled.",
      variant: "destructive",
    }
  }
  if (status !== "active") {
    return {
      label: `Controller ${status.replace("_", " ")}`,
      detail:
        "The saved curve remains visible, but it cannot be applied and output controls are disabled until the controller is active.",
      variant: "secondary",
    }
  }
  if (!telemetryAvailable) {
    return {
      label: "Waiting for telemetry",
      detail:
        "The controller is registered, but no Servotronic status sample has arrived yet.",
      variant: "secondary",
    }
  }
  if (maximum) {
    return {
      label: "Maximum assistance",
      detail:
        "Maximum override is active and does not depend on vehicle speed.",
      variant: "default",
    }
  }
  if (mode === "manual") {
    return {
      label: "Manual control",
      detail:
        "The selected manual assistance level is active and does not depend on vehicle speed.",
      variant: "default",
    }
  }
  if (inhibit && inhibit !== "none") {
    const reason =
      (
        {
          no_speed: "waiting for a speed signal",
          stale_speed: "the speed signal is stale",
          invalid_speed: "the speed signal is invalid",
          can_fault: "the controller detected a CAN fault",
        } as Record<string, string>
      )[inhibit] ?? "the controller reported an unknown inhibit"
    return {
      label: "Curve output inhibited",
      detail: `Automatic curve following is off because ${reason}.`,
      variant: inhibit === "can_fault" ? "destructive" : "secondary",
    }
  }
  return {
    label: "Following curve",
    detail:
      "The controller is applying the active assistance curve to the current vehicle speed.",
    variant: "default",
  }
}
