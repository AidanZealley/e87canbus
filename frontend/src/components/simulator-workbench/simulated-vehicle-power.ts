import {
  setCoolantTemperature,
  setEngineRpm,
  setOilTemperature,
  setVehicleSpeed,
  silenceCoolantTemperature,
  silenceEngineRpm,
  silenceOilTemperature,
  silenceVehicleSpeed,
} from "@/api/http/sdk.gen"

export const IDLE_RPM = 600
export const OPERATING_TEMPERATURE_C = 90

export const setSimulatedVehicleRunning = (running: boolean) =>
  running
    ? Promise.all([
        setVehicleSpeed({ body: { speed_kph: 0 } }),
        setEngineRpm({ body: { rpm: IDLE_RPM } }),
        setOilTemperature({
          body: { temperature_c: OPERATING_TEMPERATURE_C },
        }),
        setCoolantTemperature({
          body: { temperature_c: OPERATING_TEMPERATURE_C },
        }),
      ])
    : Promise.all([
        silenceVehicleSpeed({}),
        silenceEngineRpm({}),
        silenceOilTemperature({}),
        silenceCoolantTemperature({}),
      ])
