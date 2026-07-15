// @vitest-environment jsdom
import { cleanup, render, screen, within } from "@testing-library/react"
import { DropletIcon } from "lucide-react"
import { afterEach, expect, it } from "vitest"

import { DeviceStatusFooter } from "@/components/device-status-footer"
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

  expect(screen.getAllByText("—")).toHaveLength(3)
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
  const criticalBadge = within(screen.getByLabelText("Oil temperature")).getByText(
    "Critical"
  )
  expect(criticalBadge.getAttribute("data-variant")).toBe("destructive")
  expect(criticalBadge.className).toContain("motion-safe:animate-strobe")
  expect(criticalBadge.className).not.toContain("animate-pulse")
  expect(criticalBadge.querySelector("svg[data-icon=inline-start]")).toBeTruthy()
})

it("fails an absent custom device closed", () => {
  const { container } = render(
    <DeviceStatusFooter devices={[]} />
  )

  const footer = screen.getByRole("contentinfo", { name: "Device status" })
  expect(within(footer).getByText("Button pad")).toBeTruthy()
  expect(within(footer).getByText("Unavailable")).toBeTruthy()
  expect(container.querySelector(".bg-muted-foreground")).toBeTruthy()
})

it("does not present physical desired state as an observation", () => {
  const { container } = render(
    <DeviceStatusFooter
      devices={[
        {
          id: "button_pad",
          label: "Button pad",
          source_mode: "physical",
          connected: null,
          last_seen_monotonic_s: null,
          desired_led_colours: Array(16).fill(0),
          observed_led_colours: null,
          last_output_fault: null,
        },
      ]}
    />
  )

  expect(screen.getByText("physical")).toBeTruthy()
  expect(screen.getByText(/connection unknown/)).toBeTruthy()
  expect(container.querySelector(".bg-muted-foreground")).toBeTruthy()
  expect(container.querySelector(".bg-emerald-500")).toBeNull()
})
