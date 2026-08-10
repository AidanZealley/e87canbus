import {
  MutationObserver,
  onlineManager,
  QueryClient,
} from "@tanstack/react-query"
import { afterEach, expect, test, vi } from "vitest"

import { consoleQueryClientOptions } from "./query-client-options"

const initialOnline = onlineManager.isOnline()

afterEach(() => onlineManager.setOnline(initialOnline))

test("an offline mutation fails once instead of replaying after reconnection", async () => {
  const mutation = vi.fn().mockRejectedValue(new Error("offline"))
  const observer = new MutationObserver(
    new QueryClient(consoleQueryClientOptions),
    { mutationFn: mutation }
  )
  onlineManager.setOnline(false)

  await expect(observer.mutate(undefined)).rejects.toThrow("offline")
  expect(mutation).toHaveBeenCalledTimes(1)

  onlineManager.setOnline(true)
  await vi.waitFor(() => expect(mutation).toHaveBeenCalledTimes(1))
})
