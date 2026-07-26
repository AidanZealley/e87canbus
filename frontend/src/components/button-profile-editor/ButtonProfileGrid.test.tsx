// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, expect, it, vi } from "vitest"

import { ButtonProfileGrid } from "./ButtonProfileGrid"
import { toButtonCommandSlots, type ButtonCommandSlot } from "./types"

afterEach(cleanup)

it("renders all sixteen labelled bindings and selects a button for editing", () => {
  const onEdit = vi.fn()
  const slots: ButtonCommandSlot[] = Array.from({ length: 16 }, () => null)
  slots[2] = {
    command: { type: "adjust_manual_assistance", delta: 1 },
    colour: [255, 255, 255],
    active_colour: null,
    animation: null,
  }

  render(
    <ButtonProfileGrid
      slots={toButtonCommandSlots(slots)}
      rgb={Array.from({ length: 16 }, () => [0, 0, 0] as const)}
      onEdit={onEdit}
    />
  )

  expect(screen.getAllByRole("button", { name: /Edit button/ })).toHaveLength(
    16
  )
  fireEvent.click(
    screen.getByRole("button", { name: "Edit button 2: Assist +" })
  )
  expect(onEdit).toHaveBeenCalledWith(2)
})
