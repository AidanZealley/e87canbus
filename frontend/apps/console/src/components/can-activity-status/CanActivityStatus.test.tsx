// @vitest-environment jsdom
import { act, cleanup, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, expect, it } from "vitest"

import { CanActivityStatus } from "./CanActivityStatus"
import { consoleSnapshot } from "@/local-live/test-fixtures"
import { useConsoleLiveStore } from "@/local-live/store"

beforeEach(() => useConsoleLiveStore.getState().reset())
afterEach(cleanup)

it("renders a received-frame update from the complete local snapshot", () => {
  render(<CanActivityStatus />)
  expect(screen.getByRole("status").textContent).toContain(
    "K-CAN status unavailable"
  )

  act(() => {
    useConsoleLiveStore
      .getState()
      .applySnapshot(consoleSnapshot("console-boot", 2, 37))
  })

  expect(screen.getByRole("status").textContent).toContain(
    "K-CAN connected, 37 frames received"
  )
})

it("presents silence without claiming a CAN fault and exposes reader faults", () => {
  render(<CanActivityStatus />)
  act(() => {
    useConsoleLiveStore
      .getState()
      .applySnapshot(consoleSnapshot("console-boot", 1))
  })
  expect(screen.getByRole("status").textContent).toContain("no frames observed")
  expect(screen.getByRole("status").textContent).not.toContain("fault")

  act(() => {
    useConsoleLiveStore.getState().applySnapshot(
      consoleSnapshot("console-boot", 2, 0, {
        connected: false,
        fault: "reader stopped",
      })
    )
  })
  expect(screen.getByRole("status").textContent).toContain(
    "K-CAN fault: reader stopped"
  )

  act(() => useConsoleLiveStore.getState().transportDisconnected())
  expect(screen.getByRole("status").textContent).toContain(
    "K-CAN status unavailable"
  )
})
