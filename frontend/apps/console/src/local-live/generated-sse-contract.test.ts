import { describe, expect, it, vi } from "vitest"

import { streamConsoleLiveApiLiveGet } from "@/api/console-host"

const responseWith = (event: unknown) =>
  new Response(`data: ${JSON.stringify(event)}\n\n`, {
    headers: { "Content-Type": "text/event-stream" },
  })

describe("generated console SSE operation", () => {
  it("validates each streamed JSON record with the generated schema", async () => {
    const onSseError = vi.fn()
    const valid = {
      type: "console.snapshot",
      data: {
        can: {
          interface: "kcan",
          connected: true,
          frames_received: 12,
          fault: null,
        },
      },
    }
    const result = await streamConsoleLiveApiLiveGet({
      baseUrl: "http://test.local",
      fetch: vi.fn(async () => responseWith(valid)),
      onSseError,
      sseMaxRetryAttempts: 1,
    })

    expect(await result.stream.next()).toEqual({ done: false, value: valid })
    expect(onSseError).not.toHaveBeenCalled()

    for (const invalid of [
      {
        ...valid,
        data: { can: { ...valid.data.can, frames_received: -1 } },
      },
      { data: valid.data },
    ]) {
      onSseError.mockClear()
      const invalidResult = await streamConsoleLiveApiLiveGet({
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
