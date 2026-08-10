import {
  setCoolantTemperature,
  setEngineRpm,
  setOilTemperature,
  setVehicleSpeed,
  silenceCoolantTemperature,
  silenceEngineRpm,
  silenceOilTemperature,
  silenceVehicleSpeed,
} from "@e87canbus/coordinator-client/api/http/sdk.gen"
export const IDLE_RPM = 600

export const setSimulatedVehicleRunning = (
  running: boolean,
  temperatures: { oilOperatingC: number; coolantOperatingC: number }
) =>
  running
    ? Promise.all([
        setVehicleSpeed({ body: { speed_kph: 0 } }),
        setEngineRpm({ body: { rpm: IDLE_RPM } }),
        setOilTemperature({
          body: { temperature_c: temperatures.oilOperatingC },
        }),
        setCoolantTemperature({
          body: { temperature_c: temperatures.coolantOperatingC },
        }),
      ])
    : Promise.all([
        silenceVehicleSpeed({}),
        silenceEngineRpm({}),
        silenceOilTemperature({}),
        silenceCoolantTemperature({}),
      ])
