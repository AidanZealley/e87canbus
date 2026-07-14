import { createFileRoute } from "@tanstack/react-router"

export const Route = createFileRoute("/car/settings/")({
  component: SettingsPlaceholder,
})

function SettingsPlaceholder() {
  return (
    <section className="p-5">
      <p className="text-xs font-medium tracking-widest text-muted-foreground uppercase">
        Car display
      </p>
      <h1 className="mt-1 text-2xl font-semibold">Settings</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Display settings will be added in a later phase.
      </p>
    </section>
  )
}
