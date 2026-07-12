import { useEffect, useRef } from "react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import type { CanTraceEntry } from "@/simulator/types"
import { cn } from "@/lib/utils"

type Props = {
  trace: CanTraceEntry[]
  selected: CanTraceEntry | null
  autoScroll: boolean
  onSelect: (entry: CanTraceEntry) => void
}

function decodeMeaning(entry: CanTraceEntry) {
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

export function CanTraceTable({ trace, selected, autoScroll, onSelect }: Props) {
  const viewportRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const viewport = viewportRef.current
    if (autoScroll && viewport) {
      viewport.scrollTop = viewport.scrollHeight
    }
  }, [autoScroll, trace.length])

  return (
    <Card className="min-w-0">
      <CardHeader>
        <CardTitle>CAN Trace</CardTitle>
        <span className="text-xs text-muted-foreground">{trace.length} frames</span>
      </CardHeader>
      <CardContent>
        <ScrollArea viewportRef={viewportRef} className="h-[360px] rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-24">Time</TableHead>
                <TableHead className="w-24">Source</TableHead>
                <TableHead className="w-20">ID</TableHead>
                <TableHead className="w-24">Data</TableHead>
                <TableHead>Decoded</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {trace.map((entry, index) => {
                const isSelected = selected === entry
                return (
                  <TableRow
                    key={`${entry.monotonic_s}-${entry.source}-${entry.data_hex}-${index}`}
                    className={cn("cursor-pointer", isSelected && "bg-muted")}
                    onClick={() => onSelect(entry)}
                  >
                    <TableCell className="font-mono text-xs">{entry.monotonic_s.toFixed(3)}</TableCell>
                    <TableCell>{entry.source}</TableCell>
                    <TableCell className="font-mono">{entry.arbitration_id_hex}</TableCell>
                    <TableCell className="font-mono">{entry.data_hex || "--"}</TableCell>
                    <TableCell>{decodeMeaning(entry)}</TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
