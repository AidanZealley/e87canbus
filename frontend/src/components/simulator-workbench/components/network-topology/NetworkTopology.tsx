import { CableIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { useNetworks } from "../../query"

export const NetworkTopology = () => {
  const networks = useNetworks()

  return (
    <Card className="@container min-w-0">
      <CardHeader>
        <CardTitle>CAN network topology</CardTitle>
        <CardDescription>
          Independent simulated BMW broadcast domains
        </CardDescription>
        <CardAction>
          <CableIcon aria-hidden="true" />
        </CardAction>
      </CardHeader>
      <CardContent className="grid gap-3 @4xl:grid-cols-3">
        {networks.map((network) => (
          <section key={network.id} className="rounded-md border p-3">
            <div className="mb-3 flex items-center justify-between gap-2">
              <h3 className="font-heading text-sm font-semibold">
                {network.label}
              </h3>
              <Badge variant={network.connected ? "default" : "destructive"}>
                {network.connected ? "Connected" : "Disconnected"}
              </Badge>
            </div>
            <dl className="mb-3 grid grid-cols-2 gap-2 text-xs">
              <div>
                <dt className="text-muted-foreground">Interface</dt>
                <dd className="font-mono">{network.interface}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Bitrate</dt>
                <dd className="font-mono">
                  {network.bitrate.toLocaleString()} bit/s
                </dd>
              </div>
            </dl>
            <div className="flex flex-wrap gap-1">
              {network.nodes.map((node) => (
                <Badge key={node} variant="outline">
                  {node}
                </Badge>
              ))}
            </div>
          </section>
        ))}
      </CardContent>
    </Card>
  )
}
