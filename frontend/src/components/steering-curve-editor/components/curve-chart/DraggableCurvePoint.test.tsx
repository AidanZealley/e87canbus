// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { DraggableCurvePoint } from "./DraggableCurvePoint"

afterEach(cleanup)

const renderPoint = (onChange = vi.fn()) => {
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
  it("uses pointer capture movement and stops safely on cancel", () => {
    const onChange = renderPoint()
    const handle = screen.getByRole("slider", {
      name: "Assistance at 60 km/h",
    })

    fireEvent.pointerDown(handle, { pointerId: 4, clientY: 100 })
    fireEvent.pointerMove(handle, { pointerId: 4, clientY: 80 })
    expect(onChange).toHaveBeenLastCalledWith(400)

    fireEvent.pointerCancel(handle, { pointerId: 4 })
    fireEvent.pointerMove(handle, { pointerId: 4, clientY: 60 })
    expect(onChange).toHaveBeenCalledTimes(1)
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
