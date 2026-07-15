// @vitest-environment jsdom
import type { ReactNode } from "react"
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { afterEach, beforeEach, expect, it, vi } from "vitest"

import { DEFAULT_APPLICATION_SETTINGS } from "@/api/settings"
import type {
  ActiveSteeringCurve,
  SteeringCurveDefinition,
  StoredSteeringProfile,
} from "@/api/steering"
import type { CarData } from "@/components/car-layout/car-data-context"
import { CarDrive } from "@/components/car-drive"
import { CarOverview } from "@/components/car-overview"
import { CarSettingsForm } from "@/components/car-settings-form"
import { CarSteeringEditor } from "@/components/car-steering-editor"
import { emptySnapshot } from "@/components/simulator-workbench/utils"
import { ThemeProvider } from "@/components/theme-provider"

const mocks = vi.hoisted(() => ({ data: {} as CarData }))

vi.mock("@/components/car-layout", async () => {
  const actual = await vi.importActual<
    typeof import("@/components/car-layout")
  >("@/components/car-layout")
  return { ...actual, useCarData: () => mocks.data }
})

vi.mock("@/components/steering-curve-editor/components/curve-chart", () => ({
  CurveChart: ({
    active,
    draft,
    activeSpeedKph,
    activeAssistance,
    onPointChange,
  }: {
    active: SteeringCurveDefinition
    draft: SteeringCurveDefinition
    activeSpeedKph: number | null
    activeAssistance: number | null
    onPointChange: (index: number, value: number) => void
  }) => (
    <div>
      <span>
        active {active.points[1]?.assistance_per_mille} draft{" "}
        {draft.points[1]?.assistance_per_mille}
      </span>
      <span>
        marker {activeSpeedKph} {activeAssistance}
      </span>
      <button onClick={() => onPointChange(1, 800)}>Drag draft point</button>
    </div>
  ),
}))

const definition = (
  values = [1000, 890, 780, 670, 380, 0, 0, 0]
): SteeringCurveDefinition => ({
  schema_version: 1,
  interpolation: "linear-v1",
  points: [0, 100, 200, 300, 600, 1000, 1600, 2500].map(
    (speed_deci_kph, index) => ({
      speed_deci_kph,
      assistance_per_mille: values[index] ?? 0,
    })
  ),
})

const profile = (
  name = "Dry track",
  value = definition(),
  revision = 1
): StoredSteeringProfile => ({
  profile_id:
    name === "Dry track"
      ? "11111111-1111-4111-8111-111111111111"
      : "22222222-2222-4222-8222-222222222222",
  name,
  revision,
  definition: value,
  created_at: "2026-07-14T00:00:00.000000Z",
  updated_at: "2026-07-14T00:00:00.000000Z",
})

const active = (
  value = definition(),
  revision = 1,
  saved: StoredSteeringProfile | null = profile()
): ActiveSteeringCurve => ({
  definition: value,
  fingerprint: `fingerprint-${revision}`,
  activation_revision: revision,
  status: "active",
  saved_profile_id: saved?.profile_id ?? null,
  saved_profile_revision: saved?.revision ?? null,
  supported_interpolations: ["linear-v1", "monotone-cubic-v1"],
})

const initialCarData = (): CarData => ({
  application: {
    ...emptySnapshot.application,
    vehicle_speed_kph: 100,
    speed_valid: true,
    steering_mode: "manual",
    manual_assistance_level: 2,
    active_steering_curve: active(),
    engine: {
      rpm: { value: 7100, status: "valid" },
      oil_temperature_c: { value: 125, status: "valid" },
      coolant_temperature_c: { value: 115, status: "valid" },
    },
  },
  steeringController: {
    effective_assistance: 0.78,
    last_command_reason: "manual",
    watchdog_timed_out: false,
  },
  devices: [
    { id: "button_pad", label: "Button pad", status: "online", reason: null },
    {
      id: "steering_controller",
      label: "Steering controller",
      status: "degraded",
      reason: "simulated warning",
    },
  ],
  connectionState: "connected",
  connectionFault: false,
  settings: DEFAULT_APPLICATION_SETTINGS,
  settingsAuthoritative: true,
  settingsFault: false,
  settingsError: null,
  settingsLoading: false,
  settingsRefetching: false,
  settingsRefetch: vi.fn(async () => {}),
  oilSeverity: "warning",
  coolantSeverity: "critical",
})

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  })

const renderScreen = (children: ReactNode) => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <ThemeProvider disableTransitionOnChange={false}>
        {children}
      </ThemeProvider>
    </QueryClientProvider>
  )
}

beforeEach(() => {
  mocks.data = initialCarData()
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: vi.fn().mockReturnValue({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  })
})

