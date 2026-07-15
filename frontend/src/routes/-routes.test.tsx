// @vitest-environment jsdom
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react"
import {
  RouterProvider,
  createMemoryHistory,
  createRouter,
} from "@tanstack/react-router"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { ThemeProvider } from "@/components/theme-provider"
import { routeTree } from "@/routeTree.gen"

vi.mock("@/components/simulator-workbench", async () => {
  const { SimulatorToolbar } =
    await import("@/components/simulator-workbench/components/simulator-toolbar")

  return {
    SimulatorWorkbench: () => (
      <div>
        <p>Existing simulator workbench</p>
        <SimulatorToolbar
          connectionState="connected"
          onReset={vi.fn()}
        />
      </div>
    ),
  }
})

const renderPath = async (path: string) => {
  const history = createMemoryHistory({ initialEntries: [path] })
  const router = createRouter({ routeTree, history, notFoundMode: "root" })
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  await router.load()

  return render(
    <QueryClientProvider client={queryClient}>
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

afterEach(() => {
  cleanup()
  localStorage.clear()
  document.documentElement.classList.remove("light", "dark")
  vi.clearAllMocks()
})

it("renders both choices at the root", async () => {
  await renderPath("/")

  expect(
    screen
      .getByRole("link", { name: /Development Workbench/ })
      .getAttribute("href")
  ).toBe("/dev")
  expect(
    screen.getByRole("link", { name: /Car Display/ }).getAttribute("href")
  ).toBe("/car")
})

it("renders the existing workbench with home and theme controls at /dev", async () => {
  await renderPath("/dev")

  expect(screen.getByText("Existing simulator workbench")).toBeTruthy()
  expect(
    screen
      .getByRole("link", { name: "Back to mode chooser" })
      .getAttribute("href")
  ).toBe("/")
  expect(
    screen.getByRole("button", { name: "Choose color theme" })
  ).toBeTruthy()
})

describe.each([
  ["/car", "Overview"],
  ["/car/drive", "Drive"],
  ["/car/steering", "Steering"],
  ["/car/settings", "Settings"],
])("car route %s", (path, heading) => {
  it("renders inside the isolated car layout with the correct active link", async () => {
    await renderPath(path)

    expect(screen.getByRole("heading", { name: heading })).toBeTruthy()
    const navigation = screen.getByRole("navigation", { name: "Car display" })
    const links = Array.from(navigation.querySelectorAll("a"))
    expect(links).toHaveLength(4)
    expect(links.map((link) => link.getAttribute("href"))).toEqual([
      "/car",
      "/car/drive",
      "/car/steering",
      "/car/settings",
    ])
    expect(
      screen.getByRole("link", { name: heading }).getAttribute("aria-current")
    ).toBe("page")
  })
})

it("offers only car-safe recovery for an unknown car route", async () => {
  await renderPath("/car/unknown")

  const links = screen.getAllByRole("link")
  expect(links).toHaveLength(1)
  expect(links[0]?.getAttribute("href")).toBe("/car")
  expect(screen.queryByText("Development workbench")).toBeNull()
  expect(screen.queryByText("Mode chooser")).toBeNull()
})

it("offers chooser and development recovery for other unknown routes", async () => {
  await renderPath("/unknown")

  expect(
    screen.getByRole("link", { name: "Mode chooser" }).getAttribute("href")
  ).toBe("/")
  expect(
    screen
      .getByRole("link", { name: "Development workbench" })
      .getAttribute("href")
  ).toBe("/dev")
})

it("applies and persists a theme selected from the dev toolbar", async () => {
  await renderPath("/dev")

  fireEvent.click(screen.getByRole("button", { name: "Choose color theme" }))
  fireEvent.click(await screen.findByRole("menuitemradio", { name: "Dark" }))

  await waitFor(() => {
    expect(document.documentElement.classList.contains("dark")).toBe(true)
  })
  expect(localStorage.getItem("theme")).toBe("dark")
})
