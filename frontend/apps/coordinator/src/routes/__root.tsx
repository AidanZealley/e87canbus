import {
  Link,
  Outlet,
  createRootRoute,
} from "@tanstack/react-router"

import { buttonVariants } from "@/components/ui/button"
import { SimulatedVehiclePopover } from "@/components/simulated-vehicle-popover"

export const Route = createRootRoute({
  component: RootLayout,
  notFoundComponent: NotFound,
})

function RootLayout() {
  return (
    <>
      <Outlet />
      <SimulatedVehiclePopover />
    </>
  )
}

function NotFound() {
  return (
    <main className="flex min-h-svh items-center justify-center bg-muted/30 p-6">
      <section className="w-full max-w-md rounded-xl border bg-card p-6 text-card-foreground shadow-sm">
        <p className="text-xs font-medium tracking-widest text-muted-foreground uppercase">
          404
        </p>
        <h1 className="mt-2 text-2xl font-semibold">Route not found</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          No application view matches this address.
        </p>
        <div className="mt-5 flex flex-wrap gap-2">
          <Link to="/" className={buttonVariants()}>
            Development workbench
          </Link>
        </div>
      </section>
    </main>
  )
}
