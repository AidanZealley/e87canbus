// @vitest-environment jsdom
import { cleanup, render, screen, within } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { DeviceStatusFooter } from "@/components/device-status-footer"
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
    </div>
  )

  expect(screen.getByText("Critical")).toBeTruthy()
  expect(screen.getByText("Redline")).toBeTruthy()
  expect(screen.getByRole("meter").getAttribute("aria-valuenow")).toBe("7200")
  expect(screen.getByRole("meter").getAttribute("aria-valuemax")).toBe("7200")
  expect(screen.getByRole("meter").getAttribute("aria-valuetext")).toContain(
    "7600 RPM"
  )
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

describe.each(["light", "dark"])("%s theme", (theme) => {
  it("renders every reusable instrument", () => {
    const { container } = render(
      <div className={theme}>
        <TelemetryValue label="Speed" value={62} unit="mph" status="Live" />
        <TemperatureGauge
          label="Oil temperature"
          value={127}
          unit="°C"
          status="valid"
          severity="warning"
        />
        <RpmBar rpm={6900} stage="stage_1" position={0.95} redlineRpm={7200} />
        <DeviceStatusFooter
          devices={[
            {
              id: "button_pad",
              label: "Button pad",
              source_mode: "emulated",
              connected: true,
              last_seen_monotonic_s: 1,
              desired_led_colours: Array(16).fill(0),
              observed_led_colours: Array(16).fill(0),
              last_output_fault: null,
            },
          ]}
        />
      </div>
    )

    expect(container.textContent).toContain("62")
    expect(container.textContent).toContain("Warning")
    expect(container.textContent).toContain("Shift stage 1")
    expect(container.textContent).toContain("Button pad")
  })
})
