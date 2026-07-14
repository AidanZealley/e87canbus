// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react"
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
    interpolation: "linear-v1",
    points: [0, 100, 200, 300, 600, 1000, 1600, 2500].map(
      (speed_deci_kph, index) => ({
        speed_deci_kph,
        assistance_per_mille: [1000, 890, 780, 670, 380, 0, 0, 0][index] ?? 0,
      })
    ),
  }

  render(
    <CurveChart
      active={definition}
      draft={definition}
      speedKph={10}
      activeAssistance={0.89}
      onPointChange={vi.fn()}
    />
  )

  expect(await screen.findAllByRole("slider")).toHaveLength(8)
  expect(document.querySelectorAll(".recharts-line-curve")).toHaveLength(2)
  for (const path of document.querySelectorAll(".recharts-line-curve")) {
    expect(path.getAttribute("d")).not.toContain("C")
  }
  expect(
    document.querySelector(".recharts-reference-dot circle")?.getAttribute(
      "pointer-events"
    )
  ).toBe("none")
})
