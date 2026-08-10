import { Link, createRootRoute } from "@tanstack/react-router"

import { CarLayout } from "@/components/car-layout"
import { buttonVariants } from "@/components/ui/button"

export const Route = createRootRoute({
  component: CarLayout,
  notFoundComponent: NotFound,
})

function NotFound() {
  return (
    <section className="flex h-full items-center justify-center p-6">
      <div className="w-full max-w-md rounded-xl border bg-card p-6 text-card-foreground shadow-sm">
        <p className="text-xs font-medium tracking-widest text-muted-foreground uppercase">
          404
        </p>
        <h1 className="mt-2 text-2xl font-semibold">Route not found</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          No console view matches this address.
        </p>
        <Link to="/" className={`${buttonVariants()} mt-5`}>
          Return to drive
        </Link>
      </div>
    </section>
  )
}
