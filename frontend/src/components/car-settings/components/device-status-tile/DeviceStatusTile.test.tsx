// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, expect, it } from "vitest"

import type { DeviceRegistryEntryState } from "@/api/live-contract.gen"
import { DeviceStatusTile } from "./DeviceStatusTile"

afterEach(cleanup)

const device = (
  overrides: Partial<DeviceRegistryEntryState> = {}
): DeviceRegistryEntryState => ({
  role: "button_pad",
  label: "Button pad",
  device_id: 1,
  source_mode: "physical",
  status: "stale",
  protocol_version: 1,
  device_session_id: 1,
  last_status_code: null,
  last_transition_monotonic_s: null,
  ...overrides,
})

it("does not present physical desired state as an observation", () => {
  const { container } = render(<DeviceStatusTile device={device()} />)

  expect(screen.getByText("physical")).toBeTruthy()
  expect(screen.getByText("Contact lost")).toBeTruthy()
  expect(container.querySelector(".bg-amber-500")).toBeTruthy()
  expect(container.querySelector(".bg-emerald-500")).toBeNull()
})

it("reports unobserved and faulted devices as such", () => {
  const { container } = render(
    <div>
      <DeviceStatusTile
        device={device({
          role: "servotronic_controller",
          label: "Servotronic controller",
          status: "not_found",
          protocol_version: null,
        })}
      />
      <DeviceStatusTile
        device={device({ status: "fault", last_status_code: 7 })}
      />
    </div>
  )

  expect(screen.getByText("Not found")).toBeTruthy()
  expect(screen.getByText("Never seen on the bus")).toBeTruthy()
  expect(screen.getByText("-")).toBeTruthy()
  expect(screen.getByText("Reported status code 7")).toBeTruthy()
  expect(container.querySelector(".bg-emerald-500")).toBeNull()
})
