// @vitest-environment jsdom
import type { ReactNode } from "react"
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { afterEach, beforeEach, expect, it, vi } from "vitest"

import {
  applicationSettingsQueryKey,
  DEFAULT_APPLICATION_SETTINGS,
  type ApplicationSettings,
} from "@/api/settings"
import {
  steeringProfilesQueryKey,
  type ActiveSteeringCurve,
  type SteeringCurveDefinition,
  type StoredSteeringProfile,
} from "@/api/steering"
import { CarDrive } from "@/components/car-drive"
import { CarOverview } from "@/components/car-overview"
import { CarSettingsForm } from "@/components/car-settings-form"
import { CarSteeringEditor } from "@/components/car-steering-editor"
import { ThemeProvider } from "@/components/theme-provider"
import { useLiveStore } from "@/live/live-store"
import { snapshot } from "@/live/test-fixtures"

vi.mock("@/components/steering-curve-editor/components/curve-chart", () => ({
  CurveChart: ({
    active,
    draft,
    onPointChange,
  }: {
    active: SteeringCurveDefinition
    draft: SteeringCurveDefinition
    onPointChange: (index: number, value: number) => void
  }) => (
    <div>
      <span>
        active {active.points[1]?.assistance_per_mille} draft{" "}
        {draft.points[1]?.assistance_per_mille}
      </span>
      <button onClick={() => onPointChange(1, 800)}>Drag draft point</button>
    </div>
  ),
}))

const definition = (
  values = [1000, 890, 780, 670, 380, 0, 0, 0]
): SteeringCurveDefinition => ({
  schema_version: 1,
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
})

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  })

const prepareLiveState = () => {
  const value = snapshot("screens-boot", 3)
  value.data.vehicle = { speed_kph: 100, speed_valid: true }
  value.data.engine = {
    rpm: { value: 6900, status: "valid" },
    oil_temperature_c: { value: 126, status: "valid" },
    coolant_temperature_c: { value: 98, status: "valid" },
  }
  value.data.steering = {
    ...value.data.steering,
    mode: "manual",
    manual_assistance_level: 2,
    active_curve: active(),
    servotronic: {
      effective_assistance: 0.5,
      last_command_reason: "auto",
      watchdog_timed_out: false,
    },
  }
  value.data.devices = {
    registry: {
      ...value.data.devices.registry,
      button_pad: {
        ...value.data.devices.registry.button_pad,
        source_mode: "physical",
        status: "active",
        protocol_version: 1,
        device_session_id: 1,
      },
      servotronic_controller: {
        ...value.data.devices.registry.servotronic_controller,
        status: "active",
        protocol_version: 1,
        device_session_id: 1,
      },
    },
    networks: [],
  }
  useLiveStore.getState().applySnapshot(value)
}

const settingsAt = (
  revision: number,
  overrides: Partial<ApplicationSettings> = {}
): ApplicationSettings => ({
  ...DEFAULT_APPLICATION_SETTINGS,
  revision,
  updated_at: `2026-07-14T12:00:0${revision}.000000Z`,
  ...overrides,
})

const renderScreen = (
  children: ReactNode,
  options: {
    settings?: ApplicationSettings | null
    profiles?: StoredSteeringProfile[]
  } = {}
) => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  if (options.settings !== null) {
    client.setQueryData(
      applicationSettingsQueryKey,
      options.settings ?? DEFAULT_APPLICATION_SETTINGS
    )
  }
  client.setQueryData(steeringProfilesQueryKey, options.profiles ?? [])
  return {
    client,
    ...render(
      <QueryClientProvider client={client}>
        <ThemeProvider disableTransitionOnChange={false}>
          {children}
        </ThemeProvider>
      </QueryClientProvider>
    ),
  }
}

