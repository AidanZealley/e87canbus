import { createFileRoute } from "@tanstack/react-router"

import { SimulatorWorkbench } from "@/components/simulator-workbench"

export const Route = createFileRoute("/dev/")({
  component: SimulatorWorkbench,
})
