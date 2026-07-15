import { Button } from "@/components/ui/button"
import type { DevicesState, TraceRow } from "@/api/live-events"

type CanNetwork = TraceRow["network"]
type NetworkStatus = DevicesState["networks"][number]

type NetworkFiltersProps = {
  networks: NetworkStatus[]
  selected: Set<CanNetwork>
  onToggle: (network: CanNetwork) => void
}

export const NetworkFilters = ({
  networks,
  selected,
  onToggle,
}: NetworkFiltersProps) => (
  <div className="flex flex-wrap items-center gap-1" aria-label="CAN network filters">
    {networks.map((network) => {
      const active = selected.has(network.id)
      return (
        <Button
          key={network.id}
          type="button"
          size="sm"
          variant={active ? "default" : "outline"}
          aria-pressed={active}
          onClick={() => onToggle(network.id)}
        >
          {network.label}
        </Button>
      )
    })}
  </div>
)
