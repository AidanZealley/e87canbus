// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, expect, it } from "vitest"

import { ClusterTachometer } from "./ClusterTachometer"

afterEach(cleanup)

it("interpolates the dot-matrix mask in lockstep with the needle", () => {
  const { rerender } = render(
    <ClusterTachometer
      rpm={3600}
      stage="normal"
      position={0.5}
      redlineRpm={7200}
      shiftStage1Rpm={6800}
    />
  )
  const meter = screen.getByRole("meter", { name: "Engine speed" })
  const wash = meter.querySelector<HTMLElement>(
    '[data-slot="tachometer-wash"]'
  )
  const needle = meter.querySelector<HTMLElement>(
    '[data-slot="tachometer-needle"]'
  )
  const warningSegment = meter.querySelector<HTMLElement>(
    '[data-start-rpm="6000"]'
  )
  const finalSegment = meter.querySelector<HTMLElement>(
    '[data-start-rpm="7000"]'
  )

  expect(wash?.style.width).toBe("45%")
  expect(needle?.style.left).toBe("45%")
  expect(wash?.className).toContain("motion-safe:transition-[width]")
  expect(wash?.className).toContain("motion-safe:duration-100")
  expect(wash?.className).toContain("motion-safe:ease-linear")
  expect(needle?.className).toContain("motion-safe:transition-[left]")
  expect(needle?.className).toContain("motion-safe:duration-100")
  expect(needle?.className).toContain("motion-safe:ease-linear")
  expect(warningSegment?.dataset.severity).toBe("warn")
  expect(finalSegment?.dataset.severity).toBe("critical")

  rerender(
    <ClusterTachometer
      rpm={7200}
      stage="redline"
      position={1}
      redlineRpm={7200}
      shiftStage1Rpm={6800}
    />
  )

  expect(wash?.style.width).toBe("90%")
  expect(needle?.style.left).toBe("90%")
  expect(warningSegment?.dataset.severity).toBe("critical")
  expect(finalSegment?.dataset.severity).toBe("critical")
})
