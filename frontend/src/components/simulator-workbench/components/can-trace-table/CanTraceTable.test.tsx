// @vitest-environment jsdom
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react"
import { afterEach, beforeEach, expect, it, vi } from "vitest"

import type { DevicesState, TraceRow } from "@/api/live-contract.gen"

type CanTraceEntry = TraceRow
type NetworkStatus = DevicesState["networks"][number]
import { CanTraceTable } from "./CanTraceTable"

const networks: NetworkStatus[] = [
  {
    id: "fcan",
    label: "F-CAN",
    interface: "can2",
    bitrate: 500_000,
    connected: true,
    nodes: ["simulated-vehicle"],
  },
]

const frame = (sequence: number): CanTraceEntry => ({
  type: "frame",
  session_id: 1,
  sequence,
  network: "fcan",
  source: "simulated-vehicle",
  arbitration_id: 0x1fffff00,
  arbitration_id_hex: "0x1fffff00",
  data_hex: "0000",
  is_extended_id: true,
  monotonic_s: sequence,
})

beforeEach(() => {
  HTMLElement.prototype.scrollTo = vi.fn()
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

it("renders only a bounded virtual window for a full trace", async () => {
  const trace = Array.from({ length: 2_000 }, (_, index) => frame(index + 1))

  render(
    <CanTraceTable
      trace={trace}
      totalCount={trace.length}
      networks={networks}
      selectedNetworks={new Set(["fcan"])}
      selected={null}
      onSelect={vi.fn()}
      onToggleNetwork={vi.fn()}
    />
  )

  await waitFor(() => {
    expect(screen.getAllByRole("row").length).toBeLessThan(40)
  })
  expect(screen.getByText("2000 frames captured")).toBeTruthy()
  expect(document.querySelector("[data-state='selected']")).toBeNull()
  expect(
    document.querySelector<HTMLTableSectionElement>("[data-slot='table-body']")
      ?.className
  ).toContain("[&_td]:h-8")
  expect(
    document.querySelector<HTMLButtonElement>(
      "button[aria-label='Jump to latest CAN frame']"
    )?.className
  ).toContain("opacity-0")
})

it("pauses following when scrolled up and offers a jump to latest", async () => {
  const trace = Array.from({ length: 100 }, (_, index) => frame(index + 1))

  render(
    <CanTraceTable
      trace={trace}
      totalCount={trace.length}
      networks={networks}
      selectedNetworks={new Set(["fcan"])}
      selected={null}
      onSelect={vi.fn()}
      onToggleNetwork={vi.fn()}
    />
  )

  const viewport = document.querySelector<HTMLElement>(
    "[data-slot='scroll-area-viewport']"
  )!
  Object.defineProperties(viewport, {
    scrollHeight: { configurable: true, value: 1_000 },
    clientHeight: { configurable: true, value: 360 },
    scrollTop: { configurable: true, value: 100, writable: true },
  })
  fireEvent.wheel(viewport, { deltaY: -100 })
  fireEvent.scroll(viewport)

  const jump = await screen.findByRole("button", {
    name: "Jump to latest CAN frame",
  })
  expect(jump.className).toContain("opacity-100")
  const scrollTo = vi.mocked(HTMLElement.prototype.scrollTo)
  scrollTo.mockClear()
  fireEvent.click(jump)

  expect(scrollTo).toHaveBeenCalled()
})
