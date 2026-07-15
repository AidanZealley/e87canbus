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

import type {
  ActiveSteeringCurve,
  SteeringCurveDefinition,
  StoredSteeringProfile,
} from "@/api/steering"
import { steeringProfilesQueryKey } from "@/api/steering"
import { SteeringCurveCard } from "@/components/simulator-workbench/components/steering-curve-card"

vi.mock("./components/curve-chart", () => ({
  CurveChart: ({
    onPointChange,
  }: {
    onPointChange: (index: number, value: number) => void
  }) => (
    <button onClick={() => onPointChange(1, 800)}>Simulate point drag</button>
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

const active = (
  value = definition(),
  revision = 1,
  profile: StoredSteeringProfile | null = null
): ActiveSteeringCurve => ({
  definition: value,
  fingerprint: `fingerprint-${revision}`,
  activation_revision: revision,
  status: "active",
  saved_profile_id: profile?.profile_id ?? null,
  saved_profile_revision: profile?.revision ?? null,
  supported_interpolations: ["linear-v1", "monotone-cubic-v1"],
})

const profile = (
  value = definition(),
  revision = 1
): StoredSteeringProfile => ({
  profile_id: "11111111-1111-4111-8111-111111111111",
  name: "Dry track",
  revision,
  definition: value,
  created_at: "2026-07-14T00:00:00.000000Z",
  updated_at: "2026-07-14T00:00:00.000000Z",
})

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  })

const renderEditor = (
  activeCurve: ActiveSteeringCurve,
  speedKph: number | null = 10
) => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  const result = render(
    <SteeringCurveCard activeCurve={activeCurve} speedKph={speedKph} />,
    { wrapper: Wrapper }
  )
  return { ...result, client }
}

const savedProfileSelect = () =>
  screen.getByRole("combobox", { name: "Saved profile" })

const waitForSelectedProfile = async (name: string) => {
  await waitFor(() => expect(savedProfileSelect().textContent).toContain(name))
}

const chooseProfile = async (name: string) => {
  fireEvent.click(savedProfileSelect())
  const option = await screen.findByRole("option", { name })
  fireEvent.pointerDown(option, { button: 0, pointerType: "mouse" })
  fireEvent.click(option)
}

beforeEach(() => {
  vi.restoreAllMocks()
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("SteeringCurveEditor", () => {
  it("converts a linear draft and explicitly applies the smooth definition", async () => {
    const requests: Array<{
      url: string
      method: string
      definition?: SteeringCurveDefinition
    }> = []
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        const method = init?.method ?? "GET"
        if (method === "GET") return jsonResponse({ profiles: [] })
        const body = JSON.parse(String(init?.body)) as {
          definition: SteeringCurveDefinition
        }
        requests.push({ url, method, definition: body.definition })
        if (url.endsWith("/api/commands/steering-curve")) {
          return commandResponse()
        }
        throw new Error(`Unexpected request: ${method} ${url}`)
      })
    )

    renderEditor(active())
    fireEvent.click(
      await screen.findByRole("button", { name: "Convert draft to smooth" })
    )
    fireEvent.click(screen.getByRole("button", { name: "Apply draft" }))

    await waitFor(() => expect(requests).toHaveLength(1))
    expect(screen.getByText("Active · r1")).toBeTruthy()
    expect(screen.getByText("Draft changed")).toBeTruthy()
    expect(
      screen.getByRole("button", { name: "Use linear draft" })
    ).toBeTruthy()
    expect(requests).toHaveLength(1)
    expect(requests[0]?.url).toMatch(/\/api\/commands\/steering-curve$/)
    expect(requests[0]?.definition?.interpolation).toBe("monotone-cubic-v1")
    expect(
      requests.some((request) => request.url.endsWith("/steering/profiles"))
    ).toBe(false)
  })

  it("disables smooth conversion when the active consumer advertises linear only", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ profiles: [] }))
    )
    const linearOnly = {
      ...active(),
      supported_interpolations: ["linear-v1" as const],
    }

    renderEditor(linearOnly)

    const conversion = await screen.findByRole("button", {
      name: "Smooth unavailable",
    })
    expect((conversion as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByText("Draft matches active")).toBeTruthy()
  })

  it("converts only the draft and saves smooth interpolation as an explicit profile", async () => {
    const requests: Array<{
      url: string
      method: string
      definition?: SteeringCurveDefinition
    }> = []
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        const method = init?.method ?? "GET"
        if (method === "GET") return jsonResponse({ profiles: [] })
        const body = JSON.parse(String(init?.body)) as {
          name: string
          definition: SteeringCurveDefinition
        }
        requests.push({ url, method, definition: body.definition })
        if (method === "POST" && url.endsWith("/api/steering/profiles")) {
          return jsonResponse(
            { ...profile(body.definition), name: body.name },
            201
          )
        }
        throw new Error(`Unexpected request: ${method} ${url}`)
      })
    )

    renderEditor(active())
    fireEvent.click(
      await screen.findByRole("button", { name: "Convert draft to smooth" })
    )

    expect(screen.getByText(/monotone-cubic-v1/)).toBeTruthy()
    expect(screen.getByText("Draft changed")).toBeTruthy()
    expect(requests).toHaveLength(0)

    fireEvent.change(
      screen.getByRole("textbox", { name: "New profile name" }),
      { target: { value: "Smooth track" } }
    )
    fireEvent.click(screen.getByRole("button", { name: "Save as" }))

    await waitFor(() => expect(requests).toHaveLength(1))
    expect(requests[0]?.definition?.interpolation).toBe("monotone-cubic-v1")
    expect(
      requests.some((request) => request.url.includes("/api/commands/"))
    ).toBe(false)
  })

  it("keeps Apply and Save as separate operations and evaluates active separately", async () => {
    const saved = profile()
    const requests: Array<{ url: string; method: string }> = []
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        const method = init?.method ?? "GET"
        requests.push({ url, method })
        if (url.endsWith("/api/steering/profiles") && method === "GET") {
          return jsonResponse({ profiles: [saved] })
        }
        if (url.endsWith("/api/commands/steering-curve")) {
          return commandResponse()
        }
        if (url.includes(`/api/steering/profiles/${saved.profile_id}`)) {
          const request = JSON.parse(String(init?.body)) as {
            definition: SteeringCurveDefinition
          }
          return jsonResponse({
            ...saved,
            revision: 2,
            definition: request.definition,
          })
        }
        throw new Error(`Unexpected request: ${method} ${url}`)
      })
    )

    const { client } = renderEditor(active())
    await waitFor(() =>
      expect(client.getQueryState(steeringProfilesQueryKey)?.status).toBe(
        "success"
      )
    )
    fireEvent.click(screen.getByText("Simulate point drag"))
    expect(screen.getByText(/active 89.0%/)).toBeTruthy()
    expect(screen.getByText(/draft preview 80.0%/)).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: "Apply draft" }))

    await waitFor(() =>
      expect(
        requests.filter((request) => request.url.includes("/api/commands/"))
      ).toHaveLength(1)
    )
    expect(
      requests.filter(
        (request) =>
          request.method === "POST" && request.url.endsWith("/profiles")
      )
    ).toHaveLength(0)

    await chooseProfile("Dry track · r1")
    fireEvent.change(
      screen.getByRole("spinbutton", { name: "Assistance at 20 km/h" }),
      { target: { value: "70" } }
    )
    fireEvent.click(screen.getByRole("button", { name: "Save revision" }))

    await waitFor(() =>
      expect(
        requests.filter((request) => request.method === "PUT")
      ).toHaveLength(1)
    )
    expect(
      requests.filter((request) => request.url.includes("/api/commands/"))
    ).toHaveLength(1)
  })

  it("preserves a dirty draft when active state changes externally", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ profiles: [] }))
    )
    const initial = active()
    const { rerender } = renderEditor(initial)
    fireEvent.click(screen.getByText("Simulate point drag"))

    const externalDefinition = definition([1000, 850, 780, 670, 380, 0, 0, 0])
    rerender(
      <SteeringCurveCard
        activeCurve={active(externalDefinition, 2)}
        speedKph={10}
      />
    )

    expect(
      (
        screen.getByRole("spinbutton", {
          name: "Assistance at 10 km/h",
        }) as HTMLInputElement
      ).value
    ).toBe("80")
    expect(await screen.findByText("Active changed externally")).toBeTruthy()
  })

  it("retains a draft on revision conflict and offers the refreshed saved values", async () => {
    const original = profile()
    const refreshed = profile(
      definition([1000, 890, 700, 670, 380, 0, 0, 0]),
      2
    )
    let listCount = 0
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        const method = init?.method ?? "GET"
        if (url.endsWith("/api/steering/profiles") && method === "GET") {
          listCount += 1
          return jsonResponse({
            profiles: [listCount === 1 ? original : refreshed],
          })
        }
        if (method === "PUT") {
          return jsonResponse(
            {
              error: {
                code: "profile_revision_conflict",
                message: "profile is now at revision 2",
                current_revision: 2,
              },
            },
            409
          )
        }
        throw new Error(`Unexpected request: ${method} ${url}`)
      })
    )

    renderEditor(active(original.definition, 1, original))
    await waitForSelectedProfile("Dry track · r1")
    fireEvent.change(
      screen.getByRole("spinbutton", { name: "Assistance at 20 km/h" }),
      { target: { value: "80" } }
    )
    fireEvent.click(screen.getByRole("button", { name: "Save revision" }))

    expect(await screen.findByText("Saved revision conflict")).toBeTruthy()
    expect(
      (
        screen.getByRole("spinbutton", {
          name: "Assistance at 20 km/h",
        }) as HTMLInputElement
      ).value
    ).toBe("80")
    await waitForSelectedProfile("Dry track · r2")
    fireEvent.click(screen.getByRole("button", { name: "Load saved" }))
    expect(
      (
        screen.getByRole("spinbutton", {
          name: "Assistance at 20 km/h",
        }) as HTMLInputElement
      ).value
    ).toBe("70")
  })

  it("prevents duplicate Apply requests while the first action is pending", async () => {
    let resolveActivation: ((response: Response) => void) | undefined
    const activation = new Promise<Response>((resolve) => {
      resolveActivation = resolve
    })
    const fetchMock = vi.fn(async (input: RequestInfo | URL) =>
      String(input).endsWith("/api/steering/profiles")
        ? jsonResponse({ profiles: [] })
        : activation
    )
    vi.stubGlobal("fetch", fetchMock)

    const { client } = renderEditor(active())
    await waitFor(() =>
      expect(client.getQueryState(steeringProfilesQueryKey)?.status).toBe(
        "success"
      )
    )
    fireEvent.click(screen.getByText("Simulate point drag"))
    const apply = screen.getByRole("button", { name: "Apply draft" })
    fireEvent.click(apply)
    fireEvent.click(apply)

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.filter(([input]) =>
          String(input).includes("/api/commands/")
        )
      ).toHaveLength(1)
    )
    resolveActivation?.(commandResponse())
    await waitFor(() => expect(screen.queryByText("Applying…")).toBeNull())
  })

  it("saves as, reverts with confirmation, and deletes with the committed revision", async () => {
    const created = profile(definition([1000, 800, 780, 670, 380, 0, 0, 0]))
    const requests: Array<{ url: string; method: string }> = []
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        const method = init?.method ?? "GET"
        requests.push({ url, method })
        if (url.endsWith("/api/steering/profiles") && method === "GET") {
          return jsonResponse({ profiles: [] })
        }
        if (url.endsWith("/api/steering/profiles") && method === "POST") {
          return jsonResponse(created, 201)
        }
        if (method === "DELETE") return new Response(null, { status: 204 })
        throw new Error(`Unexpected request: ${method} ${url}`)
      })
    )

    const { client: saveAsClient } = renderEditor(active())
    await waitFor(() =>
      expect(saveAsClient.getQueryState(steeringProfilesQueryKey)?.status).toBe(
        "success"
      )
    )
    fireEvent.click(screen.getByText("Simulate point drag"))
    fireEvent.change(
      screen.getByRole("textbox", { name: "New profile name" }),
      {
        target: { value: "Dry track" },
      }
    )
    fireEvent.click(screen.getByRole("button", { name: "Save as" }))
    await waitForSelectedProfile("Dry track · r1")

    fireEvent.click(screen.getByRole("button", { name: "Reload active" }))
    expect(
      screen.getByRole("alertdialog", { name: "Reload active values?" })
    ).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: "Reload" }))
    expect(
      (
        screen.getByRole("spinbutton", {
          name: "Assistance at 10 km/h",
        }) as HTMLInputElement
      ).value
    ).toBe("89")

    fireEvent.click(screen.getByRole("button", { name: "Delete saved" }))
    expect(
      screen.getByRole("alertdialog", { name: "Delete saved profile?" })
    ).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: "Delete" }))
    await waitForSelectedProfile("No saved selection")
    expect(
      requests.some(
        (request) =>
          request.method === "DELETE" &&
          request.url.endsWith(
            `/api/steering/profiles/${created.profile_id}?expected_revision=1`
          )
      )
    ).toBe(true)
    expect(
      requests.filter((request) => request.url.includes("/api/commands/"))
    ).toHaveLength(0)
  })

  it("delete confirmation identifies and deletes the selected profile", async () => {
    const first = profile()
    const second: StoredSteeringProfile = {
      ...profile(),
      profile_id: "22222222-2222-4222-8222-222222222222",
      name: "Wet track",
    }
    const requests: Array<{ url: string; method: string }> = []
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        const method = init?.method ?? "GET"
        requests.push({ url, method })
        if (method === "GET") {
          return jsonResponse({ profiles: [first, second] })
        }
        if (method === "DELETE") return new Response(null, { status: 204 })
        throw new Error(`Unexpected request: ${method} ${url}`)
      })
    )

    renderEditor(active(first.definition, 1, first))
    await waitForSelectedProfile("Dry track · r1")
    fireEvent.click(screen.getByRole("button", { name: "Delete saved" }))
    expect(
      screen.getByText(
        "This will permanently delete Dry track. This action cannot be undone."
      )
    ).toBeTruthy()

    fireEvent.click(screen.getByRole("button", { name: "Delete" }))

    await waitFor(() =>
      expect(
        requests.some(
          (request) =>
            request.method === "DELETE" &&
            request.url.endsWith(
              `/api/steering/profiles/${first.profile_id}?expected_revision=1`
            )
        )
      ).toBe(true)
    )
    expect(
      requests.some(
        (request) =>
          request.method === "DELETE" && request.url.includes(second.profile_id)
      )
    ).toBe(false)
    expect(savedProfileSelect().textContent).toContain("No saved selection")
  })
})

const commandResponse = () =>
  jsonResponse({ accepted: true, boot_id: "test-boot", revision: 2 })
