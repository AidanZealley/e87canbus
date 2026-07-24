// @vitest-environment jsdom
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react"
import { afterEach, expect, it, vi } from "vitest"

import { ButtonBindingDialog } from "./ButtonBindingDialog"

afterEach(cleanup)

it("shows fields applicable to the selected command and applies changes", async () => {
  const onApply = vi.fn()
  render(
    <ButtonBindingDialog
      buttonIndex={5}
      command={{ type: "set_manual_assistance_level", level: 3 }}
      open
      onOpenChange={vi.fn()}
      onApply={onApply}
    />
  )

  expect(screen.getByRole("dialog")).toBeTruthy()
  expect(screen.getByRole("heading", { name: "Edit button 5" })).toBeTruthy()
  expect(screen.getByText(/dim amber preview/)).toBeTruthy()
  const input = screen.getByLabelText("Level")
  fireEvent.change(input, { target: { value: "7" } })
  fireEvent.click(screen.getByRole("button", { name: "Apply binding" }))

  await waitFor(() => {
    expect(onApply).toHaveBeenCalledWith({
      type: "set_manual_assistance_level",
      level: 7,
    })
  })
})

it("does not show irrelevant parameter fields", () => {
  render(
    <ButtonBindingDialog
      buttonIndex={0}
      command={{ type: "start_high_beam_strobe" }}
      open
      onOpenChange={vi.fn()}
      onApply={vi.fn()}
    />
  )

  expect(screen.queryByLabelText("Level")).toBeNull()
  expect(screen.queryByLabelText("Mode")).toBeNull()
  expect(screen.queryByLabelText("State")).toBeNull()
})
