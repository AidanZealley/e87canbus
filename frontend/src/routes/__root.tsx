import {
  Link,
  Outlet,
  createRootRoute,
  useLocation,
} from "@tanstack/react-router"

import { buttonVariants } from "@/components/ui/button"
import { SimulatedVehiclePopover } from "@/components/simulated-vehicle-popover/SimulatedVehiclePopover"
import { cn } from "@/lib/utils"

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
  const pathname = useLocation({ select: (location) => location.pathname })
  const isCarPath = pathname.startsWith("/car/")

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
          {isCarPath ? (
            <Link to="/car" className={buttonVariants()}>
              Return to car overview
            </Link>
          ) : (
            <>
              <Link to="/" className={buttonVariants()}>
                Mode chooser
              </Link>
              <Link
                to="/dev"
                className={cn(buttonVariants({ variant: "outline" }))}
              >
                Development workbench
              </Link>
            </>
          )}
        </div>
      </section>
    </main>
  )
}
