// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { afterEach, expect, it, vi } from "vitest"

import { SimulatorWorkbench } from "./SimulatorWorkbench"

vi.mock("@/components/button-profile-editor", () => ({
  ButtonProfileEditor: () => <div>Button profile editor</div>,
}))
vi.mock("./components/simulator-toolbar", () => ({
  SimulatorToolbar: () => <div>Toolbar</div>,
}))
vi.mock("./SimulatorCoordinatorPanel", () => ({
  SimulatorCoordinatorPanel: () => <div>Coordinator panel controls</div>,
}))

afterEach(cleanup)

it("renders the remaining coordinator and button-profile controls", () => {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <SimulatorWorkbench />
    </QueryClientProvider>
  )

  expect(screen.getByText("Coordinator panel controls")).toBeTruthy()
  expect(screen.getByText("Button profile editor")).toBeTruthy()
  expect(screen.queryByText(/CAN network topology/i)).toBeNull()
  expect(screen.queryByText(/CAN trace/i)).toBeNull()
})
