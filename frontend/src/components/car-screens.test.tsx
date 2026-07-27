// @vitest-environment jsdom
import type { ReactNode } from "react"
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { afterEach, beforeEach, expect, it, vi } from "vitest"

import {
  getApplicationSettingsQueryKey,
  getSavedSteeringProfileQueryKey,
  listSteeringProfilesQueryKey,
} from "@/api/http/@tanstack/react-query.gen"
import type {
  ApplicationSettingsResponse,
  SteeringProfileResponse,
} from "@/api/http/types.gen"
import type {
  ActiveSteeringCurveState,
  SteeringCurveDefinition,
} from "@/api/live-contract.gen"
import { CarDrive } from "@/components/car-drive"
import { CarSettings } from "@/components/car-settings"
import { CarSteeringEditor } from "@/components/car-steering-editor"
import { ThemeProvider } from "@/components/theme-provider"
import { DEFAULT_APPLICATION_SETTINGS } from "@/lib/application-settings"
import { useLiveStore } from "@/live/live-store"
import { snapshot } from "@/live/test-fixtures"

const toastMock = vi.hoisted(() => ({ error: vi.fn(), success: vi.fn() }))

vi.mock("sonner", () => ({ toast: toastMock }))

vi.mock("@/components/steering-curve-editor/components/curve-chart", () => ({
  CurveChart: ({
    active,
    draft,
    onPointChange,
    onPointCommit,
  }: {
    active: SteeringCurveDefinition
    draft: SteeringCurveDefinition
    onPointChange?: (index: number, value: number) => void
    onPointCommit?: (definition: SteeringCurveDefinition) => void
  }) => (
    <div>
      <span>
        active {active.points[1]?.assistance_per_mille} draft{" "}
        {draft.points[1]?.assistance_per_mille}
      </span>
      <button
        onClick={() => {
          onPointChange?.(1, 800)
          onPointCommit?.(definition([1000, 800, 780, 670, 380, 0, 0, 0]))
        }}
      >
        Drag draft point
      </button>
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
  ) as SteeringCurveDefinition["points"],
})

const profile = (
  name = "Dry track",
  value = definition(),
  revision = 1
): SteeringProfileResponse => ({
  profile_id:
    name === "Dry track"
      ? "11111111-1111-4111-8111-111111111111"
      : "22222222-2222-4222-8222-222222222222",
  name,
  revision,
  definition: value as SteeringProfileResponse["definition"],
  created_at: "2026-07-14T00:00:00.000000Z",
  updated_at: "2026-07-14T00:00:00.000000Z",
})

const active = (
  value = definition(),
  revision = 1,
  saved: SteeringProfileResponse | null = profile()
): ActiveSteeringCurveState => ({
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

const requestUrl = (input: RequestInfo | URL) =>
  input instanceof Request ? input.url : String(input)

const requestMethod = (input: RequestInfo | URL, init?: RequestInit) =>
  input instanceof Request ? input.method : (init?.method ?? "GET")

const requestBody = async (
  input: RequestInfo | URL,
  init?: RequestInit
): Promise<Record<string, unknown>> =>
  JSON.parse(
    input instanceof Request ? await input.clone().text() : String(init?.body)
  ) as Record<string, unknown>

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
    manual_assistance_level_count: 11,
    active_curve: active(),
    servotronic: {
      effective_assistance: 0.5,
      last_command_reason: "auto",
      watchdog_timed_out: false,
      active_curve_source: null,
      active_curve_revision: null,
      active_curve_crc32: null,
      observed_speed_kph: null,
      speed_fresh: null,
      pwm_duty: null,
      inhibit_reason: null,
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

const settingsSlider = (name: string) =>
  document.querySelector(`input[aria-label="${name}"]`) as HTMLInputElement

const settingsAt = (
  revision: number,
  overrides: Partial<ApplicationSettingsResponse> = {}
): ApplicationSettingsResponse => ({
  ...DEFAULT_APPLICATION_SETTINGS,
  revision,
  updated_at: `2026-07-14T12:00:0${revision}.000000Z`,
  ...overrides,
})

const renderScreen = (
  children: ReactNode,
  options: {
    settings?: ApplicationSettingsResponse | null
    profiles?: SteeringProfileResponse[]
  } = {}
) => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  if (options.settings !== null) {
    client.setQueryData(
      getApplicationSettingsQueryKey(),
      options.settings ?? DEFAULT_APPLICATION_SETTINGS
    )
  }
  client.setQueryData(listSteeringProfilesQueryKey(), options.profiles ?? [])
  const savedProfile = options.profiles?.[0]
  if (savedProfile !== undefined) {
    client.setQueryData(getSavedSteeringProfileQueryKey(), savedProfile)
  }
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

it("masks all drive live observations after disconnect", () => {
  renderScreen(<CarDrive />)
  expect(screen.getAllByText("126").length).toBeGreaterThan(0)
  expect(screen.getAllByText("62").length).toBeGreaterThan(0)

  act(() => useLiveStore.getState().transportDisconnected())

  expect(screen.queryByText("126")).toBeNull()
  expect(screen.queryByText("62")).toBeNull()
  expect(screen.getAllByText("Unavailable").length).toBeGreaterThan(0)
})

it.each(["steering", "device"] as const)(
  "makes steering views unavailable for a %s adapter fault",
  (faultSource) => {
    renderScreen(<CarSteeringEditor />)
    expect(screen.getAllByText("50%")).toHaveLength(1)

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
    expect(screen.getAllByText("Controller fault")).toHaveLength(2)
  }
)

it("uses the shared thin steering editor and applies point changes immediately", async () => {
  const requests: Array<{ url: string; body: Record<string, unknown> }> = []
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const body = await requestBody(input, init)
      requests.push({ url: requestUrl(input), body })
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
  expect(screen.getByRole("switch", { name: "Auto" })).toBeTruthy()
  fireEvent.click(screen.getByRole("button", { name: "Drag draft point" }))
  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0]?.url).toMatch(/api\/steering\/curve$/)
  expect(requests[0]?.body).toEqual({
    definition: definition([1000, 800, 780, 670, 380, 0, 0, 0]),
  })
})

it("keeps the curve visible but disables controls while the controller is stale", () => {
  prepareLiveState()
  const current = useLiveStore.getState()
  current.applyDevices({
    protocol_version: 1,
    boot_id: "screens-boot",
    revision: 4,
    emitted_at: "2026-07-15T00:00:04Z",
    data: {
      ...current.devices,
      registry: {
        ...current.devices.registry,
        servotronic_controller: {
          ...current.devices.registry.servotronic_controller,
          status: "stale",
        },
      },
    },
  })
  renderScreen(<CarSteeringEditor />)

  expect(screen.getByText(/active 890 draft 890/)).toBeTruthy()
  expect(screen.getAllByText("Controller stale").length).toBeGreaterThan(0)
  expect(
    screen.getByRole("switch", { name: "Auto" }).hasAttribute("data-disabled")
  ).toBe(true)
  expect(
    (
      screen.getByRole("button", {
        name: "Increase assistance",
      }) as HTMLButtonElement
    ).disabled
  ).toBe(true)
})

it("edits settings only from authority and writes one canonical document per change", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => new Promise<Response>(() => {}))
  )
  const unavailable = renderScreen(<CarSettings />, { settings: null })
  expect(screen.getByText("Loading current settings…")).toBeTruthy()
  expect(screen.queryByRole("button", { name: "km/h" })).toBeNull()
  unavailable.unmount()

  const requests: Record<string, unknown>[] = []
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const body = await requestBody(input, init)
      requests.push(body)
      return jsonResponse(settingsAt(2, body))
    })
  )
  renderScreen(<CarSettings />)
  fireEvent.click(screen.getByRole("button", { name: "km/h" }))

  await waitFor(() =>
    expect(toastMock.success).toHaveBeenCalledWith("Settings saved")
  )
  expect(requests).toHaveLength(1)
  expect(requests[0]).toMatchObject({
    expected_revision: 1,
    speed_unit: "kmh",
    oil_operating_c: 110,
    oil_warning_c: 125,
    coolant_critical_c: 120,
    redline_rpm: 7200,
  })
  expect(Object.keys(requests[0] ?? {})).toHaveLength(12)
})

