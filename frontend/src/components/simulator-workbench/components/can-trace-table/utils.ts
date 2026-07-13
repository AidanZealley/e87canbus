import type { CanTraceEntry } from "../../types"

export const decodeMeaning = (entry: CanTraceEntry) => {
  if (entry.arbitration_id_hex === "0x700") {
    const button = Number.parseInt(entry.data_hex.slice(0, 2), 16)
    const state = entry.data_hex.slice(2, 4) === "01" ? "pressed" : "released"
    return `button ${button} ${state}`
  }

  if (entry.arbitration_id_hex === "0x701") {
    const button = Number.parseInt(entry.data_hex.slice(0, 2), 16)
    const colour = Number.parseInt(entry.data_hex.slice(2, 4), 16)
    return `LED ${button} colour ${colour}`
  }

  return "unknown"
}
