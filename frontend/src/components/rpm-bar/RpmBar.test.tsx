// @vitest-environment jsdom
import { cleanup, render } from "@testing-library/react"
import { afterEach, expect, it } from "vitest"

import { RpmBar } from "./RpmBar"

afterEach(cleanup)

it.each(["stage_2", "redline"] as const)(
  "fast-strobes active segments at %s",
  (stage) => {
    const { container } = render(
      <RpmBar rpm={7100} stage={stage} position={1} redlineRpm={7200} />
    )

    const segments = container.querySelectorAll('[aria-hidden="true"]')
    expect(segments).toHaveLength(18)
    for (const segment of segments) {
      expect(segment.className).toContain("motion-safe:animate-shift-strobe")
    }
  }
)

it("does not strobe normal or stage 1 segments", () => {
  const { container } = render(
    <RpmBar rpm={6800} stage="stage_1" position={1} redlineRpm={7200} />
  )

  for (const segment of container.querySelectorAll('[aria-hidden="true"]')) {
    expect(segment.className).not.toContain("animate-shift-strobe")
  }
})
