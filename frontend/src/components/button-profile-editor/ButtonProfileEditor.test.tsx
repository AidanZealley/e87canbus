// @vitest-environment jsdom
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { afterEach, expect, it, vi } from "vitest"

import type { ButtonProfileResponse } from "@/api/http"

const mocks = vi.hoisted(() => ({
  update: vi.fn(),
  activate: vi.fn(),
  profile: null as ButtonProfileResponse | null,
}))

vi.mock("@tanstack/react-query", async (importOriginal) => {
  const original =
    await importOriginal<typeof import("@tanstack/react-query")>()
  return {
    ...original,
    useQuery: () => ({
      data: mocks.profile,
      error: null,
      isError: false,
      isPending: false,
      refetch: vi.fn(),
    }),
  }
})

vi.mock("@/api/http/@tanstack/react-query.gen", () => ({
  getSavedButtonProfileQueryKey: () => ["saved-button-profile"],
  getSavedButtonProfileOptions: () => ({
    queryKey: ["saved-button-profile"],
    queryFn: vi.fn(),
    staleTime: Number.POSITIVE_INFINITY,
  }),
  updateButtonProfileMutation: () => ({ mutationFn: mocks.update }),
  activateButtonProfileMutation: () => ({ mutationFn: mocks.activate }),
}))

import { ButtonProfileEditor } from "./ButtonProfileEditor"

const profile = (revision: number, level: number): ButtonProfileResponse =>
  ({
    profile_id: "profile-1",
    name: "My buttons",
    revision,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    definition: {
      schema_version: 1,
      slots: [
        { type: "set_manual_assistance_level", level },
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
      ],
    },
  }) as ButtonProfileResponse

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

it("renders a newer saved revision when the profile changes", async () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  mocks.profile = profile(1, 2)
  const view = render(
    <QueryClientProvider client={queryClient}>
      <ButtonProfileEditor profile={mocks.profile!} />
    </QueryClientProvider>
  )
  expect(
    await screen.findByRole("button", { name: "Edit button 0: Assist 2" })
  ).toBeTruthy()

  act(() => {
    view.rerender(
      <QueryClientProvider client={queryClient}>
        <ButtonProfileEditor profile={profile(2, 7)} />
      </QueryClientProvider>
    )
  })

  expect(
    await screen.findByRole("button", { name: "Edit button 0: Assist 7" })
  ).toBeTruthy()
  expect(screen.queryByText("Saved profile changed")).toBeNull()
})

it("commits a binding as soon as it is applied", async () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  mocks.profile = profile(1, 2)
  mocks.update.mockResolvedValue(profile(2, 5))
  render(
    <QueryClientProvider client={queryClient}>
      <ButtonProfileEditor profile={mocks.profile!} />
    </QueryClientProvider>
  )

  fireEvent.click(
    await screen.findByRole("button", { name: "Edit button 0: Assist 2" })
  )
  fireEvent.change(screen.getByLabelText("Level"), {
    target: { value: "5" },
  })
  fireEvent.click(screen.getByRole("button", { name: "Apply binding" }))

  await waitFor(() => {
    expect(mocks.update.mock.calls[0]?.[0]).toEqual({
      path: { profile_id: "profile-1" },
      body: {
        name: "My buttons",
        expected_revision: 1,
        definition: {
          schema_version: 1,
          slots: [
            { type: "set_manual_assistance_level", level: 5 },
            null,
            null,
            null,
            null,
            null,
            null,
            null,
            null,
            null,
            null,
            null,
            null,
            null,
            null,
            null,
          ],
        },
      },
    })
  })
  expect(screen.queryByRole("button", { name: "Save profile" })).toBeNull()
  expect(screen.queryByRole("button", { name: "Discard changes" })).toBeNull()
})
