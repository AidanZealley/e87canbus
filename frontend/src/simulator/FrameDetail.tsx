import { Info } from "lucide-react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import type { CanTraceEntry } from "@/simulator/types"

type Props = {
  frame: CanTraceEntry | null
}

export function FrameDetail({ frame }: Props) {
  return (
    <Card className="min-w-0">
      <CardHeader>
        <CardTitle>Frame Detail</CardTitle>
        <Info className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        {frame ? (
          <div className="grid gap-2 text-sm">
            <Detail label="Source" value={frame.source} />
            <Detail label="Arbitration ID" value={`${frame.arbitration_id_hex} (${frame.arbitration_id})`} />
            <Detail label="Extended" value={frame.is_extended_id ? "true" : "false"} />
            <Detail label="Data hex" value={frame.data_hex || "--"} />
            <Separator />
            <div className="grid gap-1">
              <span className="text-xs font-medium text-muted-foreground">Payload bytes</span>
              <div className="flex flex-wrap gap-1">
                {(frame.data_hex.match(/.{1,2}/g) ?? []).map((byte, index) => (
                  <span key={`${byte}-${index}`} className="rounded-sm border bg-muted px-2 py-1 font-mono text-xs">
                    {byte}
                  </span>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="text-sm text-muted-foreground">Select a trace row.</div>
        )}
      </CardContent>
    </Card>
  )
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[110px_minmax(0,1fr)] gap-2">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <span className="min-w-0 break-words font-mono text-xs">{value}</span>
    </div>
  )
}
