// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react"
import {
  RouterProvider,
  createMemoryHistory,
  createRouter,
} from "@tanstack/react-router"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { afterEach, beforeEach, expect, it, vi } from "vitest"

import { ThemeProvider } from "@/components/theme-provider"
import { routeTree } from "@/routeTree.gen"

vi.mock("@/components/simulator-workbench", () => ({
  SimulatorWorkbench: () => <p>Existing simulator workbench</p>,
}))

const renderPath = async (path: string) => {
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: [path] }),
    notFoundMode: "root",
  })
  await router.load()
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <ThemeProvider disableTransitionOnChange={false}>
        <RouterProvider router={router} />
      </ThemeProvider>
    </QueryClientProvider>
  )
}

beforeEach(() => {
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
  vi.clearAllMocks()
})

it("roots the coordinator app in the existing workbench", async () => {
  await renderPath("/")
  expect(screen.getByText("Existing simulator workbench")).toBeTruthy()
  expect(screen.queryByText("Car Display")).toBeNull()
})

it("recovers unknown routes to the workbench", async () => {
  await renderPath("/unknown")
  expect(
    screen.getByRole("link", { name: "Development workbench" }).getAttribute("href")
  ).toBe("/")
})
