// @vitest-environment jsdom
import { act, cleanup, render } from "@testing-library/react"
import {
  QueryClient,
  QueryClientProvider,
  useQuery,
} from "@tanstack/react-query"
import { afterEach, expect, it } from "vitest"

import {
  applicationSettingsQueryOptions,
  DEFAULT_APPLICATION_SETTINGS,
} from "@/api/settings"
import { useLiveStore } from "./live-store"
import { snapshot } from "./test-fixtures"

afterEach(cleanup)

it("rerenders a vehicle subscriber without rerendering settings or button panels", () => {
  useLiveStore.getState().reset()
  useLiveStore.getState().applySnapshot(snapshot("render-boot", 1))
  const renders = { vehicle: 0, buttons: 0, settings: 0 }
  const VehicleInstrument = () => {
    renders.vehicle += 1
    const speed = useLiveStore((state) => state.vehicle.speed_kph)
    return <span>{speed}</span>
  }
  const ButtonPanel = () => {
    renders.buttons += 1
    const maximumLed = useLiveStore((state) => state.buttons.led_colours[3])
    return <span>{maximumLed}</span>
  }
  const SettingsPanel = () => {
    renders.settings += 1
    const settings = useQuery(applicationSettingsQueryOptions())
    return <span>{settings.data?.speed_unit}</span>
  }
  const queryClient = new QueryClient()
  queryClient.setQueryData(
    applicationSettingsQueryOptions().queryKey,
    DEFAULT_APPLICATION_SETTINGS
  )
  render(
    <QueryClientProvider client={queryClient}>
      <VehicleInstrument />
      <ButtonPanel />
      <SettingsPanel />
    </QueryClientProvider>
  )
  expect(renders).toEqual({ vehicle: 1, buttons: 1, settings: 1 })
  act(() => {
    useLiveStore.getState().applyVehicle({
      ...snapshot("render-boot", 2),
      data: { speed_kph: 88, speed_valid: true },
    })
  })
  expect(renders).toEqual({ vehicle: 2, buttons: 1, settings: 1 })
})
