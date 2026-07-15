import { createFileRoute } from "@tanstack/react-router"

import { CarSteeringEditor } from "@/components/car-steering-editor"

export const Route = createFileRoute("/car/steering/")({
  component: CarSteeringEditor,
})
