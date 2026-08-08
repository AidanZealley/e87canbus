// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, expect, it } from "vitest"

import { CoordinatorPanel } from "./CoordinatorPanel"

afterEach(cleanup)

it("renders five accessible status lights", () => {
  const { container } = render(
    <CoordinatorPanel display="ready" onHotspotPress={() => undefined} />
  )

  expect(
    screen.getByRole("img", { name: "Coordinator indicator: Ready" })
  ).toBeTruthy()
  expect(container.querySelectorAll("[data-panel-light]")).toHaveLength(5)
})
