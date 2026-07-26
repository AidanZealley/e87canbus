// @vitest-environment jsdom
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react"
import { afterEach, expect, it, vi } from "vitest"

import { toButtonCommandSlots, type ButtonCommandSlot } from "../../types"
import { ButtonProfileList } from "./ButtonProfileList"

afterEach(cleanup)

const slots = (): ButtonCommandSlot[] => {
  const values: ButtonCommandSlot[] = Array.from({ length: 16 }, () => null)
  values[2] = {
    command: { type: "set_manual_assistance_level", level: 3 },
    colour: [0, 102, 255],
    active_colour: null,
    animation: null,
  }
  return values
}

it("renders sixteen numbered items and expands command-specific controls", () => {
  render(
    <ButtonProfileList
      slots={toButtonCommandSlots(slots())}
      visualStates={Array.from({ length: 16 }, (_, index) =>
        index === 2 ? "inactive" : "unassigned"
      )}
      onChange={async () => {}}
    />
  )

  expect(screen.getAllByRole("region", { name: /Button \d+:/ })).toHaveLength(
    16
  )
  const configure = screen.getByRole("button", {
    name: "Configure button 2: Assist 3",
  })
  expect(configure.getAttribute("aria-expanded")).toBe("false")
  fireEvent.click(configure)
  expect(configure.getAttribute("aria-expanded")).toBe("true")
  expect(screen.getByLabelText("Level")).toBeTruthy()
  expect(screen.getByLabelText("Active animation")).toBeTruthy()
})

it("shows paired colour values and keeps invalid dark hex drafts unsaved", async () => {
  const onChange = vi.fn(async () => {})
  render(
    <ButtonProfileList
      slots={toButtonCommandSlots(slots())}
      visualStates={Array.from({ length: 16 }, () => "inactive")}
      onChange={onChange}
    />
  )

  fireEvent.click(
    screen.getByRole("button", {
      name: "Button 2 colour: full #0066FF, faint #000308",
    })
  )
  const hex = screen.getByLabelText("Hex value")
  fireEvent.change(hex, { target: { value: "#00000F" } })
  fireEvent.blur(hex)
  expect(
    await screen.findByText(/inactive LED does not render as off/)
  ).toBeTruthy()
  expect(onChange).not.toHaveBeenCalled()

  fireEvent.change(hex, { target: { value: "#00FF00" } })
  fireEvent.blur(hex)
  await waitFor(() => {
    expect(onChange).toHaveBeenCalledWith(
      2,
      expect.objectContaining({ colour: [0, 255, 0] })
    )
  })
})

it("saves native-picker and preset colour changes", async () => {
  const onChange = vi.fn(async () => {})
  render(
    <ButtonProfileList
      slots={toButtonCommandSlots(slots())}
      visualStates={Array.from({ length: 16 }, () => "inactive")}
      onChange={onChange}
    />
  )

  fireEvent.click(
    screen.getByRole("button", {
      name: "Button 2 colour: full #0066FF, faint #000308",
    })
  )
  fireEvent.change(screen.getByLabelText("Picker"), {
    target: { value: "#ff0000" },
  })
  await waitFor(() => {
    expect(onChange).toHaveBeenCalledWith(
      2,
      expect.objectContaining({ colour: [255, 0, 0] })
    )
  })

  fireEvent.click(screen.getByRole("button", { name: "Use White #FFFFFF" }))
  await waitFor(() => {
    expect(onChange).toHaveBeenCalledWith(
      2,
      expect.objectContaining({ colour: [255, 255, 255] })
    )
  })
})

it("uses generated command fields and hides animation for momentary commands", () => {
  const values = slots()
  values[4] = {
    command: { type: "start_high_beam_strobe" },
    colour: [255, 255, 255],
    active_colour: null,
    animation: null,
  }
  render(
    <ButtonProfileList
      slots={toButtonCommandSlots(values)}
      visualStates={Array.from({ length: 16 }, () => "inactive")}
      onChange={async () => {}}
    />
  )

  fireEvent.click(
    screen.getByRole("button", {
      name: "Configure button 4: High-beam strobe",
    })
  )
  const strobeItem = screen.getByRole("region", {
    name: "Button 4: High-beam strobe",
  })
  expect(within(strobeItem).queryByLabelText("Level")).toBeNull()
  expect(within(strobeItem).queryByLabelText("Active animation")).toBeNull()
})

it("clears an assigned item without a dialog or simulated button interaction", async () => {
  const onChange = vi.fn(async () => {})
  render(
    <ButtonProfileList
      slots={toButtonCommandSlots(slots())}
      visualStates={Array.from({ length: 16 }, () => "inactive")}
      onChange={onChange}
    />
  )

  fireEvent.click(screen.getByRole("button", { name: "Clear button 2" }))
  await waitFor(() => expect(onChange).toHaveBeenCalledWith(2, null))
  expect(screen.queryByRole("dialog")).toBeNull()
})
