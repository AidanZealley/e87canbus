// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, expect, it, vi } from "vitest"

import type { SteeringCurveDefinition } from "@/api/steering"
import { CurveChart } from "./CurveChart"

afterEach(cleanup)

it("renders eight accessible points on honest linear series", async () => {
  vi.stubGlobal(
    "ResizeObserver",
    class {
      private readonly callback: ResizeObserverCallback

      constructor(callback: ResizeObserverCallback) {
        this.callback = callback
      }

      observe(target: Element) {
        this.callback(
          [
            {
              target,
              contentRect: {
                x: 0,
                y: 0,
                top: 0,
                left: 0,
                right: 800,
                bottom: 300,
                width: 800,
                height: 300,
                toJSON: () => ({}),
              },
            } as ResizeObserverEntry,
          ],
          this
        )
      }
      unobserve() {}
      disconnect() {}
    }
  )
  const definition: SteeringCurveDefinition = {
    schema_version: 1,
    points: [0, 100, 200, 300, 600, 1000, 1600, 2500].map(
      (speed_deci_kph, index) => ({
        speed_deci_kph,
        assistance_per_mille: [1000, 890, 780, 670, 380, 0, 0, 0][index] ?? 0,
      })
    ),
  }

  const { rerender } = render(
    <CurveChart
      active={definition}
      draft={definition}
      activeSpeedKph={20}
      activeAssistance={0.78}
      onPointChange={vi.fn()}
    />
  )

  expect(await screen.findAllByRole("slider")).toHaveLength(8)
  expect(document.querySelectorAll(".recharts-line-curve")).toHaveLength(2)
  for (const path of document.querySelectorAll(".recharts-line-curve")) {
    expect(path.getAttribute("d")).not.toContain("C")
  }
  const marker = document.querySelector(".recharts-reference-line line")
  expect(marker?.getAttribute("stroke")).toBe("var(--color-indigo-500)")
  expect(document.querySelector(".recharts-tooltip-wrapper")).not.toBeNull()
  const tooltip = document.querySelector<HTMLElement>(
    ".recharts-tooltip-wrapper"
  )!
  expect(tooltip.style.opacity).toBe("1")
  const firstPoint = screen.getAllByRole("slider")[0]!
  fireEvent.pointerDown(firstPoint, {
    button: 0,
    buttons: 1,
    pointerId: 1,
    pointerType: "mouse",
  })
  expect(tooltip.style.opacity).toBe("0")
  fireEvent.pointerUp(firstPoint, { pointerId: 1, pointerType: "mouse" })
  expect(tooltip.style.opacity).toBe("1")
  const activeDots = document.querySelectorAll(".recharts-active-dot circle")
  expect(activeDots).toHaveLength(0)
  expect(document.querySelector(".recharts-zIndex-layer_1300")).not.toBeNull()
  const activeCurvePath = document
    .querySelectorAll(".recharts-line-curve")[0]
    ?.getAttribute("d")
  const markerYAtCurveAssistance = marker?.getAttribute("y1")

  rerender(
    <CurveChart
      active={definition}
      draft={definition}
      activeSpeedKph={20}
      activeAssistance={1}
      onPointChange={vi.fn()}
    />
  )
  const maximumAssistanceMarker = document.querySelector(
    ".recharts-reference-line line"
  )
  expect(maximumAssistanceMarker?.getAttribute("stroke")).toBe(
    "var(--color-indigo-500)"
  )
  expect(maximumAssistanceMarker?.getAttribute("y1")).not.toBe(
    markerYAtCurveAssistance
  )
  expect(
    document.querySelectorAll(".recharts-line-curve")[0]?.getAttribute("d")
  ).toBe(activeCurvePath)

  rerender(
    <CurveChart
      active={definition}
      draft={definition}
      activeSpeedKph={null}
      activeAssistance={null}
      onPointChange={vi.fn()}
    />
  )
  const stoppedMarker = document.querySelector(
    ".recharts-reference-line line"
  )
  expect(stoppedMarker).not.toBeNull()
  expect(stoppedMarker?.getAttribute("y1")).toBe(
    maximumAssistanceMarker?.getAttribute("y1")
  )
})
