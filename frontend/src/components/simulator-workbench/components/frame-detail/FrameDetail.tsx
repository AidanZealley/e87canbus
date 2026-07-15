import { InfoIcon, ScanSearchIcon } from "lucide-react"

import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { Separator } from "@/components/ui/separator"
import type { TraceRow } from "@/api/live-events"

type FrameDetailProps = {
  frame: TraceRow | null
}

export const FrameDetail = ({ frame }: FrameDetailProps) => (
  <Card className="min-w-0">
    <CardHeader>
      <CardTitle>Frame detail</CardTitle>
      <CardDescription>Selected trace payload</CardDescription>
      <CardAction>
        <InfoIcon aria-hidden="true" />
      </CardAction>
    </CardHeader>

    <CardContent>
      {frame ? (
        <div className="flex flex-col gap-3 text-xs">
          <dl className="flex flex-col gap-2">
            <div className="grid grid-cols-[110px_minmax(0,1fr)] gap-2">
              <dt className="font-medium text-muted-foreground">Network</dt>
              <dd className="min-w-0 font-mono break-words">
                {frame.network}
              </dd>
            </div>
            <div className="grid grid-cols-[110px_minmax(0,1fr)] gap-2">
              <dt className="font-medium text-muted-foreground">Sequence</dt>
              <dd className="min-w-0 font-mono break-words">
                {frame.sequence}
              </dd>
            </div>
            <div className="grid grid-cols-[110px_minmax(0,1fr)] gap-2">
              <dt className="font-medium text-muted-foreground">Source</dt>
              <dd className="min-w-0 font-mono break-words">{frame.source}</dd>
            </div>
            <div className="grid grid-cols-[110px_minmax(0,1fr)] gap-2">
              <dt className="font-medium text-muted-foreground">
                Arbitration ID
              </dt>
              <dd className="min-w-0 font-mono break-words">
                {frame.arbitration_id_hex} ({frame.arbitration_id})
              </dd>
            </div>
            <div className="grid grid-cols-[110px_minmax(0,1fr)] gap-2">
              <dt className="font-medium text-muted-foreground">Extended</dt>
              <dd className="min-w-0 font-mono break-words">
                {frame.is_extended_id ? "true" : "false"}
              </dd>
            </div>
            <div className="grid grid-cols-[110px_minmax(0,1fr)] gap-2">
              <dt className="font-medium text-muted-foreground">Data hex</dt>
              <dd className="min-w-0 font-mono break-words">
                {frame.data_hex || "--"}
              </dd>
            </div>
          </dl>

          <Separator />

          <div className="flex flex-col gap-1">
            <span className="font-medium text-muted-foreground">
              Payload bytes
            </span>
            <div className="flex flex-wrap gap-1">
              {(frame.data_hex.match(/.{1,2}/g) ?? []).map((byte, index) => (
                <span
                  key={`${byte}-${index}`}
                  className="rounded-sm border bg-muted px-2 py-1 font-mono"
                >
                  {byte}
                </span>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <Empty className="min-h-[220px] border">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <ScanSearchIcon />
            </EmptyMedia>
            <EmptyTitle>No frame selected</EmptyTitle>
            <EmptyDescription>
              Select a CAN trace row to inspect its payload.
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      )}
    </CardContent>

    {frame ? (
      <CardFooter>
        <p className="font-mono text-xs text-muted-foreground">
          t+{frame.monotonic_s.toFixed(3)}s
        </p>
      </CardFooter>
    ) : null}
  </Card>
)
