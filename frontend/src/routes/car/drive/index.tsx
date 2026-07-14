import { createFileRoute } from "@tanstack/react-router"

export const Route = createFileRoute("/car/drive/")({
  component: DrivePlaceholder,
})

function DrivePlaceholder() {
  return (
    <section className="p-5">
      <p className="text-xs font-medium tracking-widest text-muted-foreground uppercase">
        Car display
      </p>
      <h1 className="mt-1 text-2xl font-semibold">Drive</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Drive telemetry will be added in a later phase.
      </p>
    </section>
  )
}
