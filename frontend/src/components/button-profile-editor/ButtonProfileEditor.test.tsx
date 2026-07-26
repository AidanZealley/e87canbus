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
  profile: null as ButtonProfileResponse | null,
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
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
}))

vi.mock("sonner", () => ({
  toast: {
    error: mocks.toastError,
    success: mocks.toastSuccess,
  },
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
      slots: [
        {
          command: { type: "set_manual_assistance_level", level },
          colour: [12, 34, 56],
          active_colour: null,
          animation: {
            kind: "breathe",
            period_ms: 2000,
            minimum: 8,
            maximum: 255,
          },
        },
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
    await screen.findByRole("button", {
      name: "Configure button 0: Assist 2",
    })
  ).toBeTruthy()

  act(() => {
    view.rerender(
      <QueryClientProvider client={queryClient}>
        <ButtonProfileEditor profile={profile(2, 7)} />
      </QueryClientProvider>
    )
  })

  expect(
    await screen.findByRole("button", {
      name: "Configure button 0: Assist 7",
    })
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
    await screen.findByRole("button", {
      name: "Configure button 0: Assist 2",
    })
  )
  fireEvent.change(screen.getByLabelText("Level"), {
    target: { value: "5" },
  })
  fireEvent.blur(screen.getByLabelText("Level"))

  await waitFor(() => {
    expect(mocks.update.mock.calls[0]?.[0]).toEqual({
      path: { profile_id: "profile-1" },
      body: {
        name: "My buttons",
        expected_revision: 1,
        definition: {
          slots: [
            {
              command: {
                type: "set_manual_assistance_level",
                level: 5,
              },
              colour: [12, 34, 56],
              active_colour: null,
              animation: {
                kind: "breathe",
                period_ms: 2000,
                minimum: 8,
                maximum: 255,
              },
            },
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

it("surfaces revision conflicts through the existing error detail", async () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  mocks.profile = profile(1, 2)
  mocks.update.mockRejectedValue({
    body: {
      error: {
        code: "button_profile_revision_conflict",
        message: "Button profile is at revision 2, not 1",
        current_revision: 2,
      },
    },
  })
  render(
    <QueryClientProvider client={queryClient}>
      <ButtonProfileEditor profile={mocks.profile!} />
    </QueryClientProvider>
  )

  fireEvent.click(await screen.findByRole("button", { name: "Clear button 0" }))

  await waitFor(() => {
    expect(mocks.toastError).toHaveBeenCalledWith(
      "Button profile is at revision 2, not 1"
    )
  })
})
