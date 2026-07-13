import type { CanTraceEntry } from "../../types"

export const decodeMeaning = (entry: CanTraceEntry) => {
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

  if (entry.arbitration_id_hex === "0x701") {
    if (entry.data_hex.length !== 4) return "malformed LED update"
    const button = Number.parseInt(entry.data_hex.slice(0, 2), 16)
    const colour = Number.parseInt(entry.data_hex.slice(2, 4), 16)
    return `LED ${button} colour ${colour}`
  }

  return "unknown"
}
