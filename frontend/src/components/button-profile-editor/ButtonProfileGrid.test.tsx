// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, expect, it, vi } from "vitest"

import { ButtonProfileGrid } from "./ButtonProfileGrid"

afterEach(cleanup)

it("renders all sixteen labelled bindings and selects a button for editing", () => {
  const onEdit = vi.fn()
  const slots = Array.from({ length: 16 }, () => null)
  slots[2] = { type: "adjust_manual_assistance", delta: 1 } as never

  render(
    <ButtonProfileGrid
      slots={slots}
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
