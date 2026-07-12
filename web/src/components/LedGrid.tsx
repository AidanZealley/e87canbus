import { Circle } from "lucide-react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"

const ledStyles: Record<number, string> = {
  0: "bg-zinc-100 border-zinc-300 text-zinc-500",
  1: "bg-red-500 border-red-600 text-white",
  2: "bg-emerald-500 border-emerald-600 text-white",
  3: "bg-blue-500 border-blue-600 text-white",
  4: "bg-amber-400 border-amber-500 text-zinc-950",
  5: "bg-white border-zinc-400 text-zinc-900",
}

const ledNames: Record<number, string> = {
  0: "off",
  1: "red",
  2: "green",
  3: "blue",
  4: "amber",
  5: "white",
}

type Props = {
  ledColours: Record<string, number>
}

export function LedGrid({ ledColours }: Props) {
  return (
    <Card className="min-w-0">
      <CardHeader>
        <CardTitle>LED State</CardTitle>
        <Circle className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-4 gap-2">
          {Array.from({ length: 16 }, (_, index) => {
            const colour = ledColours[String(index)] ?? 0
            return (
              <div
                key={index}
                className={cn(
                  "flex aspect-square min-h-14 flex-col items-center justify-center rounded-md border text-xs font-medium",
                  ledStyles[colour] ?? ledStyles[0],
                )}
              >
                <span className="text-base font-semibold">{index}</span>
                <span className="uppercase opacity-80">{ledNames[colour] ?? colour}</span>
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}
