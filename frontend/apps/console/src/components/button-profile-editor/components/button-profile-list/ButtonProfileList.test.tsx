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
      manualAssistanceLevelCount={11}
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
  expect(screen.getByText("30%")).toBeTruthy()
  expect(screen.getByLabelText("Active animation")).toBeTruthy()
  expect(screen.queryByRole("spinbutton")).toBeNull()
  expect(screen.queryByRole("textbox")).toBeNull()
})

it("maps animation speed presets and commits a two-thumb brightness range", async () => {
  const values = slots()
  values[2] = {
    ...values[2]!,
    animation: {
      kind: "breathe",
      period_ms: 2000,
      minimum: 8,
      maximum: 255,
    },
  }
  const onChange = vi.fn(async () => {})
  render(
    <ButtonProfileList
      slots={toButtonCommandSlots(values)}
      visualStates={Array.from({ length: 16 }, () => "inactive")}
      manualAssistanceLevelCount={11}
      onChange={onChange}
    />
  )
  fireEvent.click(
    screen.getByRole("button", {
      name: "Configure button 2: Assist 3",
    })
  )

  fireEvent.click(screen.getByLabelText("Speed"))
  const fast = await screen.findByRole("option", { name: "Fast" })
  fireEvent.pointerDown(fast, { pointerType: "mouse" })
  fireEvent.click(fast)
  await waitFor(() => {
    expect(onChange).toHaveBeenCalledWith(
      2,
      expect.objectContaining({
        animation: expect.objectContaining({ period_ms: 1000 }),
      })
    )
  })

  onChange.mockClear()
  fireEvent.change(screen.getByLabelText("Minimum brightness"), {
    target: { value: "32" },
  })
  await waitFor(() => {
    expect(onChange).toHaveBeenCalledWith(
      2,
      expect.objectContaining({
        animation: expect.objectContaining({
          minimum: 32,
          maximum: 255,
        }),
      })
    )
  })
})

it("removes hex entry and keeps invalid dark picker values unsaved", async () => {
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
  expect(screen.queryByLabelText("Hex value")).toBeNull()
  expect(screen.getAllByRole("button", { name: /^Use / })).toHaveLength(10)
  const picker = screen.getByLabelText("Picker")
  fireEvent.input(picker, { target: { value: "#00000f" } })
  fireEvent.change(picker, { target: { value: "#00000f" } })
  expect(
    await screen.findByText(/inactive LED does not render as off/)
  ).toBeTruthy()
  expect(onChange).not.toHaveBeenCalled()

  fireEvent.input(picker, { target: { value: "#00ff00" } })
  fireEvent.change(picker, { target: { value: "#00ff00" } })
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

  fireEvent.click(screen.getByRole("button", { name: "Use Purple #8000FF" }))
  await waitFor(() => {
    expect(onChange).toHaveBeenCalledWith(
      2,
      expect.objectContaining({ colour: [128, 0, 255] })
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
