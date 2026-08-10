import { forwardRef, type ForwardedRef } from "react"
import type { LucideProps } from "lucide-react"

export type DashboardIconProps = LucideProps

const parseSvg = (raw: string) => {
  const viewBox = raw.match(/viewBox="([^"]+)"/)?.[1] ?? "0 0 200 200"
  const body = raw.match(/<svg[^>]*>([\s\S]*)<\/svg>/)?.[1] ?? ""

  return { body, viewBox }
}

export const createDashboardIcon = (displayName: string, raw: string) => {
  const { body, viewBox } = parseSvg(raw)

  const Icon = forwardRef(function DashboardIcon(
    {
      absoluteStrokeWidth = false,
      className = "",
      size = 24,
      color = "currentColor",
      strokeWidth = 2,
      ...props
    }: DashboardIconProps,
    ref: ForwardedRef<SVGSVGElement>
  ) {
    const numericSize =
      typeof size === "number" ? size : Number.parseFloat(String(size))
    const resolvedStrokeWidth =
      absoluteStrokeWidth && Number.isFinite(numericSize)
        ? (Number(strokeWidth) * 24) / numericSize
        : strokeWidth

    return (
      <svg
        ref={ref}
        xmlns="http://www.w3.org/2000/svg"
        width={size}
        height={size}
        viewBox={viewBox}
        color={color}
        fill="currentColor"
        stroke="currentColor"
        strokeWidth={resolvedStrokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
        className={`lucide lucide-${displayName
          .replace(/([a-z0-9])([A-Z])/g, "$1-$2")
          .toLowerCase()} ${className}`.trim()}
        {...props}
      >
        <g dangerouslySetInnerHTML={{ __html: body }} />
      </svg>
    )
  })

  Icon.displayName = displayName
  return Icon
}
