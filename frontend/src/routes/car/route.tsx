import {
  GaugeIcon,
  HouseIcon,
  SettingsIcon,
  SlidersHorizontalIcon,
} from "lucide-react"
import { Link, Outlet, createFileRoute } from "@tanstack/react-router"

import { buttonVariants } from "@/components/ui/button"
import { cn } from "@/lib/utils"

const navigation = [
  { to: "/car", label: "Overview", icon: HouseIcon },
  { to: "/car/drive", label: "Drive", icon: GaugeIcon },
  { to: "/car/steering", label: "Steering", icon: SlidersHorizontalIcon },
  { to: "/car/settings", label: "Settings", icon: SettingsIcon },
] as const

export const Route = createFileRoute("/car")({
  component: CarLayout,
})

function CarLayout() {
  return (
    <div className="flex h-svh min-w-0 overflow-hidden bg-background text-foreground">
      <aside className="flex w-14 shrink-0 flex-col border-r bg-sidebar text-sidebar-foreground">
        <nav
          className="flex flex-1 flex-col items-center justify-center gap-3 py-3"
          aria-label="Car display"
        >
          {navigation.map(({ to, label, icon: Icon }) => (
            <Link
              key={to}
              to={to}
              activeOptions={{ exact: true }}
              aria-label={label}
              title={label}
              className={cn(
                buttonVariants({ variant: "ghost", size: "icon-lg" }),
                "text-sidebar-foreground focus-visible:ring-sidebar-ring/40 data-[status=active]:bg-sidebar-primary data-[status=active]:text-sidebar-primary-foreground"
              )}
            >
              <Icon aria-hidden="true" />
              <span className="sr-only">{label}</span>
            </Link>
          ))}
        </nav>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="h-2 shrink-0 border-b bg-muted/30" aria-hidden="true" />
        <main className="min-h-0 min-w-0 flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
