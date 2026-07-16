import type { ReactNode } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import type { DeviceRegistryEntry } from "@/api/live-events"

export type SimulatedDeviceAction =
  | "connect"
  | "disconnect"
  | "reboot"
  | "incompatible"
  | "restore-compatible"
  | "fault"
  | "clear-fault"

export type SimulatedDeviceActionAvailability = Record<
  SimulatedDeviceAction,
  boolean
>

export type SimulatedDeviceActionCallbacks = Partial<
  Record<SimulatedDeviceAction, () => void>
>

type SimulatedDeviceCardProps = {
  role: DeviceRegistryEntry["role"]
  registryEntry: DeviceRegistryEntry
  availableActions: SimulatedDeviceActionAvailability
  callbacks: SimulatedDeviceActionCallbacks
  pendingAction?: SimulatedDeviceAction | null
  errorMessage?: string | null
  children: ReactNode
}

const actionLabels: Record<SimulatedDeviceAction, string> = {
  connect: "Connect",
  disconnect: "Disconnect",
  reboot: "Reboot",
  incompatible: "Simulate incompatible",
  "restore-compatible": "Restore compatible",
  fault: "Set fault",
  "clear-fault": "Clear fault",
}

export const SimulatedDeviceCard = ({
  role,
  registryEntry,
  availableActions,
  callbacks,
  pendingAction = null,
  errorMessage = null,
  children,
}: SimulatedDeviceCardProps) => {
  const statusVariant =
    registryEntry.status === "active"
      ? "default"
      : registryEntry.status === "not_found" || registryEntry.status === "disabled"
        ? "outline"
        : registryEntry.status === "pending"
          ? "warning"
          : "destructive"
  const visibleActions = (Object.keys(actionLabels) as SimulatedDeviceAction[]).filter(
    (action) => availableActions[action] && callbacks[action] !== undefined
  )

  return (
    <Card className="min-w-0" data-device-role={role}>
      <CardHeader>
        <CardTitle>{registryEntry.label}</CardTitle>
        <CardDescription>
          Virtual peer · {registryEntry.source_mode}
        </CardDescription>
        <Badge variant={statusVariant} aria-label={`Status: ${registryEntry.status}`}>
          {formatStatus(registryEntry.status)}
        </Badge>
      </CardHeader>

      <CardContent className="grid gap-4">
        <dl className="grid grid-cols-2 gap-2 text-xs">
          <div className="rounded-md border p-2">
            <dt className="text-muted-foreground">Protocol</dt>
            <dd className="font-medium">
              {registryEntry.protocol_version ?? "Not observed"}
            </dd>
          </div>
          <div className="rounded-md border p-2">
            <dt className="text-muted-foreground">Session</dt>
            <dd className="font-medium">
              {registryEntry.device_session_id ?? "Not observed"}
            </dd>
          </div>
          {registryEntry.last_status_code !== null ? (
            <div className="col-span-2 rounded-md border p-2">
              <dt className="text-muted-foreground">Device status code</dt>
              <dd className="font-medium">{registryEntry.last_status_code}</dd>
            </div>
          ) : null}
        </dl>

        {children}
        {errorMessage ? (
          <p className="text-xs text-destructive" role="alert">
            {errorMessage}
          </p>
        ) : null}
      </CardContent>

      {visibleActions.length > 0 ? (
        <CardFooter className="flex flex-wrap gap-2 border-t">
          {visibleActions.map((action) => (
            <Button
              key={action}
              size="sm"
              variant={action === "disconnect" || action === "fault" ? "destructive" : "outline"}
              disabled={pendingAction !== null}
              onClick={callbacks[action]}
            >
              {pendingAction === action ? `${actionLabels[action]}…` : actionLabels[action]}
            </Button>
          ))}
        </CardFooter>
      ) : null}
    </Card>
  )
}

const formatStatus = (status: DeviceRegistryEntry["status"]) =>
  status.replaceAll("_", " ").replace(/^./, (character) => character.toUpperCase())