afterEach(() => {
  cleanup()
  localStorage.clear()
  document.documentElement.classList.remove("light", "dark")
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

it("renders overview steering provenance, one-based level, temperatures and devices", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => jsonResponse({ profiles: [profile()] }))
  )
  renderScreen(<CarOverview />)

  expect(screen.getByText("Manual")).toBeTruthy()
  expect(screen.getByText("Level 3 of 8")).toBeTruthy()
  expect(screen.getByText("78%")).toBeTruthy()
  expect(await screen.findByText("Dry track")).toBeTruthy()
  expect(screen.getByText("Warning")).toBeTruthy()
  expect(screen.getByText("Critical")).toBeTruthy()
  const footer = screen.getByRole("contentinfo", { name: "Device status" })
  expect(within(footer).getByText("online")).toBeTruthy()
  expect(within(footer).getByText("degraded")).toBeTruthy()
})

it("renders drive units, RPM stages and stale values honestly", () => {
  const view = renderScreen(<CarDrive />)
  expect(screen.getByLabelText("Speed").textContent).toContain("62")
  expect(screen.getByLabelText("Speed").textContent).toContain("mph")
  expect(screen.getByText("Shift stage 2")).toBeTruthy()

  mocks.data = {
    ...mocks.data,
    settings: {
      ...mocks.data.settings,
      speed_unit: "kmh",
      temperature_unit: "f",
    },
    application: {
      ...mocks.data.application,
      engine: {
        rpm: { value: null, status: "stale" },
        oil_temperature_c: { value: null, status: "stale" },
        coolant_temperature_c: { value: 115, status: "valid" },
      },
    },
    oilSeverity: "unavailable",
  }
  view.rerender(
    <QueryClientProvider client={new QueryClient()}>
      <ThemeProvider disableTransitionOnChange={false}>
        <CarDrive />
      </ThemeProvider>
    </QueryClientProvider>
  )

  expect(screen.getByLabelText("Speed").textContent).toContain("100")
  expect(screen.getByLabelText("Speed").textContent).toContain("km/h")
  expect(screen.getByLabelText("Engine speed").textContent).toContain("—")
  expect(screen.getByLabelText("Oil temperature").textContent).toContain(
    "Stale"
  )
  expect(screen.getByLabelText("Coolant temperature").textContent).toContain(
    "239"
  )
})

it("keeps steering draft local, survives active updates and confirms one provenance-safe activation", async () => {
  const requests: Array<{
    url: string
    method: string
    body?: Record<string, unknown>
  }> = []
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const method = init?.method ?? "GET"
      if (method === "GET")
        return jsonResponse({ profiles: [profile(), profile("Wet track")] })
      const body = JSON.parse(String(init?.body)) as Record<string, unknown>
      requests.push({ url, method, body })
      return jsonResponse({ accepted: true, boot_id: "test-boot", revision: 2 })
    })
  )
  const view = renderScreen(<CarSteeringEditor />)
  await screen.findByRole("combobox", { name: "Saved profile" })
  fireEvent.click(screen.getByRole("button", { name: "Drag draft point" }))
  expect(screen.getByText("active 890 draft 800")).toBeTruthy()

  mocks.data = {
    ...mocks.data,
    application: {
      ...mocks.data.application,
      active_steering_curve: active(
        definition([1000, 850, 780, 670, 380, 0, 0, 0]),
        2,
        null
      ),
    },
  }
  view.rerender(
    <QueryClientProvider client={new QueryClient()}>
      <ThemeProvider disableTransitionOnChange={false}>
        <CarSteeringEditor />
      </ThemeProvider>
    </QueryClientProvider>
  )
  expect(screen.getByText("active 850 draft 800")).toBeTruthy()

  fireEvent.click(screen.getByRole("button", { name: "Apply" }))
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }))
  expect(requests).toHaveLength(0)
  fireEvent.click(screen.getByRole("button", { name: "Apply" }))
  fireEvent.click(screen.getByRole("button", { name: "Confirm activation" }))
  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0]?.url).toMatch(/api\/commands\/steering-curve$/)
  expect(requests[0]?.body).toEqual({
    definition: definition([1000, 800, 780, 670, 380, 0, 0, 0]),
  })
  expect(requests.some((request) => request.url.endsWith("/profiles"))).toBe(
    false
  )
})

