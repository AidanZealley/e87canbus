import { createFileRoute } from "@tanstack/react-router"

import { CarSettings } from "@/components/car-settings"

export const Route = createFileRoute("/car/settings/")({
  component: CarSettings,
})
