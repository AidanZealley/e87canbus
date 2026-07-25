import { expect, it } from "vitest"

import { buttonProfileStatusLabel } from "./profile-status"

it("never reports a profile active while live state is unsynchronized", () => {
  expect(
    buttonProfileStatusLabel({
      synchronized: false,
      sameProfile: true,
      sameRevision: true,
    })
  ).toBe("Status unavailable")
  expect(
    buttonProfileStatusLabel({
      synchronized: true,
      sameProfile: true,
      sameRevision: true,
    })
  ).toBe("Active")
})
