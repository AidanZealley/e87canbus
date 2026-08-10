import { createFileRoute } from "@tanstack/react-router"

import { CarButtons } from "@/components/car-buttons"

export const Route = createFileRoute("/buttons/")({
  component: CarButtons,
})
