import { useEffect, useRef } from "react"
import { RadioTowerIcon } from "lucide-react"

import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { CanTraceEntry } from "../../types"
import { decodeMeaning } from "./utils"

type CanTraceTableProps = {
  trace: CanTraceEntry[]
  selected: CanTraceEntry | null
  autoScroll: boolean
  onSelect: (entry: CanTraceEntry) => void
}

export const CanTraceTable = ({
  trace,
  selected,
  autoScroll,
  onSelect,
}: CanTraceTableProps) => {
  const scrollAreaRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const viewport = scrollAreaRef.current?.querySelector<HTMLElement>(
      "[data-slot='scroll-area-viewport']"
    )

    if (autoScroll && viewport) viewport.scrollTop = viewport.scrollHeight
  }, [autoScroll, trace.length])

  return (
    <Card className="min-w-0">
      <CardHeader>
        <CardTitle>CAN trace</CardTitle>
        <CardDescription>Coordinator and button-pad traffic</CardDescription>
        <CardAction>
          <RadioTowerIcon aria-hidden="true" />
        </CardAction>
      </CardHeader>

      <CardContent>
        {trace.length > 0 ? (
          <ScrollArea
            ref={scrollAreaRef}
            className="h-[360px] rounded-md border"
          >
            <Table>
              <TableHeader className="sticky top-0 bg-card">
                <TableRow>
                  <TableHead className="w-24">Time</TableHead>
                  <TableHead className="w-24">Source</TableHead>
                  <TableHead className="w-20">ID</TableHead>
                  <TableHead className="w-28">Data</TableHead>
                  <TableHead>Decoded</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {trace.map((entry, index) => (
                  <TableRow
                    key={`${entry.monotonic_s}-${entry.source}-${entry.data_hex}-${index}`}
                    data-state={selected === entry ? "selected" : undefined}
                    className="cursor-pointer"
                    onClick={() => onSelect(entry)}
                  >
                    <TableCell className="font-mono text-xs">
                      {entry.monotonic_s.toFixed(3)}
                    </TableCell>
                    <TableCell>{entry.source}</TableCell>
                    <TableCell className="font-mono">
                      {entry.arbitration_id_hex}
                    </TableCell>
                    <TableCell className="font-mono">
                      {entry.data_hex || "--"}
                    </TableCell>
                    <TableCell>{decodeMeaning(entry)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </ScrollArea>
        ) : (
          <Empty className="min-h-[360px] border">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <RadioTowerIcon />
              </EmptyMedia>
              <EmptyTitle>No frames captured</EmptyTitle>
              <EmptyDescription>
                Press a NeoTrellis key or run a simulator step to populate the
                trace.
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        )}
      </CardContent>

      <CardFooter>
        <p className="text-xs text-muted-foreground">
          {trace.length} {trace.length === 1 ? "frame" : "frames"} captured
        </p>
      </CardFooter>
    </Card>
  )
}
