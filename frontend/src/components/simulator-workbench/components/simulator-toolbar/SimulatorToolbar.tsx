import { HomeIcon, RefreshCcwIcon } from "lucide-react"
import { Link } from "@tanstack/react-router"

import { ModeToggle } from "@/components/mode-toggle"
import { Button, buttonVariants } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { cn } from "@/lib/utils"
import { ConnectionBadge } from "../connection-badge"
import type { LiveConnectionStatus } from "@/live/live-store"

type SimulatorToolbarProps = {
  connectionState: LiveConnectionStatus
  autoScroll: boolean
  onAutoScrollChange: (enabled: boolean) => void
  onReset: () => void
  resetPending?: boolean
}

export const SimulatorToolbar = ({
  connectionState,
  autoScroll,
  onAutoScrollChange,
  onReset,
  resetPending = false,
}: SimulatorToolbarProps) => (
  <header className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur-sm">
    <div className="mx-auto flex min-h-14 w-full max-w-[1600px] flex-wrap items-center justify-between gap-3 px-4 py-2 lg:px-6">
      <div className="flex items-center gap-3">
        <Link
          to="/"
          aria-label="Back to mode chooser"
          title="Mode chooser"
          className={cn(buttonVariants({ variant: "ghost", size: "icon" }))}
        >
          <HomeIcon />
        </Link>
        <div className="flex flex-col">
          <h1 className="font-heading text-sm font-semibold tracking-wide">
            E87 CAN Simulator
          </h1>
          <p className="hidden text-xs text-muted-foreground sm:block">
            Hardware-free control workbench
          </p>
        </div>
        <ConnectionBadge connectionState={connectionState} />
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
        <Button
          variant="outline"
          size="sm"
          disabled={resetPending}
          onClick={onReset}
        >
          <RefreshCcwIcon data-icon="inline-start" />
          Reset
        </Button>
        <ModeToggle />
      </div>
    </div>
  </header>
)