it("initializes settings only from authority and saves one canonical complete document", async () => {
  mocks.data = {
    ...mocks.data,
    settingsAuthoritative: false,
    settingsLoading: false,
  }
  const view = renderScreen(<CarSettingsForm />)
  expect(screen.getByText(/Current settings unavailable/)).toBeTruthy()
  expect(screen.queryByRole("button", { name: "Save settings" })).toBeNull()

  mocks.data = { ...mocks.data, settingsAuthoritative: true }
  view.rerender(
    <QueryClientProvider client={new QueryClient()}>
      <ThemeProvider disableTransitionOnChange={false}>
        <CarSettingsForm />
      </ThemeProvider>
    </QueryClientProvider>
  )
  const requests: Record<string, unknown>[] = []
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      const body = JSON.parse(String(init?.body)) as Record<string, unknown>
      requests.push(body)
      return jsonResponse({
        ...DEFAULT_APPLICATION_SETTINGS,
        ...body,
        revision: 2,
        updated_at: "2026-07-14T12:00:00.000000Z",
      })
    })
  )
  fireEvent.change(
    screen.getByRole("spinbutton", { name: "Oil warning (°C)" }),
    {
      target: { value: "124.5" },
    }
  )
  fireEvent.click(screen.getByRole("button", { name: "Save settings" }))
  await screen.findByText("Saved revision 2")
  expect(requests).toHaveLength(1)
  expect(requests[0]).toMatchObject({
    expected_revision: 1,
    oil_warning_c: 124.5,
    coolant_critical_c: 115,
    redline_rpm: 7200,
  })
  expect(Object.keys(requests[0] ?? {})).toHaveLength(10)
})

it("keeps theme and retry available when the initial settings load fails", async () => {
  const refetch = vi.fn(async () => {})
  const fetchMock = vi.fn()
  vi.stubGlobal("fetch", fetchMock)
  mocks.data = {
    ...mocks.data,
    settingsAuthoritative: false,
    settingsFault: true,
    settingsError: new Error("settings unavailable"),
    settingsLoading: false,
    settingsRefetch: refetch,
  }
  renderScreen(<CarSettingsForm />)

  expect(screen.queryByRole("button", { name: "Save settings" })).toBeNull()
  expect(
    screen.getByText("Current settings unavailable. Saving is disabled.")
  ).toBeTruthy()

  fireEvent.click(screen.getByRole("button", { name: "Choose color theme" }))
  fireEvent.click(await screen.findByRole("menuitemradio", { name: "Dark" }))
  await waitFor(() =>
    expect(document.documentElement.classList.contains("dark")).toBe(true)
  )
  expect(fetchMock).not.toHaveBeenCalled()

  fireEvent.click(screen.getByRole("button", { name: "Retry settings" }))
  expect(refetch).toHaveBeenCalledTimes(1)
  expect(fetchMock).not.toHaveBeenCalled()
})

it("confirms conflict reload while retaining the dirty draft until accepted", async () => {
  const fetchMock = vi.fn(async () =>
    jsonResponse(
      {
        error: {
          code: "settings_revision_conflict",
          message: "settings are now at revision 2",
          current_revision: 2,
        },
      },
      409
    )
  )
  vi.stubGlobal("fetch", fetchMock)
  const view = renderScreen(<CarSettingsForm />)
  const oil = screen.getByRole("spinbutton", { name: "Oil warning (°C)" })
  fireEvent.change(oil, { target: { value: "124" } })
  fireEvent.click(screen.getByRole("button", { name: "Save settings" }))
  expect(
    await screen.findByText(/revision 2.*draft was retained/i)
  ).toBeTruthy()
  expect((oil as HTMLInputElement).value).toBe("124")
  expect(
    screen.getByRole("button", { name: "Reload Current Settings" })
  ).toBeTruthy()

  mocks.data = {
    ...mocks.data,
    settings: {
      ...DEFAULT_APPLICATION_SETTINGS,
      revision: 2,
      oil_warning_c: 126,
      updated_at: "2026-07-14T12:00:00.000000Z",
    },
  }
  view.rerender(
    <QueryClientProvider client={new QueryClient()}>
      <ThemeProvider disableTransitionOnChange={false}>
        <CarSettingsForm />
      </ThemeProvider>
    </QueryClientProvider>
  )
  expect(screen.getByText("Loaded revision 2")).toBeTruthy()
  expect((oil as HTMLInputElement).value).toBe("124")

  fireEvent.click(
    screen.getByRole("button", { name: "Reload Current Settings" })
  )
  expect(screen.getByText("Reload current settings?")).toBeTruthy()
  expect(screen.getByText(/load revision 2/)).toBeTruthy()
  fireEvent.click(screen.getByRole("button", { name: "Keep draft" }))
  expect((oil as HTMLInputElement).value).toBe("124")

  fireEvent.click(
    screen.getByRole("button", { name: "Reload Current Settings" })
  )
  fireEvent.click(screen.getByRole("button", { name: "Discard and reload" }))
  await waitFor(() =>
    expect(
      (
        screen.getByRole("spinbutton", {
          name: "Oil warning (°C)",
        }) as HTMLInputElement
      ).value
    ).toBe("126")
  )
  expect(screen.getByText("Settings are current")).toBeTruthy()
  expect(
    screen.queryByRole("button", { name: "Reload Current Settings" })
  ).toBeNull()
})
