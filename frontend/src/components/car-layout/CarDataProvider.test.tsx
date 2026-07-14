// @vitest-environment jsdom
import { useState } from "react"
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react"
import { afterEach, beforeEach, expect, it, vi } from "vitest"

import { DEFAULT_APPLICATION_SETTINGS } from "@/api/settings"
import { DeviceStatusFooter } from "@/components/device-status-footer"
import { emptySnapshot } from "@/components/simulator-workbench/utils"
import { CarDataProvider } from "./CarDataProvider"
import { CarStatusBanners } from "./CarStatusBanners"
import { useCarData } from "./car-data-context"

const mocks = vi.hoisted(() => ({
  snapshotHookCalls: 0,
  socketHookCalls: 0,
  socketSubscriptionsStarted: 0,
  activeSocketSubscriptions: 0,
  socketState: "connected" as
    "connecting" | "connected" | "disconnected" | "reconnecting",
  snapshot: {} as {
    data: typeof emptySnapshot
    isFetched: boolean
    isError: boolean
  },
  settings: {} as {
    settings: typeof DEFAULT_APPLICATION_SETTINGS
    isAuthoritative: boolean
    persistenceFault: boolean
    canSave: boolean
    error: Error | null
    isLoading: boolean
    isRefetching: boolean
    refetch: () => Promise<void>
  },
}))

vi.mock("@/components/simulator-workbench/query", async () => {
  const { useEffect } = await vi.importActual<typeof import("react")>("react")
  return {
    useSimulatorSnapshot: () => {
      mocks.snapshotHookCalls += 1
      return mocks.snapshot
    },
    useSimulatorSocket: () => {
      mocks.socketHookCalls += 1
      useEffect(() => {
        mocks.socketSubscriptionsStarted += 1
        mocks.activeSocketSubscriptions += 1
        return () => {
          mocks.activeSocketSubscriptions -= 1
        }
      }, [])
      return mocks.socketState
    },
  }
})

vi.mock("@/lib/application-settings-query", () => ({
  useEffectiveApplicationSettings: () => mocks.settings,
}))

const snapshotWithOilTemperature = (oilTemperatureC: number) => ({
  ...emptySnapshot,
  session_id: 1,
  revision: 1,
  application: {
    ...emptySnapshot.application,
    engine: {
      ...emptySnapshot.application.engine,
      rpm: { value: 7100, status: "valid" as const },
      oil_temperature_c: {
        value: oilTemperatureC,
        status: "valid" as const,
      },
    },
  },
})

const Consumer = () => {
  const data = useCarData()
  return (
    <div>
      <span>RPM {data.application.engine.rpm.value ?? "none"}</span>
      <span>RPM status {data.application.engine.rpm.status}</span>
      <span>Oil {data.oilSeverity}</span>
      <span>Settings {data.settings.oil_warning_c}</span>
      <span>Fault {String(data.settingsFault)}</span>
      <span>Authoritative {String(data.settingsAuthoritative)}</span>
    </div>
  )
}

const DeviceConsumer = () => {
  const { devices } = useCarData()
  return (
    <>
      <span>
        Devices {devices.map((device) => device.status).join(",") || "none"}
      </span>
      <DeviceStatusFooter devices={devices} />
    </>
  )
}

const SettingsRefetchConsumer = () => {
  const { settingsRefetch, settingsRefetching } = useCarData()
  return (
    <button
      type="button"
      disabled={settingsRefetching}
      onClick={() => void settingsRefetch()}
    >
      {settingsRefetching ? "Retrying settings" : "Retry settings"}
    </button>
  )
}

const ChildNavigation = () => {
  const [route, setRoute] = useState("Overview")
  const { oilSeverity } = useCarData()
  return (
    <div>
      <button type="button" onClick={() => setRoute("Drive")}>
        Navigate
      </button>
      <span>{route}</span>
      <span>Oil {oilSeverity}</span>
    </div>
  )
}

