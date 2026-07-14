import { createFileRoute } from "@tanstack/react-router"

import { CarSettingsForm } from "@/components/car-settings-form"

export const Route = createFileRoute("/car/settings/")({
  component: CarSettingsForm,
})
