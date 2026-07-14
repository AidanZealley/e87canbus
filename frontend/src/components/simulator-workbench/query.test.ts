import assert from "node:assert/strict"
import test from "node:test"
import { QueryClient } from "@tanstack/react-query"

import {
  applySimulatorEvent,
  replaceSimulatorSnapshot,
  simulatorQueryKey,
} from "./cache.ts"
import { reconnectDelay } from "./connection.ts"
import { emptySnapshot, type WorkbenchSnapshot } from "./utils.ts"

test("frame events update only the cached trace slice", () => {
  const queryClient = new QueryClient()
  queryClient.setQueryData<WorkbenchSnapshot>(simulatorQueryKey, emptySnapshot)

  applySimulatorEvent(queryClient, {
    type: "frame",
    session_id: 0,
    sequence: 1,
    network: "kcan",
    source: "neotrellis",
    arbitration_id: 0x700,
    arbitration_id_hex: "0x700",
    data_hex: "0001",
    is_extended_id: false,
    monotonic_s: 0,
  })

  const updated = queryClient.getQueryData<WorkbenchSnapshot>(simulatorQueryKey)
  assert.equal(updated?.trace.length, 1)
  assert.equal(updated?.application, emptySnapshot.application)
  assert.equal(updated?.led_colours, emptySnapshot.led_colours)
  assert.equal(updated?.networks, emptySnapshot.networks)
})

test("a reconnect snapshot replaces revisions from a previous backend process", () => {
  const queryClient = new QueryClient()
  queryClient.setQueryData<WorkbenchSnapshot>(simulatorQueryKey, {
    ...emptySnapshot,
    session_id: 4,
    revision: 20,
  })

  replaceSimulatorSnapshot(queryClient, {
    ...emptySnapshot,
    session_id: 1,
    revision: 1,
    application: {
      ...emptySnapshot.application,
      steering_mode: "manual",
    },
  })

  const updated = queryClient.getQueryData<WorkbenchSnapshot>(simulatorQueryKey)
  assert.equal(updated?.session_id, 1)
  assert.equal(updated?.revision, 1)
  assert.equal(updated?.application.steering_mode, "manual")
})

test("reconnect delay is exponential, jittered, and capped", () => {
  assert.equal(reconnectDelay(0, () => 0.5), 500)
  assert.equal(reconnectDelay(3, () => 0.5), 4_000)
  assert.equal(reconnectDelay(20, () => 0.5), 10_000)
  assert.equal(reconnectDelay(0, () => 0), 400)
  assert.equal(reconnectDelay(0, () => 1), 600)
})