beforeEach(() => {
  mocks.snapshotHookCalls = 0
  mocks.socketHookCalls = 0
  mocks.socketSubscriptionsStarted = 0
  mocks.activeSocketSubscriptions = 0
  mocks.socketState = "connected"
  mocks.snapshot = {
    data: snapshotWithOilTemperature(136),
    isFetched: true,
    isError: false,
  }
  mocks.settings = {
    settings: DEFAULT_APPLICATION_SETTINGS,
    isAuthoritative: true,
    persistenceFault: false,
    canSave: true,
    error: null,
    isLoading: false,
    isRefetching: false,
    refetch: vi.fn(async () => {}),
  }
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

it("keeps one snapshot/socket owner while child navigation preserves warnings", async () => {
  render(
    <CarDataProvider>
      <ChildNavigation />
    </CarDataProvider>
  )

  await waitFor(() => expect(screen.getByText("Oil critical")).toBeTruthy())
  expect(mocks.socketSubscriptionsStarted).toBe(1)
  expect(mocks.activeSocketSubscriptions).toBe(1)

  fireEvent.click(screen.getByRole("button", { name: "Navigate" }))

  expect(screen.getByText("Drive")).toBeTruthy()
  expect(screen.getByText("Oil critical")).toBeTruthy()
  expect(mocks.socketSubscriptionsStarted).toBe(1)
  expect(mocks.activeSocketSubscriptions).toBe(1)
})

it("exposes the settings refetch boundary and pending state", () => {
  const refetch = vi.fn(async () => {})
  mocks.settings = { ...mocks.settings, refetch }
  const view = render(
    <CarDataProvider>
      <SettingsRefetchConsumer />
    </CarDataProvider>
  )

  fireEvent.click(screen.getByRole("button", { name: "Retry settings" }))
  expect(refetch).toHaveBeenCalledTimes(1)

  mocks.settings = { ...mocks.settings, isRefetching: true }
  view.rerender(
    <CarDataProvider>
      <SettingsRefetchConsumer />
    </CarDataProvider>
  )
  expect(
    (
      screen.getByRole("button", {
        name: "Retrying settings",
      }) as HTMLButtonElement
    ).disabled
  ).toBe(true)
})

it("masks cached live telemetry and device health whenever the connection is lost", () => {
  mocks.snapshot = {
    ...mocks.snapshot,
    data: {
      ...mocks.snapshot.data,
      devices: [
        {
          id: "button_pad",
          label: "Button pad",
          status: "online",
          reason: null,
        },
      ],
    },
  }
  mocks.socketState = "reconnecting"
  render(
    <CarDataProvider>
      <Consumer />
      <DeviceConsumer />
    </CarDataProvider>
  )

  expect(screen.getByText("RPM none")).toBeTruthy()
  expect(screen.getByText("RPM status stale")).toBeTruthy()
  expect(screen.getByText("Oil unavailable")).toBeTruthy()
  expect(screen.getByText("Devices none")).toBeTruthy()
  const footer = screen.getByRole("contentinfo", { name: "Device status" })
  expect(within(footer).getAllByText("offline")).toHaveLength(2)
  expect(within(footer).getAllByText(/unavailable/)).toHaveLength(2)
})

it("derives promotions and connection failures on the first render with new inputs", async () => {
  const observed: string[] = []
  const SeverityObserver = () => {
    const { oilSeverity } = useCarData()
    observed.push(oilSeverity)
    return <span>Observed {oilSeverity}</span>
  }
  mocks.snapshot = {
    ...mocks.snapshot,
    data: snapshotWithOilTemperature(100),
  }
  const view = render(
    <CarDataProvider>
      <SeverityObserver />
    </CarDataProvider>
  )
  await waitFor(() => expect(screen.getByText("Observed normal")).toBeTruthy())

  observed.length = 0
  mocks.snapshot = {
    ...mocks.snapshot,
    data: snapshotWithOilTemperature(136),
  }
  view.rerender(
    <CarDataProvider>
      <SeverityObserver />
    </CarDataProvider>
  )
  expect(observed[0]).toBe("critical")

  observed.length = 0
  mocks.socketState = "reconnecting"
  view.rerender(
    <CarDataProvider>
      <SeverityObserver />
    </CarDataProvider>
  )
  expect(observed[0]).toBe("unavailable")
})

it("presents compact connection and configuration faults together", () => {
  mocks.socketState = "connecting"
  mocks.settings = {
    settings: DEFAULT_APPLICATION_SETTINGS,
    isAuthoritative: false,
    persistenceFault: true,
    canSave: false,
    error: new Error("settings offline"),
    isLoading: false,
    isRefetching: false,
    refetch: vi.fn(async () => {}),
  }
  render(
    <CarDataProvider>
      <CarStatusBanners />
    </CarDataProvider>
  )

  expect(screen.getByText("Live data unavailable")).toBeTruthy()
  expect(screen.getByText("Connecting to vehicle data.")).toBeTruthy()
  expect(screen.getByText("Configuration unavailable")).toBeTruthy()
  expect(screen.getByText("Using compiled display defaults.")).toBeTruthy()
})

it("reports faulted defaults and replaces them after settings recovery", () => {
  mocks.settings = {
    settings: DEFAULT_APPLICATION_SETTINGS,
    isAuthoritative: false,
    persistenceFault: true,
    canSave: false,
    error: new Error("settings offline"),
    isLoading: false,
    isRefetching: false,
    refetch: vi.fn(async () => {}),
  }
  const view = render(
    <CarDataProvider>
      <Consumer />
    </CarDataProvider>
  )

  expect(screen.getByText("Settings 125")).toBeTruthy()
  expect(screen.getByText("Fault true")).toBeTruthy()
  expect(screen.getByText("Authoritative false")).toBeTruthy()

  mocks.settings = {
    ...mocks.settings,
    settings: { ...DEFAULT_APPLICATION_SETTINGS, oil_warning_c: 130 },
    isAuthoritative: true,
    persistenceFault: false,
    canSave: true,
    error: null,
  }
  view.rerender(
    <CarDataProvider>
      <Consumer />
    </CarDataProvider>
  )

  expect(screen.getByText("Settings 130")).toBeTruthy()
  expect(screen.getByText("Fault false")).toBeTruthy()
  expect(screen.getByText("Authoritative true")).toBeTruthy()
})

it("re-evaluates an existing warning immediately when authoritative thresholds change", async () => {
  const observed: string[] = []
  const SeverityObserver = () => {
    const { oilSeverity } = useCarData()
    observed.push(oilSeverity)
    return <span>Observed {oilSeverity}</span>
  }
  mocks.snapshot = {
    ...mocks.snapshot,
    data: snapshotWithOilTemperature(127),
  }
  const view = render(
    <CarDataProvider>
      <SeverityObserver />
    </CarDataProvider>
  )
  await waitFor(() => expect(screen.getByText("Observed warning")).toBeTruthy())

  mocks.settings = {
    ...mocks.settings,
    settings: {
      ...DEFAULT_APPLICATION_SETTINGS,
      oil_warning_c: 130,
      oil_critical_c: 140,
    },
  }
  observed.length = 0
  view.rerender(
    <CarDataProvider>
      <SeverityObserver />
    </CarDataProvider>
  )

  expect(observed[0]).toBe("normal")
  expect(screen.getByText("Observed normal")).toBeTruthy()
})