beforeEach(() => {
  prepareLiveState()
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
  useLiveStore.getState().reset()
  localStorage.clear()
  document.documentElement.classList.remove("light", "dark")
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

it("masks all overview and drive live observations after disconnect", () => {
  renderScreen(
    <>
      <CarOverview />
      <CarDrive />
    </>
  )
  expect(screen.getByText("Manual")).toBeTruthy()
  expect(screen.getByText("50%")).toBeTruthy()
  expect(screen.getAllByText("126").length).toBeGreaterThan(0)

  act(() => useLiveStore.getState().transportDisconnected())

  expect(screen.queryByText("Manual")).toBeNull()
  expect(screen.queryByText("50%")).toBeNull()
  expect(screen.queryByText("126")).toBeNull()
  expect(screen.getByText("Active curve unavailable")).toBeTruthy()
  expect(screen.getAllByText("Unavailable").length).toBeGreaterThan(0)
})

it.each(["steering", "device"] as const)(
  "makes steering views unavailable for a %s adapter fault",
  (faultSource) => {
    renderScreen(
      <>
        <CarOverview />
        <CarSteeringEditor />
      </>
    )
    expect(screen.getByText("50%")).toBeTruthy()

    act(() => {
      const current = useLiveStore.getState()
      const fault = {
        kind:
          faultSource === "steering"
            ? ("steering_actuator" as const)
            : ("device_adapter" as const),
        monotonic_s: 4,
        message: "adapter failed",
      }
      current.applyHealth({
        protocol_version: 1,
        boot_id: "screens-boot",
        revision: 4,
        emitted_at: "2026-07-15T00:00:04Z",
        data: {
          ...current.health,
          steering: {
            fault: faultSource === "steering" ? fault : null,
          },
          devices: current.health.devices.map((device) =>
            device.role === "servotronic_controller"
              ? {
                  ...device,
                  fault: faultSource === "device" ? fault : null,
                }
              : device
          ),
        },
      })
    })

    expect(screen.queryByText("50%")).toBeNull()
    expect(
      screen.getAllByText(/servotronic output adapter is faulted/)
    ).toHaveLength(2)
  }
)

it("keeps steering draft local across active updates and activates without false provenance", async () => {
  const requests: Array<{ url: string; body: Record<string, unknown> }> = []
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const body = JSON.parse(String(init?.body)) as Record<string, unknown>
      requests.push({ url: String(input), body })
      return jsonResponse({
        accepted: true,
        boot_id: "screens-boot",
        revision: 4,
      })
    })
  )
  renderScreen(<CarSteeringEditor />, {
    profiles: [profile(), profile("Wet track")],
  })
  expect(
    screen.getByRole("combobox", { name: "Saved profile" }).textContent
  ).toContain("Dry track")
  fireEvent.click(screen.getByRole("button", { name: "Drag draft point" }))
  expect(screen.getByText("active 890 draft 800")).toBeTruthy()

  act(() => {
    const current = useLiveStore.getState()
    current.applySteering({
      protocol_version: 1,
      boot_id: "screens-boot",
      revision: 4,
      emitted_at: "2026-07-15T00:00:04Z",
      data: {
        ...current.steering!,
        active_curve: active(
          definition([1000, 850, 780, 670, 380, 0, 0, 0]),
          2,
          null
        ),
      },
    })
  })
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
})

it("loads settings only from authority and saves one canonical document", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => new Promise<Response>(() => {}))
  )
  const unavailable = renderScreen(<CarSettingsForm />, { settings: null })
  expect(screen.queryByRole("button", { name: "Save settings" })).toBeNull()
  unavailable.unmount()

  const requests: Record<string, unknown>[] = []
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      const body = JSON.parse(String(init?.body)) as Record<string, unknown>
      requests.push(body)
      return jsonResponse(settingsAt(2, body))
    })
  )
  renderScreen(<CarSettingsForm />)
  fireEvent.change(
    screen.getByRole("spinbutton", { name: "Oil warning (°C)" }),
    { target: { value: "124.5" } }
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

it("keeps theme and retry available after an initial settings load failure", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(jsonResponse({ detail: "unavailable" }, 503))
    .mockResolvedValueOnce(jsonResponse(settingsAt(2)))
  vi.stubGlobal("fetch", fetchMock)
  renderScreen(<CarSettingsForm />, { settings: null })

  expect(
    await screen.findByText("Current settings unavailable. Saving is disabled.")
  ).toBeTruthy()
  expect(screen.queryByRole("button", { name: "Save settings" })).toBeNull()
  fireEvent.click(screen.getByRole("button", { name: "Choose color theme" }))
  fireEvent.click(await screen.findByRole("menuitemradio", { name: "Dark" }))
  await waitFor(() =>
    expect(document.documentElement.classList.contains("dark")).toBe(true)
  )

  fireEvent.click(screen.getByRole("button", { name: "Retry settings" }))
  expect(await screen.findByText("Loaded revision 2")).toBeTruthy()
  expect(fetchMock).toHaveBeenCalledTimes(2)
})

it("retains a conflicting settings draft until reload is confirmed", async () => {
  const fetchMock = vi.fn(
    async (_input: RequestInfo | URL, init?: RequestInit) =>
      init?.method === "PUT"
        ? jsonResponse(
            {
              error: {
                code: "settings_revision_conflict",
                message: "settings are now at revision 2",
                current_revision: 2,
              },
            },
            409
          )
        : jsonResponse(settingsAt(2, { oil_warning_c: 126 }))
  )
  vi.stubGlobal("fetch", fetchMock)
  renderScreen(<CarSettingsForm />)
  const oil = screen.getByRole("spinbutton", { name: "Oil warning (°C)" })
  fireEvent.change(oil, { target: { value: "124" } })
  fireEvent.click(screen.getByRole("button", { name: "Save settings" }))

  expect(
    await screen.findByText(/revision 2.*draft was retained/i)
  ).toBeTruthy()
  expect(await screen.findByText("Loaded revision 2")).toBeTruthy()
  expect((oil as HTMLInputElement).value).toBe("124")
  fireEvent.click(
    screen.getByRole("button", { name: "Reload Current Settings" })
  )
  fireEvent.click(screen.getByRole("button", { name: "Keep draft" }))
  expect((oil as HTMLInputElement).value).toBe("124")
  fireEvent.click(
    screen.getByRole("button", { name: "Reload Current Settings" })
  )
  fireEvent.click(screen.getByRole("button", { name: "Discard and reload" }))
  await waitFor(() => expect((oil as HTMLInputElement).value).toBe("126"))
})
