import { CarFrontIcon, WrenchIcon } from "lucide-react"
import { Link, createFileRoute } from "@tanstack/react-router"

export const Route = createFileRoute("/")({
  component: ModeChooser,
})

function ModeChooser() {
  return (
    <main className="grid min-h-svh bg-background md:grid-cols-2">
      <Link
        to="/dev"
        className="group flex min-h-64 flex-col items-center justify-center gap-5 border-b p-8 text-center transition-colors outline-none hover:bg-muted/60 focus-visible:z-10 focus-visible:ring-4 focus-visible:ring-ring/40 md:border-r md:border-b-0"
      >
        <span className="rounded-2xl border bg-card p-5 text-card-foreground shadow-sm transition-transform group-hover:-translate-y-1">
          <WrenchIcon className="size-10" aria-hidden="true" />
        </span>
        <span>
          <span className="block text-2xl font-semibold">
            Development Workbench
          </span>
          <span className="mt-2 block max-w-sm text-sm text-muted-foreground">
            Inspect and control the hardware-free CAN simulator.
          </span>
        </span>
      </Link>
      <Link
        to="/car"
        className="group flex min-h-64 flex-col items-center justify-center gap-5 p-8 text-center transition-colors outline-none hover:bg-muted/60 focus-visible:z-10 focus-visible:ring-4 focus-visible:ring-ring/40"
      >
        <span className="rounded-2xl border bg-card p-5 text-card-foreground shadow-sm transition-transform group-hover:-translate-y-1">
          <CarFrontIcon className="size-10" aria-hidden="true" />
        </span>
        <span>
          <span className="block text-2xl font-semibold">Car Display</span>
          <span className="mt-2 block max-w-sm text-sm text-muted-foreground">
            Open the focused in-car control centre shell.
          </span>
        </span>
      </Link>
    </main>
  )
}
