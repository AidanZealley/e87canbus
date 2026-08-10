// @vitest-environment jsdom
import { cleanup, render, screen, within } from "@testing-library/react"
import { DropletIcon } from "lucide-react"
import { afterEach, expect, it } from "vitest"

import { DriveTemperatureGauge } from "@/components/drive-temperature-gauge"
import { RpmBar } from "@/components/rpm-bar"
import { TelemetryValue } from "@/components/telemetry-value"
import { TemperatureGauge } from "@/components/temperature-gauge"

afterEach(cleanup)

it("never renders a manufactured numeric zero for unavailable values", () => {
  render(
    <div>
      <TelemetryValue label="Speed" value={null} unit="mph" />
      <TemperatureGauge
        label="Oil temperature"
        value={null}
        unit="°C"
        status="never_observed"
        severity="unavailable"
      />
      <RpmBar rpm={null} stage="unavailable" position={0} redlineRpm={7200} />
    </div>
  )

  expect(screen.getAllByText("-")).toHaveLength(3)
  expect(screen.queryByText("0")).toBeNull()
  expect(screen.getAllByText("Unavailable").length).toBeGreaterThanOrEqual(3)
})

it("renders severity and RPM stage as text in addition to color", () => {
  render(
    <div>
      <TemperatureGauge
        label="Coolant temperature"
        value={116}
        unit="°C"
        status="valid"
        severity="critical"
      />
      <RpmBar rpm={7600} stage="redline" position={1} redlineRpm={7200} />
      <DriveTemperatureGauge
        icon={DropletIcon}
        label="Oil temperature"
        value={230}
        valueC={110}
        unit="°F"
        operatingTemperatureC={110}
        maximumTemperatureC={150}
        status="valid"
        severity="critical"
      />
    </div>
  )

  expect(screen.getAllByText("Critical")).toHaveLength(2)
  expect(screen.getByText("Redline")).toBeTruthy()
  expect(screen.getByRole("meter").getAttribute("aria-valuenow")).toBe("7200")
  expect(screen.getByRole("meter").getAttribute("aria-valuemax")).toBe("7200")
  expect(screen.getByRole("meter").getAttribute("aria-valuetext")).toContain(
    "7600 RPM"
  )
  const rpmSegments = screen
    .getByRole("meter")
    .querySelectorAll('[aria-hidden="true"]')
  expect(rpmSegments).toHaveLength(18)
  for (const segment of rpmSegments) {
    expect(segment.className).toContain("motion-safe:animate-shift-strobe")
  }
  expect(
    screen
      .getByRole("progressbar", { name: "Oil temperature position" })
      .getAttribute("aria-valuenow")
  ).toBe("50")
  const criticalBadge = within(
    screen.getByLabelText("Oil temperature")
  ).getByText("Critical")
  expect(criticalBadge.getAttribute("data-variant")).toBe("destructive")
  expect(criticalBadge.className).toContain("motion-safe:animate-strobe")
  expect(criticalBadge.className).not.toContain("animate-pulse")
  expect(
    criticalBadge.querySelector("svg[data-icon=inline-start]")
  ).toBeTruthy()
})

it("shows cold below OT, centers OT, and holds the bar below its useful range", () => {
  render(
    <div>
      <DriveTemperatureGauge
        icon={DropletIcon}
        label="Very cold oil"
        value={60}
        valueC={60}
        unit="°C"
        operatingTemperatureC={110}
        maximumTemperatureC={150}
        status="valid"
        severity="normal"
      />
      <DriveTemperatureGauge
        icon={DropletIcon}
        label="Cold oil"
        value={90}
        valueC={90}
        unit="°C"
        operatingTemperatureC={110}
        maximumTemperatureC={150}
        status="valid"
        severity="normal"
      />
      <DriveTemperatureGauge
        icon={DropletIcon}
        label="Warm oil"
        value={110}
        valueC={110}
        unit="°C"
        operatingTemperatureC={110}
        maximumTemperatureC={150}
        status="valid"
        severity="normal"
      />
    </div>
  )

  const veryCold = screen.getByLabelText("Very cold oil")
  expect(within(veryCold).getByText("Cold").getAttribute("data-variant")).toBe(
    "cold"
  )
  expect(
    screen
      .getByRole("progressbar", { name: "Very cold oil position" })
      .getAttribute("aria-valuenow")
  ).toBe("0")
  expect(
    screen
      .getByRole("progressbar", { name: "Cold oil position" })
      .getAttribute("aria-valuenow")
  ).toBe("25")
  expect(
    screen
      .getByRole("progressbar", { name: "Warm oil position" })
      .getAttribute("aria-valuenow")
  ).toBe("50")
  expect(
    screen
      .getByRole("progressbar", { name: "Cold oil position" })
      .className.includes("bg-blue-500")
  ).toBe(true)
  expect(
    screen
      .getByRole("progressbar", { name: "Warm oil position" })
      .className.includes("bg-emerald-500")
  ).toBe(false)
})
