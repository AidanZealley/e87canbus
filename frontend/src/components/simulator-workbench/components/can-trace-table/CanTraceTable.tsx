import { useCallback, useEffect, useRef, useState } from "react"
import { useVirtualizer } from "@tanstack/react-virtual"
import { ArrowDownIcon, RadioTowerIcon } from "lucide-react"
import type { DevicesState, TraceRow } from "@/api/live-events"

import { Button } from "@/components/ui/button"
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
import { NetworkFilters } from "../network-filters"
import { decodeMeaning } from "./utils"

type CanNetwork = TraceRow["network"]
type NetworkStatus = DevicesState["networks"][number]

const TRACE_ROW_HEIGHT_PX = 32
const TRACE_ROW_OVERSCAN = 12

type CanTraceTableProps = {
  trace: TraceRow[]
  totalCount: number
  networks: NetworkStatus[]
  selectedNetworks: Set<CanNetwork>
  selected: TraceRow | null
  autoScroll: boolean
  onSelect: (entry: TraceRow) => void
  onToggleNetwork: (network: CanNetwork) => void
}

export const CanTraceTable = ({
  trace,
  totalCount,
  networks,
  selectedNetworks,
  selected,
  autoScroll,
  onSelect,
  onToggleNetwork,
}: CanTraceTableProps) => {
  const scrollAreaRef = useRef<HTMLDivElement | null>(null)
  const latestIndexRef = useRef(-1)
  const scrollAnimationFrameRef = useRef<number | null>(null)
  const ignoreScrollUntilRef = useRef(0)
  const followingLatestRef = useRef(true)
  const [isFollowingLatest, setIsFollowingLatest] = useState(true)
  // TanStack Virtual manages a mutable external store; React Compiler must not memoize it.
  // eslint-disable-next-line react-hooks/incompatible-library
  const rowVirtualizer = useVirtualizer({
    count: trace.length,
    getScrollElement: () =>
      scrollAreaRef.current?.querySelector<HTMLElement>(
        "[data-slot='scroll-area-viewport']"
      ) ?? null,
    estimateSize: () => TRACE_ROW_HEIGHT_PX,
    getItemKey: (index) => trace[index]?.sequence ?? index,
    overscan: TRACE_ROW_OVERSCAN,
    initialRect: { width: 1_000, height: 360 },
  })
  const virtualRows = rowVirtualizer.getVirtualItems()
  const firstVirtualRow = virtualRows[0]
  const lastVirtualRow = virtualRows.at(-1)
  const paddingTop = firstVirtualRow?.start ?? 0
  const paddingBottom = lastVirtualRow
    ? rowVirtualizer.getTotalSize() - lastVirtualRow.end
    : 0
  const latestSequence = trace.at(-1)?.sequence
  const hasTrace = trace.length > 0
  const showLatest = !autoScroll || !isFollowingLatest
  latestIndexRef.current = trace.length - 1
  const scrollToLatest = useCallback(() => {
    const scroll = () => {
      if (latestIndexRef.current >= 0) {
        rowVirtualizer.scrollToIndex(latestIndexRef.current, { align: "end" })
      }
    }
    ignoreScrollUntilRef.current = Date.now() + 100
    scroll()
    if (scrollAnimationFrameRef.current !== null) {
      cancelAnimationFrame(scrollAnimationFrameRef.current)
    }
    scrollAnimationFrameRef.current = requestAnimationFrame(scroll)
  }, [rowVirtualizer])

  useEffect(() => {
    if (!hasTrace) {
      followingLatestRef.current = true
      const animationFrame = requestAnimationFrame(() =>
        setIsFollowingLatest(true)
      )
      return () => cancelAnimationFrame(animationFrame)
    }

    const viewport = scrollAreaRef.current?.querySelector<HTMLElement>(
      "[data-slot='scroll-area-viewport']"
    )
    if (!viewport) return

    const handleScroll = () => {
      const distanceFromBottom =
        viewport.scrollHeight - viewport.clientHeight - viewport.scrollTop
      const isAtBottom = distanceFromBottom <= 2
      if (Date.now() < ignoreScrollUntilRef.current && !isAtBottom) return
      followingLatestRef.current = isAtBottom
      setIsFollowingLatest(isAtBottom)
    }
    const handleWheel = (event: WheelEvent) => {
      if (event.deltaY >= 0) return
      ignoreScrollUntilRef.current = 0
      followingLatestRef.current = false
      setIsFollowingLatest(false)
    }
    viewport.addEventListener("scroll", handleScroll, { passive: true })
    viewport.addEventListener("wheel", handleWheel, { passive: true })
    return () => {
      viewport.removeEventListener("scroll", handleScroll)
      viewport.removeEventListener("wheel", handleWheel)
    }
  }, [hasTrace])

  useEffect(() => {
    if (autoScroll && followingLatestRef.current) scrollToLatest()
  }, [autoScroll, latestSequence, scrollToLatest])

  useEffect(
    () => () => {
      if (scrollAnimationFrameRef.current !== null) {
        cancelAnimationFrame(scrollAnimationFrameRef.current)
      }
    },
    []
  )

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
        <div className="mb-3">
          <NetworkFilters
            networks={networks}
            selected={selectedNetworks}
            onToggle={onToggleNetwork}
          />
        </div>
        {trace.length > 0 ? (
          <div className="relative">
            <ScrollArea ref={scrollAreaRef} className="h-90 rounded-md border">
              <Table>
                <TableHeader className="sticky top-0 bg-card">
                  <TableRow>
                    <TableHead className="w-24">Time</TableHead>
                    <TableHead className="w-20">Network</TableHead>
                    <TableHead className="w-24">Source</TableHead>
                    <TableHead className="w-20">ID</TableHead>
                    <TableHead className="w-28">Data</TableHead>
                    <TableHead>Decoded</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody className="[&_td]:h-8 [&_td]:py-0">
                  {paddingTop > 0 ? <TraceSpacer height={paddingTop} /> : null}
                  {virtualRows.map((virtualRow) => {
                    const entry = trace[virtualRow.index]
                    if (entry === undefined) return null
                    return (
                      <TableRow
                        key={entry.sequence}
                        data-index={virtualRow.index}
                        data-state={
                          selected?.sequence === entry.sequence
                            ? "selected"
                            : undefined
                        }
                        className="h-8 cursor-pointer transition-none"
                        onClick={() => onSelect(entry)}
                      >
                        <TableCell className="font-mono text-xs">
                          {entry.monotonic_s.toFixed(3)}
                        </TableCell>
                        <TableCell className="font-medium uppercase">
                          {entry.network.replace("can", "-CAN")}
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
                    )
                  })}
                  {paddingBottom > 0 ? (
                    <TraceSpacer height={paddingBottom} />
                  ) : null}
                </TableBody>
              </Table>
            </ScrollArea>
            <Button
              type="button"
              variant="secondary"
              aria-label="Jump to latest CAN frame"
              aria-hidden={!showLatest}
              tabIndex={showLatest ? 0 : -1}
              className={`absolute bottom-3 left-1/2 z-10 -translate-x-1/2 shadow-md transition-opacity duration-200 ${
                showLatest ? "opacity-100" : "pointer-events-none opacity-0"
              }`}
              onClick={() => {
                followingLatestRef.current = true
                setIsFollowingLatest(true)
                scrollToLatest()
              }}
            >
              <ArrowDownIcon data-icon="inline-start" />
              Latest
            </Button>
          </div>
        ) : (
          <Empty className="min-h-90 border">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <RadioTowerIcon />
              </EmptyMedia>
              <EmptyTitle>No frames captured</EmptyTitle>
              <EmptyDescription>
                Press a button-pad emulator key to populate the trace.
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        )}
      </CardContent>

      <CardFooter>
        <p className="text-xs text-muted-foreground">
          {trace.length} {trace.length === 1 ? "frame" : "frames"} captured
          {trace.length !== totalCount ? ` · ${totalCount} total` : ""}
        </p>
      </CardFooter>
    </Card>
  )
}

const TraceSpacer = ({ height }: { height: number }) => (
  <TableRow aria-hidden="true" className="border-0 hover:bg-transparent">
    <TableCell colSpan={6} className="p-0" style={{ height }} />
  </TableRow>
)
