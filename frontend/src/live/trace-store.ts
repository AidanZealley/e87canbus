import { create } from "zustand"

import {
  LIVE_PROTOCOL_VERSION,
  type LiveEnvelope,
  type TraceBatch,
  type TraceRow,
} from "@/api/live-events"

export const TRACE_CAPACITY = 2_000

type TraceState = {
  bootId: string | null
  sessionId: number | null
  revision: number
  rows: TraceRow[]
  applyBatch: (
    envelope: LiveEnvelope<TraceBatch>,
    liveBootId: string | null
  ) => void
  clear: () => void
}

export const useTraceStore = create<TraceState>((set, get) => ({
  bootId: null,
  sessionId: null,
  revision: 0,
  rows: [],
  applyBatch: (envelope, liveBootId) => {
    if (
      envelope.protocol_version !== LIVE_PROTOCOL_VERSION ||
      liveBootId === null ||
      envelope.boot_id !== liveBootId ||
      envelope.revision < get().revision ||
      envelope.data.rows.length === 0
    ) {
      return
    }
    const incomingSession = envelope.data.rows.at(-1)?.session_id ?? null
    const current = get()
    const rows = current.sessionId === incomingSession ? current.rows : []
    const seen = new Set(rows.map((row) => `${row.session_id}:${row.sequence}`))
    const appended = [...rows]
    for (const row of envelope.data.rows) {
      const key = `${row.session_id}:${row.sequence}`
      if (row.session_id === incomingSession && !seen.has(key)) {
        appended.push(row)
        seen.add(key)
      }
    }
    appended.sort((left, right) => left.sequence - right.sequence)
    set({
      bootId: envelope.boot_id,
      sessionId: incomingSession,
      revision: envelope.revision,
      rows: appended.slice(-TRACE_CAPACITY),
    })
  },
  clear: () => set({ bootId: null, sessionId: null, revision: 0, rows: [] }),
}))
