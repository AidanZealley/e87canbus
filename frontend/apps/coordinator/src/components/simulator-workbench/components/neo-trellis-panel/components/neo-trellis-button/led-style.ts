import type { CSSProperties } from "react"

type Rgb = readonly [red: number, green: number, blue: number]

export const ledStyle = (rgb: Rgb): CSSProperties => {
  const peak = Math.max(...rgb)
  const intensity = peak === 0 ? 0 : (peak / 255) ** (1 / 2.2)
  const hue = peak === 0 ? [0, 0, 0] : rgb.map((channel) => Math.round((channel / peak) * 255))
  return {
    "--button-led-rgb": hue.join(" "),
    "--button-led-ring-alpha": `${75 * intensity}%`,
    "--button-led-glow-alpha": `${20 * intensity}%`,
    "--button-led-cast-alpha": `${14 * intensity}%`,
  } as CSSProperties
}
