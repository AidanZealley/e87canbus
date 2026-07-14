import { useMemo, useState } from "react"

import { CanTraceTable } from "./components/can-trace-table"
import { FrameDetail } from "./components/frame-detail"
import { useNetworks, useTrace } from "./query"
import type { CanNetwork, CanTraceEntry } from "./types"

const allNetworks: CanNetwork[] = ["kcan", "ptcan", "fcan"]

type SimulatorTraceProps = {
  autoScroll: boolean
}

export const SimulatorTrace = ({ autoScroll }: SimulatorTraceProps) => {
  const trace = useTrace()
  const networks = useNetworks()
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
        networks={networks}
        selectedNetworks={selectedNetworks}
        selected={selectedFrame}
        autoScroll={autoScroll}
        onSelect={(entry: CanTraceEntry) => setSelectedSequence(entry.sequence)}
        onToggleNetwork={toggleNetwork}
      />
      <FrameDetail frame={detailFrame} />
    </section>
  )
}
