// @vitest-environment jsdom
import type { ReactNode } from "react"
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import type { SteeringProfileResponse } from "@/api/http/types.gen"
import type {
  ActiveSteeringCurveState,
  SteeringCurveDefinition,
} from "@/api/live-contract.gen"
import { SteeringCurveCard } from "@/components/simulator-workbench/components/steering-curve-card"

vi.mock("./components/curve-chart", () => ({
  CurveChart: ({
    onPointChange,
    onPointCommit,
    activeAssistance,
  }: {
    onPointChange: (index: number, value: number) => void
    onPointCommit: (index: number) => void
    activeAssistance?: number | null
  }) => (
    <button
      data-active-assistance={activeAssistance ?? "none"}
      onClick={() => {
        onPointChange(1, 800)
        onPointCommit(1)
      }}
    >
      Simulate point drag
    </button>
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

const active = (
  value = definition(),
  revision = 1,
  savedProfile: SteeringProfileResponse | null = null
): ActiveSteeringCurveState => ({
  definition: value as SteeringProfileResponse["definition"],
  fingerprint: `fingerprint-${revision}`,
  activation_revision: revision,
  status: "active",
  saved_profile_id: savedProfile?.profile_id ?? null,
  saved_profile_revision: savedProfile?.revision ?? null,
})

const profile = (
  value = definition(),
  revision = 1
): SteeringProfileResponse => ({
  profile_id: "11111111-1111-4111-8111-111111111111",
  name: "Dry track",
  revision,
  definition: value as SteeringProfileResponse["definition"],
  created_at: "2026-07-14T00:00:00.000000Z",
  updated_at: "2026-07-14T00:00:00.000000Z",
})

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  })

const commandResponse = () =>
  jsonResponse({ accepted: true, boot_id: "test-boot", revision: 2 })

const requestUrl = (input: RequestInfo | URL) =>
  input instanceof Request ? input.url : String(input)

const requestMethod = (input: RequestInfo | URL, init?: RequestInit) =>
  input instanceof Request ? input.method : (init?.method ?? "GET")

const requestBody = async <Body,>(
  input: RequestInfo | URL,
  init?: RequestInit
): Promise<Body> =>
  JSON.parse(
    input instanceof Request ? await input.clone().text() : String(init?.body)
  ) as Body

const renderEditor = (
  activeCurve: ActiveSteeringCurveState,
  speedKph: number | null = 10,
  activeAssistance: number | null = null,
  steering: {
    mode?: "auto" | "manual"
    manualAssistanceLevel?: number
    maximumAssistanceActive?: boolean
  } = {}
) => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  const result = render(
    <SteeringCurveCard
      activeCurve={activeCurve}
      mode={steering.mode ?? "auto"}
      manualAssistanceLevel={steering.manualAssistanceLevel ?? 0}
      manualAssistanceLevelCount={11}
      maximumAssistanceActive={steering.maximumAssistanceActive ?? false}
      speedKph={speedKph}
      activeAssistance={activeAssistance}
    />,
    { wrapper: Wrapper }
  )
  return { ...result, client }
}

beforeEach(() => {
  vi.restoreAllMocks()
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("SteeringCurveEditor", () => {
  it("keeps current manual assistance on the chart without a speed sample", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse([]))
    )

    renderEditor(active(), null, 3 / 7)

    expect(
      screen
        .getByText("Simulate point drag")
        .getAttribute("data-active-assistance")
    ).toBe(String(3 / 7))
  })

  it("maps the up and max controls to the button-pad command semantics", async () => {
    const requests: Array<{ url: string; body: unknown }> = []
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = requestUrl(input)
        if (url.endsWith("/api/steering/profile")) return jsonResponse([])
        requests.push({ url, body: await requestBody(input, init) })
        return commandResponse()
      })
    )
    renderEditor(active())

    fireEvent.click(screen.getByRole("button", { name: "Increase assistance" }))
    await waitFor(() => expect(requests).toHaveLength(1))
    expect(requests[0]).toMatchObject({
      url: expect.stringMatching(/api\/commands\/manual-assistance-adjustment$/),
      body: { delta: 1 },
    })

    fireEvent.click(screen.getByRole("button", { name: "Max" }))
    await waitFor(() => expect(requests).toHaveLength(2))
    expect(requests[1]).toMatchObject({
      url: expect.stringMatching(/api\/commands\/maximum-assistance$/),
      body: { enabled: true },
    })
  })

  it("uses a relative down command while Max masks the remembered manual level", async () => {
    const requests: Array<{ url: string; body: unknown }> = []
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = requestUrl(input)
        if (url.endsWith("/api/steering/profile")) return jsonResponse([])
        requests.push({ url, body: await requestBody(input, init) })
        return commandResponse()
      })
    )
    renderEditor(active(), 10, 1, {
      mode: "manual",
      manualAssistanceLevel: 0,
      maximumAssistanceActive: true,
    })

    const decrease = screen.getByRole("button", {
      name: "Decrease assistance",
    }) as HTMLButtonElement
    expect(decrease.disabled).toBe(false)
    fireEvent.click(decrease)

    await waitFor(() => expect(requests).toHaveLength(1))
    expect(requests[0]).toMatchObject({
      url: expect.stringMatching(/api\/commands\/manual-assistance-adjustment$/),
      body: { delta: -1 },
    })
  })

  it("disables decrease at zero in normal Manual mode", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse([]))
    )
    renderEditor(active(), 10, 0, {
      mode: "manual",
      manualAssistanceLevel: 0,
      maximumAssistanceActive: false,
    })

    const decrease = screen.getByRole("button", {
      name: "Decrease assistance",
    }) as HTMLButtonElement
    expect(decrease.disabled).toBe(true)
  })

  it("always presents a smooth curve without an interpolation control", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse([]))
    )
    renderEditor(active(definition([1000, 800, 780, 670, 380, 0, 0, 0]), 2))
    expect(await screen.findByText(/smooth assistance/)).toBeTruthy()
    expect(
      screen.queryByRole("button", {
        name: /linear|convert|smooth unavailable/i,
      })
    ).toBeNull()
  })

  it("auto-applies on drag release without triggering a save", async () => {
    const saved = profile()
    const requests: Array<{ url: string; method: string }> = []
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = requestUrl(input)
        const method = requestMethod(input, init)
        requests.push({ url, method })
        if (url.endsWith("/api/steering/profile") && method === "GET") {
          return jsonResponse(saved)
        }
        if (url.endsWith("/api/commands/steering-curve")) {
          return commandResponse()
        }
        throw new Error(`Unexpected request: ${method} ${url}`)
      })
    )

    renderEditor(active())
    fireEvent.click(screen.getByText("Simulate point drag"))

    await waitFor(() =>
      expect(
        requests.filter((r) => r.url.includes("/api/commands/"))
      ).toHaveLength(1)
    )
    expect(
      requests.filter(
        (r) => r.method === "PUT" && r.url.includes("/api/steering/profiles")
      )
    ).toHaveLength(0)
  })

  it("Save button updates the saved profile and Reset reactivates it", async () => {
    const saved = profile()
    const requests: Array<{ url: string; method: string; body?: unknown }> = []
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = requestUrl(input)
        const method = requestMethod(input, init)
        if (url.endsWith("/api/steering/profile") && method === "GET") {
          return jsonResponse(saved)
        }
        if (url.endsWith("/api/commands/steering-curve")) {
          requests.push({ url, method })
          return commandResponse()
        }
        if (method === "PUT" && url.includes(saved.profile_id)) {
          const body = await requestBody(input, init)
          requests.push({ url, method, body })
          return jsonResponse({ ...saved, revision: 2 })
        }
        if (url.endsWith("/api/commands/activate-steering-profile")) {
          requests.push({ url, method })
          return commandResponse()
        }
        throw new Error(`Unexpected request: ${method} ${url}`)
      })
    )

    renderEditor(active(definition([1000, 800, 780, 670, 380, 0, 0, 0]), 2))
    await waitFor(() =>
      expect(
        (screen.getByRole("button", { name: "Save" }) as HTMLButtonElement)
          .disabled
      ).toBe(false)
    )

    // The active in-memory curve differs from the saved profile.
    expect(
      (screen.getByRole("button", { name: "Save" }) as HTMLButtonElement)
        .disabled
    ).toBe(false)
    expect(
      (screen.getByRole("button", { name: "Reset" }) as HTMLButtonElement)
        .disabled
    ).toBe(false)

    fireEvent.click(screen.getByText("Simulate point drag"))
    await waitFor(() =>
      expect(
        (screen.getByRole("button", { name: "Save" }) as HTMLButtonElement)
          .disabled
      ).toBe(false)
    )
    expect(
      (screen.getByRole("button", { name: "Reset" }) as HTMLButtonElement)
        .disabled
    ).toBe(false)

    // Save writes the draft to the profile
    fireEvent.click(screen.getByRole("button", { name: "Save" }))
    await waitFor(() =>
      expect(requests.some((r) => r.method === "PUT")).toBe(true)
    )

    // Reset activates the saved profile
    fireEvent.click(screen.getByText("Simulate point drag"))
    await waitFor(() =>
      expect(
        (screen.getByRole("button", { name: "Reset" }) as HTMLButtonElement)
          .disabled
      ).toBe(false)
    )
    fireEvent.click(screen.getByRole("button", { name: "Reset" }))
    await waitFor(() =>
      expect(
        requests.some((r) => r.url.includes("activate-steering-profile"))
      ).toBe(true)
    )
  })

  it("prevents duplicate activate requests when drag releases fire in quick succession", async () => {
    let resolveActivation: ((response: Response) => void) | undefined
    const activation = new Promise<Response>((resolve) => {
      resolveActivation = resolve
    })
    const fetchMock = vi.fn(async (input: RequestInfo | URL) =>
      requestUrl(input).endsWith("/api/steering/profile")
        ? jsonResponse([])
        : activation
    )
    vi.stubGlobal("fetch", fetchMock)

    renderEditor(active())
    const dragButton = screen.getByText("Simulate point drag")
    fireEvent.click(dragButton)
    fireEvent.click(dragButton)

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.filter(([input]) =>
          requestUrl(input).includes("/api/commands/")
        )
      ).toHaveLength(1)
    )
    resolveActivation?.(commandResponse())
  })
})
