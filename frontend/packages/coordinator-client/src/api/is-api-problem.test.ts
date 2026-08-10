import { describe, expect, it } from "vitest"

import { isApiProblemResponse } from "./is-api-problem"

describe("isApiProblemResponse", () => {
  it("accepts a complete generated API problem", () => {
    expect(
      isApiProblemResponse({
        error: {
          code: "profile_revision_conflict",
          message: "Profile changed",
          current_revision: 2,
        },
      })
    ).toBe(true)
  })

  it("rejects partial and unknown problem shapes", () => {
    expect(
      isApiProblemResponse({
        error: { code: "profile_revision_conflict" },
      })
    ).toBe(false)
    expect(
      isApiProblemResponse({
        error: { code: "unknown_code", message: "Unknown" },
      })
    ).toBe(false)
  })
})
