import absRaw from "./raw/ISO_7000_-_Ref-No_1407.svg?raw"
import batteryRaw from "./raw/ISO_7000_-_Ref-No_0247.svg?raw"
import checkEngineRaw from "./raw/ISO_7000_-_Ref-No_0640.svg?raw"
import coolantTemperatureRaw from "./raw/ISO_7000_-_Ref-No_0246.svg?raw"
import fuelRaw from "./raw/ISO_7000_-_Ref-No_0245.svg?raw"
import highBeamRaw from "./raw/ISO_7000_-_Ref-No_0082.svg?raw"
import lowBeamRaw from "./raw/ISO_7000_-_Ref-No_0083.svg?raw"
import oilPressureRaw from "./raw/ISO_7000_-_Ref-No_0248.svg?raw"
import tirePressureRaw from "./raw/ISO_7000_-_Ref-No_1434A.svg?raw"
import tractionControlRaw from "./raw/ISO_7000_-_Ref-No_2649.svg?raw"
import turnSignalLeftRaw from "./raw/turn-signal-left.svg?raw"
import turnSignalRightRaw from "./raw/turn-signal-right.svg?raw"

import { createDashboardIcon } from "./dashboard-icon-utils"

export type { DashboardIconProps } from "./dashboard-icon-utils"

export const HighBeam = createDashboardIcon("HighBeam", highBeamRaw)
export const LowBeam = createDashboardIcon("LowBeam", lowBeamRaw)
export const TurnSignalLeft = createDashboardIcon(
  "TurnSignalLeft",
  turnSignalLeftRaw
)
export const TurnSignalRight = createDashboardIcon(
  "TurnSignalRight",
  turnSignalRightRaw
)
export const Fuel = createDashboardIcon("Fuel", fuelRaw)
export const CoolantTemperature = createDashboardIcon(
  "CoolantTemperature",
  coolantTemperatureRaw
)
export const Battery = createDashboardIcon("Battery", batteryRaw)
export const OilPressure = createDashboardIcon("OilPressure", oilPressureRaw)
export const CheckEngine = createDashboardIcon("CheckEngine", checkEngineRaw)
export const Abs = createDashboardIcon("Abs", absRaw)
export const TirePressure = createDashboardIcon("TirePressure", tirePressureRaw)
export const TractionControl = createDashboardIcon(
  "TractionControl",
  tractionControlRaw
)