it("bounds a temperature slider by its neighbours and writes the released value", async () => {
  const requests: Record<string, unknown>[] = []
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const body = await requestBody(input, init)
      requests.push(body)
      return jsonResponse(settingsAt(2, body))
    })
  )
  renderScreen(<CarSettings />)
  fireEvent.click(screen.getByRole("tab", { name: "Temps" }))

  // The slider's thumb input is visually hidden, so it is addressed directly.
  const operating = settingsSlider("Oil operating temperature")
  expect(operating.getAttribute("aria-valuenow")).toBe("110")
  expect(operating.getAttribute("aria-valuetext")).toBe("110°C")
  expect(operating.min).toBe("60")
  expect(operating.max).toBe("124")

  fireEvent.change(operating, { target: { value: "118" } })
  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0]).toMatchObject({
    expected_revision: 1,
    oil_operating_c: 118,
    oil_warning_c: 125,
  })
  await waitFor(() =>
    expect(toastMock.success).toHaveBeenCalledWith("Settings saved")
  )
})

it("keeps theme and retry available after an initial settings load failure", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(jsonResponse({ detail: "unavailable" }, 503))
    .mockResolvedValueOnce(jsonResponse(settingsAt(2)))
  vi.stubGlobal("fetch", fetchMock)
  renderScreen(<CarSettings />, { settings: null })

  expect(
    await screen.findByText(
      "Current settings unavailable. Editing is disabled."
    )
  ).toBeTruthy()
  fireEvent.click(screen.getByRole("tab", { name: "System" }))
  fireEvent.click(await screen.findByRole("button", { name: "Dark" }))
  await waitFor(() =>
    expect(document.documentElement.classList.contains("dark")).toBe(true)
  )

  fireEvent.click(screen.getByRole("tab", { name: "Units" }))
  fireEvent.click(screen.getByRole("button", { name: "Retry settings" }))
  expect(await screen.findByRole("button", { name: "km/h" })).toBeTruthy()
  expect(fetchMock).toHaveBeenCalledTimes(2)
})

it("reloads the authoritative document when a write conflicts", async () => {
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) =>
      requestMethod(input, init) === "PUT"
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
        : jsonResponse(settingsAt(2, { speed_unit: "kmh" }))
  )
  vi.stubGlobal("fetch", fetchMock)
  renderScreen(<CarSettings />)
  fireEvent.click(screen.getByRole("button", { name: "km/h" }))

  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "km/h" }).getAttribute("aria-pressed")
    ).toBe("true")
  )
  expect(toastMock.error).toHaveBeenCalledWith(
    "Settings changed elsewhere — reloaded the latest"
  )
  expect(toastMock.success).not.toHaveBeenCalled()
})

it("shows observed device state as tiles in the devices group", () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => new Promise<Response>(() => {}))
  )
  renderScreen(<CarSettings />)
  fireEvent.click(screen.getByRole("tab", { name: "Devices" }))

  const devices = screen.getByRole("group", { name: "Device status" })
  expect(within(devices).getByText("Button pad")).toBeTruthy()
  expect(within(devices).getByText("Servotronic controller")).toBeTruthy()
  expect(within(devices).getAllByText("Active").length).toBe(2)
})
