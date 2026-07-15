import { createFileRoute } from "@tanstack/react-router"

import { CarLayout } from "@/components/car-layout"

export const Route = createFileRoute("/car")({
  component: CarLayout,
})
