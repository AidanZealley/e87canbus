import { CircleIcon } from "lucide-react"

import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { cn } from "@/lib/utils"

const ledStyles: Record<number, string> = {
  0: "border-[var(--led-off-border)] bg-[var(--led-off)] text-muted-foreground",
  1: "border-[var(--led-red-border)] bg-[var(--led-red)] text-[var(--led-on-foreground)]",
  2: "border-[var(--led-green-border)] bg-[var(--led-green)] text-[var(--led-on-foreground)]",
  3: "border-[var(--led-blue-border)] bg-[var(--led-blue)] text-[var(--led-on-foreground)]",
  4: "border-[var(--led-amber-border)] bg-[var(--led-amber)] text-[var(--led-dark-foreground)]",
  5: "border-[var(--led-white-border)] bg-[var(--led-white)] text-[var(--led-dark-foreground)]",
}

const ledNames: Record<number, string> = {
  0: "off",
  1: "red",
  2: "green",
  3: "blue",
  4: "amber",
  5: "white",
}

type LedGridProps = {
  ledColours: Record<string, number>
}

export const LedGrid = ({ ledColours }: LedGridProps) => (
  <Card className="min-w-0">
    <CardHeader>
      <CardTitle>LED state</CardTitle>
      <CardDescription>Virtual node output by button index</CardDescription>
      <CardAction>
        <CircleIcon aria-hidden="true" />
      </CardAction>
    </CardHeader>

    <CardContent>
      <div className="grid grid-cols-4 gap-2">
        {Array.from({ length: 16 }, (_, index) => {
          const colour = ledColours[String(index)] ?? 0
          const name = ledNames[colour] ?? `code ${colour}`

          return (
            <div
              key={index}
              title={`LED ${index}: ${name}`}
              className={cn(
                "flex aspect-square min-h-14 flex-col items-center justify-center rounded-md border text-xs font-medium shadow-xs",
                ledStyles[colour] ?? ledStyles[0]
              )}
            >
              <span className="font-heading text-base font-semibold">
                {index}
              </span>
              <span className="uppercase opacity-80">{name}</span>
            </div>
          )
        })}
      </div>
    </CardContent>

    <CardFooter>
      <p className="text-xs text-muted-foreground">
        Blue indicates Auto; amber indicates Manual.
      </p>
    </CardFooter>
  </Card>
)
