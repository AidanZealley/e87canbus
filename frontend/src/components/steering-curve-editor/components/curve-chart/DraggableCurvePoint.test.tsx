// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { DraggableCurvePoint } from "./DraggableCurvePoint"

afterEach(cleanup)

const renderPoint = (onChange = vi.fn(), onAdjustingChange = vi.fn()) => {
  const result = render(
    <svg viewBox="0 0 320 200">
      <DraggableCurvePoint
        x={100}
        y={100}
        speedKph={60}
        assistancePerMille={500}
        minimum={300}
        maximum={700}
        inverseY={(value) => value * 5}
        onChange={onChange}
        onAdjustingChange={onAdjustingChange}
      />
    </svg>
  )
  vi.spyOn(
    result.container.querySelector("svg")!,
    "getBoundingClientRect"
  ).mockReturnValue({
    x: 0,
    y: 0,
    top: 0,
    left: 0,
    right: 320,
    bottom: 200,
    width: 320,
    height: 200,
    toJSON: () => ({}),
  })
  return onChange
}

describe("DraggableCurvePoint", () => {
  it("keeps focus styling on a separate outer ring", () => {
    renderPoint()

    expect(
      document.querySelector(".peer-focus-visible\\:opacity-100")
    ).not.toBeNull()
    expect(
      document.querySelector(".peer-focus-visible\\:stroke-ring")
    ).toBeNull()
  })

  it("uses pointer capture movement and stops safely on cancel", () => {
    const onChange = vi.fn()
    const onAdjustingChange = vi.fn()
    renderPoint(onChange, onAdjustingChange)
    const handle = screen.getByRole("slider", {
      name: "Assistance at 60 km/h",
    })

    fireEvent.pointerDown(handle, {
      button: 0,
      buttons: 1,
      pointerId: 4,
      pointerType: "mouse",
      clientY: 100,
    })
    fireEvent.pointerMove(handle, {
      buttons: 1,
      pointerId: 4,
      pointerType: "mouse",
      clientY: 80,
    })
    expect(onChange).toHaveBeenLastCalledWith(400)

    fireEvent.pointerCancel(handle, { pointerId: 4 })
    fireEvent.pointerMove(handle, { pointerId: 4, clientY: 60 })
    expect(onChange).toHaveBeenCalledTimes(1)
    expect(onAdjustingChange.mock.calls).toEqual([[true], [false]])
  })

  it("focuses the point when a drag begins so keyboard controls are available", () => {
    renderPoint()
    const handle = screen.getByRole("slider")

    fireEvent.pointerDown(handle, {
      button: 0,
      buttons: 1,
      pointerId: 4,
      pointerType: "mouse",
    })

    expect(document.activeElement).toBe(handle)
  })

  it("does not resume a mouse drag after the button is released elsewhere", () => {
    const onChange = renderPoint()
    const handle = screen.getByRole("slider")

    fireEvent.pointerDown(handle, {
      button: 0,
      buttons: 1,
      pointerId: 1,
      pointerType: "mouse",
      clientY: 100,
    })
    fireEvent.pointerMove(handle, {
      buttons: 0,
      pointerId: 1,
      pointerType: "mouse",
      clientY: 80,
    })
    fireEvent.pointerMove(handle, {
      buttons: 0,
      pointerId: 1,
      pointerType: "mouse",
      clientY: 60,
    })

    expect(onChange).not.toHaveBeenCalled()
  })

  it("supports arrow and page-key precision controls", () => {
    const onChange = renderPoint()
    const handle = screen.getByRole("slider")

    fireEvent.keyDown(handle, { key: "ArrowDown" })
    fireEvent.keyDown(handle, { key: "PageUp" })

    expect(onChange).toHaveBeenNthCalledWith(1, 490)
    expect(onChange).toHaveBeenNthCalledWith(2, 600)
  })
})
