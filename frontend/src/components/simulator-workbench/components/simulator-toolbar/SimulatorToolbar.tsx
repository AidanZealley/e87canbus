import { RefreshCcwIcon, StepForwardIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { ConnectionBadge } from "../connection-badge"

type SimulatorToolbarProps = {
  connected: boolean
  autoScroll: boolean
  onAutoScrollChange: (enabled: boolean) => void
  onReset: () => void
  onStep: () => void
}

export const SimulatorToolbar = ({
  connected,
  autoScroll,
  onAutoScrollChange,
  onReset,
  onStep,
}: SimulatorToolbarProps) => (
  <header className="sticky top-0 border-b bg-background/95 backdrop-blur-sm">
    <div className="mx-auto flex min-h-14 w-full max-w-[1600px] flex-wrap items-center justify-between gap-3 px-4 py-2 lg:px-6">
      <div className="flex items-center gap-3">
        <div className="flex flex-col">
          <h1 className="font-heading text-sm font-semibold tracking-wide">
            E87 CAN Simulator
          </h1>
          <p className="hidden text-xs text-muted-foreground sm:block">
            Hardware-free control workbench
          </p>
        </div>
        <ConnectionBadge connected={connected} />
      </div>

      <div className="flex items-center gap-2">
        <label className="flex items-center gap-2 text-xs text-muted-foreground">
          <Switch
            checked={autoScroll}
            onCheckedChange={onAutoScrollChange}
            aria-label="Auto-scroll CAN trace"
          />
          Auto-scroll
        </label>
        <Button variant="outline" size="sm" onClick={onStep}>
          <StepForwardIcon data-icon="inline-start" />
          Step
        </Button>
        <Button variant="outline" size="sm" onClick={onReset}>
          <RefreshCcwIcon data-icon="inline-start" />
          Reset
        </Button>
      </div>
    </div>
  </header>
)
