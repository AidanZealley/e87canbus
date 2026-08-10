// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, expect, it, vi } from "vitest"

import { CurveActions } from "./CurveActions"

afterEach(cleanup)

it("uses the server-projected level count for the upper manual bound", () => {
  render(
    <CurveActions
      mode="manual"
      manualAssistanceLevel={2}
      manualAssistanceLevelCount={3}
      maximumAssistanceActive={false}
      pendingAction={null}
      activeMatchesSaved
      hasSavedProfile
      onModeChange={vi.fn()}
      onLevelAdjust={vi.fn()}
      onMaximumChange={vi.fn()}
      onSave={vi.fn()}
      onReset={vi.fn()}
    />
  )

  expect(
    screen.getByRole("button", { name: "Increase assistance" }).hasAttribute("disabled")
  ).toBe(true)
})
