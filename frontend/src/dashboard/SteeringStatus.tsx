import { Gauge } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { ApplicationSnapshot } from "@/simulator/types"

type Props = {
  application?: ApplicationSnapshot
}

export function SteeringStatus({ application }: Props) {
  if (!application) {
    return (
      <Card className="min-w-0">
        <CardHeader>
          <CardTitle>Steering Assist</CardTitle>
          <Gauge className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Application state unavailable. Restart the simulator backend.
        </CardContent>
      </Card>
    )
  }

  const isAuto = application.steering_mode === "auto"

  return (
    <Card className="min-w-0">
      <CardHeader>
        <CardTitle>Steering Assist</CardTitle>
        <Gauge className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent className="grid gap-3">
        <div className="flex items-center justify-between rounded-md border bg-muted/30 p-3">
          <span className="text-sm text-muted-foreground">Mode</span>
          <Badge className={isAuto ? "bg-blue-600 text-white" : "bg-amber-400 text-zinc-950"}>
            {isAuto ? "Auto" : "Manual"}
          </Badge>
        </div>
        <div className="grid grid-cols-2 gap-2 text-sm">
          <StatusValue label="Vehicle speed" value={`${application.vehicle_speed_kph.toFixed(1)} km/h`} />
          <StatusValue label="Manual level" value={String(application.manual_assistance_level)} />
        </div>
        <p className="text-xs text-muted-foreground">Press NeoTrellis button 0 to change mode.</p>
      </CardContent>
    </Card>
  )
}

function StatusValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border p-2">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 font-semibold">{value}</div>
    </div>
  )
}
