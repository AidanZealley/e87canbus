import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

type SettingsGroupProps = {
  title: string
  description?: string
  className?: string
  children: ReactNode
}

export const SettingsGroup = ({
  title,
  description,
  className,
  children,
}: SettingsGroupProps) => (
  <section className={cn("grid content-start gap-4", className)}>
    <div className="grid gap-0.5">
      <h2 className="font-heading text-sm font-medium">{title}</h2>
      {description === undefined ? null : (
        <p className="text-xs text-muted-foreground">{description}</p>
      )}
    </div>
    <div className="grid gap-6">{children}</div>
  </section>
)
