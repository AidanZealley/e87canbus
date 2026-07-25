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
      onApply={async (command) => onApply(command)}
    />
  )

  expect(screen.getByRole("dialog")).toBeTruthy()
  expect(screen.getByRole("heading", { name: "Edit button 5" })).toBeTruthy()
  expect(screen.getByText(/dim amber preview/)).toBeTruthy()
  expect(screen.getByText("Set manual assistance level")).toBeTruthy()
  expect(screen.queryByText("set_manual_assistance_level")).toBeNull()
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
      onApply={async () => {}}
    />
  )

  expect(screen.queryByLabelText("Level")).toBeNull()
  expect(screen.queryByLabelText("Mode")).toBeNull()
  expect(screen.queryByLabelText("State")).toBeNull()
})

it("shows presentation labels for the selected command and its parameters", () => {
  render(
    <ButtonBindingDialog
      buttonIndex={2}
      command={{ type: "adjust_manual_assistance", delta: -1 }}
      open
      onOpenChange={vi.fn()}
      onApply={async () => {}}
    />
  )

  expect(screen.getByText("Adjust manual assistance")).toBeTruthy()
  expect(screen.getByText("Decrease")).toBeTruthy()
  expect(screen.queryByText("adjust_manual_assistance")).toBeNull()
  expect(screen.queryByText("-1")).toBeNull()
})

it("stays open when applying the binding fails", async () => {
  const onOpenChange = vi.fn()
  render(
    <ButtonBindingDialog
      buttonIndex={0}
      command={null}
      open
      onOpenChange={onOpenChange}
      onApply={async () => {
        throw new Error("save failed")
      }}
    />
  )

  fireEvent.click(screen.getByRole("button", { name: "Apply binding" }))

  await waitFor(() => {
    expect(screen.getByRole("dialog")).toBeTruthy()
    expect(onOpenChange).not.toHaveBeenCalledWith(false)
  })
})
