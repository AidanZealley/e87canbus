// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react"
import { DropletIcon } from "lucide-react"
import { afterEach, expect, it } from "vitest"

import { DriveTemperatureGauge } from "./DriveTemperatureGauge"

afterEach(cleanup)

it("places the operating temperature at the midpoint", () => {
  render(
    <DriveTemperatureGauge
      icon={DropletIcon}
      label="Oil temperature"
      value={110}
      valueC={110}
      unit="°C"
      operatingTemperatureC={110}
      status="valid"
      severity="normal"
    />
  )

  expect(
    screen
      .getByRole("progressbar", { name: "Oil temperature position" })
      .getAttribute("aria-valuenow")
  ).toBe("50")
})

it("keeps progress based on Celsius when the displayed unit is Fahrenheit", () => {
  render(
    <DriveTemperatureGauge
      icon={DropletIcon}
      label="Oil temperature"
      value={230}
      valueC={110}
      unit="°F"
      operatingTemperatureC={110}
      status="valid"
      severity="normal"
    />
  )

  expect(screen.getByLabelText("Oil temperature").textContent).toContain("230")
  expect(
    screen
      .getByRole("progressbar", { name: "Oil temperature position" })
      .getAttribute("aria-valuenow")
  ).toBe("50")
})

it("shows stale telemetry without manufacturing a numeric reading", () => {
  render(
    <DriveTemperatureGauge
      icon={DropletIcon}
      label="Oil temperature"
      value={null}
      valueC={null}
      unit="°C"
      operatingTemperatureC={110}
      status="stale"
      severity="unavailable"
    />
  )

  expect(screen.getByLabelText("Oil temperature").textContent).toContain(
    "Stale"
  )
  expect(screen.getByLabelText("Oil temperature").textContent).toContain("—")
  expect(screen.queryByText("0")).toBeNull()
})

it("uses a destructive badge with an alert icon only for critical status", () => {
  const view = render(
    <DriveTemperatureGauge
      icon={DropletIcon}
      label="Oil temperature"
      value={135}
      valueC={135}
      unit="°C"
      operatingTemperatureC={110}
      status="valid"
      severity="critical"
    />
  )

  const criticalBadge = screen.getByText("Critical")
  expect(criticalBadge.getAttribute("data-variant")).toBe("destructive")
  expect(criticalBadge.className).toContain("motion-safe:animate-strobe")
  expect(criticalBadge.className).not.toContain("animate-pulse")
  expect(
    criticalBadge.querySelector("svg[data-icon=inline-start]")
  ).toBeTruthy()

  view.rerender(
    <DriveTemperatureGauge
      icon={DropletIcon}
      label="Oil temperature"
      value={110}
      valueC={110}
      unit="°C"
      operatingTemperatureC={110}
      status="valid"
      severity="normal"
    />
  )

  const normalBadge = screen.getByText("Normal")
  expect(normalBadge.getAttribute("data-variant")).toBe("default")
  expect(normalBadge.className).not.toContain("animate-strobe")
  expect(normalBadge.querySelector("svg")).toBeNull()
})

it("uses an amber badge without strobing for warning status", () => {
  render(
    <DriveTemperatureGauge
      icon={DropletIcon}
      label="Oil temperature"
      value={125}
      valueC={125}
      unit="°C"
      operatingTemperatureC={110}
      status="valid"
      severity="warning"
    />
  )

  const warningBadge = screen.getByText("Warning")
  expect(warningBadge.getAttribute("data-variant")).toBe("warning")
  expect(warningBadge.className).toContain("text-amber-700")
  expect(warningBadge.className).not.toContain("animate-strobe")
})
