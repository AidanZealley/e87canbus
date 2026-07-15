import { useEffect, useMemo, useState } from "react"
import type { TraceRow } from "@/api/live-events"

import { CanTraceTable } from "./components/can-trace-table/CanTraceTable"
import { FrameDetail } from "./components/frame-detail/FrameDetail"
import { useLiveStore } from "@/live/live-store"
import { useTraceStore } from "@/live/trace-store"
import { subscribeLiveTrace } from "@/live/transport"
type CanNetwork = TraceRow["network"]

const allNetworks: CanNetwork[] = ["kcan", "ptcan", "fcan"]

export const SimulatorTrace = () => {
  const trace = useTraceStore((state) => state.rows)
  const networks = useLiveStore((state) => state.devices.networks)
  const synchronized = useLiveStore((state) => state.connection.synchronized)
  const displayedNetworks = synchronized ? networks : []
  useEffect(() => subscribeLiveTrace(), [])
  const [selectedSequence, setSelectedSequence] = useState<number | null>(null)
  const [selectedNetworks, setSelectedNetworks] = useState<Set<CanNetwork>>(
    new Set(allNetworks)
  )

  const visibleTrace = useMemo(
    () => trace.filter((entry) => selectedNetworks.has(entry.network)),
    [selectedNetworks, trace]
  )
  const selectedFrame =
    visibleTrace.find((entry) => entry.sequence === selectedSequence) ?? null
  const detailFrame = selectedFrame ?? visibleTrace.at(-1) ?? null

  const toggleNetwork = (network: CanNetwork) => {
    const next = new Set(selectedNetworks)
    if (next.has(network)) next.delete(network)
    else next.add(network)

    const nextVisible = trace.filter((entry) => next.has(entry.network))
    if (
      selectedSequence !== null &&
      !nextVisible.some((entry) => entry.sequence === selectedSequence)
    ) {
      setSelectedSequence(null)
    }
    setSelectedNetworks(next)
  }

  return (
    <section className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
      <CanTraceTable
        trace={visibleTrace}
        totalCount={trace.length}
        networks={displayedNetworks}
        selectedNetworks={selectedNetworks}
        selected={selectedFrame}
        onSelect={(entry: TraceRow) => setSelectedSequence(entry.sequence)}
        onToggleNetwork={toggleNetwork}
      />
      <FrameDetail frame={detailFrame} />
    </section>
  )
}
