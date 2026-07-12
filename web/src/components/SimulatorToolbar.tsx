import { RefreshCcw, StepForward } from "lucide-react"

import { ConnectionBadge } from "@/components/ConnectionBadge"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"

type Props = {
  connected: boolean
  autoScroll: boolean
  onAutoScrollChange: (enabled: boolean) => void
  onReset: () => void
  onStep: () => void
}

export function SimulatorToolbar({ connected, autoScroll, onAutoScrollChange, onReset, onStep }: Props) {
  return (
    <header className="flex min-h-14 flex-wrap items-center justify-between gap-3 border-b bg-background px-4 py-2">
      <div className="flex items-center gap-3">
        <h1 className="text-base font-semibold">E87 CAN Simulator</h1>
        <ConnectionBadge connected={connected} />
      </div>
      <div className="flex items-center gap-2">
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          <Switch checked={autoScroll} onCheckedChange={onAutoScrollChange} />
          Auto-scroll
        </label>
        <Button variant="outline" size="sm" onClick={onStep}>
          <StepForward className="mr-2 h-4 w-4" />
          Step
        </Button>
        <Button variant="outline" size="sm" onClick={onReset}>
          <RefreshCcw className="mr-2 h-4 w-4" />
          Reset
        </Button>
      </div>
    </header>
  )
}
