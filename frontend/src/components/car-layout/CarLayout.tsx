import {
  GaugeIcon,
  HouseIcon,
  SettingsIcon,
  SlidersHorizontalIcon,
} from "lucide-react"
import { Link, Outlet } from "@tanstack/react-router"

import { buttonVariants } from "@/components/ui/button"
import { cn } from "@/lib/utils"
// import { CarStatusBanners } from "./CarStatusBanners"

const navigation = [
  { to: "/car", label: "Overview", icon: HouseIcon },
  { to: "/car/drive", label: "Drive", icon: GaugeIcon },
  { to: "/car/steering", label: "Steering", icon: SlidersHorizontalIcon },
  { to: "/car/settings", label: "Settings", icon: SettingsIcon },
] as const

export const CarLayout = () => (
  <div className="flex h-svh min-w-0 overflow-hidden bg-background text-foreground">
    <aside className="flex w-12 shrink-0 flex-col">
      <nav
        className="flex flex-1 flex-col items-center justify-center gap-2 py-3"
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
              "size-10 rounded-lg data-[status=active]:bg-secondary [&_svg:not([class*='size-'])]:size-5"
            )}
          >
            <Icon aria-hidden="true" />
            <span className="sr-only">{label}</span>
          </Link>
        ))}
      </nav>
    </aside>
    <div className="flex min-w-0 flex-1 flex-col py-1 pr-1">
      {/* <CarStatusBanners /> */}
      <main className="min-h-0 min-w-0 flex-1 overflow-auto rounded-lg border bg-muted/20">
        <Outlet />
      </main>
    </div>
  </div>
)
