import {
  Abs,
  Battery,
  CheckEngine,
  CoolantTemperature,
  Fuel,
  HighBeam,
  LowBeam,
  OilPressure,
  TirePressure,
  TractionControl,
  TurnSignalLeft,
  TurnSignalRight,
} from "@/icons"
import { cn } from "@/lib/utils"

type IndicatorLightsProps = {
  connected: boolean
  highBeamEnabled: boolean
}

const DORMANT = "size-6 text-muted-foreground/20"

/**
 * The tell-tale strip, shared by every dashboard so the lamps sit in one
 * order wherever they appear. Only high beam has a live channel; the rest are
 * laid out dormant, ready for the signals that will drive them.
 */
export const IndicatorLights = ({
  connected,
  highBeamEnabled,
}: IndicatorLightsProps) => {
  const highBeamOn = connected && highBeamEnabled

  return (
    <div
      className="flex w-full items-center justify-between"
      role="status"
      aria-label="Indicator lights"
    >
      <TurnSignalLeft aria-label="Left indicator" className={DORMANT} />
      <div className="flex items-center gap-4">
        <LowBeam aria-label="Dipped beam" className={DORMANT} />
        <HighBeam
          aria-label={highBeamOn ? "High beam on" : "High beam off"}
          className={cn(
            "size-6 transition-colors",
            highBeamOn ? "text-blue-500" : "text-muted-foreground/20"
          )}
        />
        <CheckEngine aria-label="Engine warning" className={DORMANT} />
        <Abs aria-label="ABS warning" className={DORMANT} />
        <TirePressure aria-label="Tyre pressure warning" className={DORMANT} />
        <TractionControl
          aria-label="Traction control warning"
          className={DORMANT}
        />
        <OilPressure aria-label="Oil pressure warning" className={DORMANT} />
        <CoolantTemperature
          aria-label="Coolant temperature warning"
          className={DORMANT}
        />
        <Battery aria-label="Battery warning" className={DORMANT} />
        <Fuel aria-label="Low fuel warning" className={DORMANT} />
      </div>
      <TurnSignalRight aria-label="Right indicator" className={DORMANT} />
    </div>
  )
}
