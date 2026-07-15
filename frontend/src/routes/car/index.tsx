import { createFileRoute } from "@tanstack/react-router"

import { CarOverview } from "@/components/car-overview"

export const Route = createFileRoute("/car/")({
  component: CarOverview,
})
