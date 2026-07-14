import type { CanTraceEntry } from "../../types"
import { isCompleteLedSnapshot, LED_COUNT } from "../../utils.ts"

const LED_SNAPSHOT_HEX_LENGTH = LED_COUNT

export const decodeLedSnapshot = (dataHex: string): number[] | null => {
  if (dataHex.length !== LED_SNAPSHOT_HEX_LENGTH) return null

  const colours = Array.from({ length: LED_COUNT }, (_, index) => {
    const byteStart = Math.floor(index / 2) * 2
    const packed = Number.parseInt(dataHex.slice(byteStart, byteStart + 2), 16)
    return index % 2 === 0 ? packed & 0x0f : packed >> 4
  })
  return isCompleteLedSnapshot(colours) ? colours : null
}

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
    const colours = decodeLedSnapshot(entry.data_hex)
    return colours === null
      ? "malformed LED snapshot"
      : `LEDs ${colours.join(" ")}`
  }

  return "unknown"
}
