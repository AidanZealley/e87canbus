// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react"
import {
  RouterProvider,
  createMemoryHistory,
  createRouter,
} from "@tanstack/react-router"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { ThemeProvider } from "@/components/theme-provider"
import { routeTree } from "@/routeTree.gen"

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
  window.scrollTo = vi.fn()
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: vi.fn().mockReturnValue({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  })
})

afterEach(cleanup)

describe.each([
  ["/", "Drive"],
  ["/steering", "Steering"],
  ["/buttons", "Buttons"],
  ["/settings", "Settings"],
])("console route %s", (path, heading) => {
  it("renders in the existing driver layout with root-relative navigation", async () => {
    await renderPath(path)
    expect(screen.getByRole("heading", { name: heading })).toBeTruthy()
    const links = Array.from(
      screen.getByRole("navigation", { name: "Car display" }).querySelectorAll("a")
    )
    expect(links.map((link) => link.getAttribute("href"))).toEqual([
      "/",
      "/steering",
      "/buttons",
      "/settings",
    ])
  })
})

it("offers only console recovery for an unknown route", async () => {
  await renderPath("/unknown")
  expect(screen.getByRole("link", { name: "Return to drive" }).getAttribute("href")).toBe("/")
  expect(screen.queryByText("Development workbench")).toBeNull()
})
