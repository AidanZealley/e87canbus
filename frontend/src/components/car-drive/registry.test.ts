import assert from "node:assert/strict"
import { test } from "vitest"

import {
  DASHBOARDS,
  DASHBOARD_OPTIONS,
  DEFAULT_DASHBOARD_ID,
  resolveDashboard,
} from "./registry"

test("resolves every dashboard the catalog offers", () => {
  for (const option of DASHBOARD_OPTIONS) {
    assert.equal(resolveDashboard(option.id), option)
    assert.equal(DASHBOARDS[option.id], option)
  }
})

test("falls back rather than blanking the drive screen on an unknown choice", () => {
  // The coordinator stores the identifier without knowing this catalog, so a
  // dashboard that was renamed, removed, or only exists in a newer build can
  // reach a running display.
  for (const stored of ["", "removed-dashboard", "from-a-newer-build"]) {
    assert.equal(resolveDashboard(stored), DASHBOARDS[DEFAULT_DASHBOARD_ID])
  }
})
