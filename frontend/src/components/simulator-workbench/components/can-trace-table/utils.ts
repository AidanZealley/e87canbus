import type { TraceRow } from "@/api/live-events"
export const decodeMeaning = (entry: TraceRow) => {
  if (entry.network !== "kcan") return "unknown"

  if (entry.arbitration_id_hex === "0x700") {
    if (entry.data_hex.length !== 4) return "malformed button event"
    const button = Number.parseInt(entry.data_hex.slice(0, 2), 16)
    const stateCode = entry.data_hex.slice(2, 4)
    if (stateCode !== "00" && stateCode !== "01") {
      return "malformed button event"
    }
    const state = stateCode === "01" ? "pressed" : "released"
    return `button ${button} ${state}`
  }

  return "unknown"
}
