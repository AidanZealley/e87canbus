import { describe, expect, it, vi } from "vitest"

import { streamCoordinatorLiveApiLiveGet } from "./http"

const responseWith = (event: unknown) =>
  new Response(`data: ${JSON.stringify(event)}\n\n`, {
    headers: { "Content-Type": "text/event-stream" },
  })

describe("generated coordinator SSE operation", () => {
  it("validates each streamed JSON record with the generated union", async () => {
    const onSseError = vi.fn()
    const valid = {
      type: "resource.changed",
      data: { resource: "settings", id: null, revision: 1 },
    }
    const result = await streamCoordinatorLiveApiLiveGet({
      baseUrl: "http://test.local",
      fetch: vi.fn(async () => responseWith(valid)),
      onSseError,
      sseMaxRetryAttempts: 1,
    })

    const next = await result.stream.next()
    expect(onSseError).not.toHaveBeenCalled()
    expect(next).toEqual({ done: false, value: valid })

    for (const invalid of [
      {
        type: "resource.changed",
        data: { resource: "settings", id: null, revision: 0 },
      },
      {
        type: "resource.changed",
        data: { resource: "settings", id: "profile-1", revision: 1 },
      },
      {
        type: "resource.changed",
        data: { resource: "button_profile", id: null, revision: 1 },
      },
    ]) {
      onSseError.mockClear()
      const invalidResult = await streamCoordinatorLiveApiLiveGet({
        baseUrl: "http://test.local",
        fetch: vi.fn(async () => responseWith(invalid)),
        onSseError,
        sseMaxRetryAttempts: 1,
      })

      expect(await invalidResult.stream.next()).toEqual({
        done: true,
        value: undefined,
      })
      expect(onSseError).toHaveBeenCalledOnce()
    }
  })
})
