import { createFileRoute } from "@tanstack/react-router"

import { CarDrive } from "@/components/car-drive"

export const Route = createFileRoute("/")({
  component: CarDrive,
})
