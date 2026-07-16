import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { LoadingButton } from "@/components/loading-button"
import { Settings2Icon } from "lucide-react"
import { actionIcons, actionLabels, statusControls } from "./constants"
import type { SimulatedDeviceAction, SimulatedDeviceCardProps } from "./types"
import {
  connectionActionForStatus,
  formatStatus,
  statusActionForControl,
  statusBadgeVariant,
  statusControlForStatus,
} from "./utils"

export const SimulatedDeviceCard = ({
  role,
  registryEntry,
  availableActions,
  callbacks,
  pendingAction = null,
  children,
}: SimulatedDeviceCardProps) => {
  const statusVariant = statusBadgeVariant(registryEntry.status)
  const connectionAction = connectionActionForStatus(registryEntry.status)
  const actionCandidates: SimulatedDeviceAction[] = [connectionAction, "reboot"]
  const visibleActions = actionCandidates.filter(
    (action) => availableActions[action] && callbacks[action] !== undefined
  )
  const statusControlActions = statusControls.map((control) => ({
    ...control,
    action: statusActionForControl(registryEntry.status, control.value),
  }))
  const statusMenuAvailable = statusControlActions.some(
    (control) =>
      control.action !== null &&
      availableActions[control.action] &&
      callbacks[control.action] !== undefined
  )

  return (
    <Card className="min-w-0" data-device-role={role}>
      <CardHeader>
        <div className="flex items-center justify-between gap-4">
          <CardTitle>{registryEntry.label}</CardTitle>
          <div className="flex items-center">
            <Badge
              variant={statusVariant}
              aria-label={`Status: ${registryEntry.status}`}
            >
              {formatStatus(registryEntry.status)}
            </Badge>
          </div>
        </div>
        <dl className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
          <div className="flex gap-1">
            <dt>Protocol</dt>
            <dd className="text-foreground">
              {registryEntry.protocol_version ?? "Not observed"}
            </dd>
          </div>
          <div className="flex gap-1">
            <dt>Session</dt>
            <dd className="text-foreground">
              {registryEntry.device_session_id ?? "Not observed"}
            </dd>
          </div>
          {registryEntry.last_status_code !== null ? (
            <div className="flex gap-1">
              <dt>Status code</dt>
              <dd className="text-foreground">
                {registryEntry.last_status_code}
              </dd>
            </div>
          ) : null}
        </dl>
      </CardHeader>

      <CardContent className="grid gap-4">{children}</CardContent>

      {visibleActions.length > 0 || statusMenuAvailable ? (
        <CardFooter className="flex items-center justify-between gap-2 border-t">
          <div className="flex flex-wrap gap-2">
            {visibleActions.map((action) => {
              const Icon = actionIcons[action]

              return (
                <LoadingButton
                  key={action}
                  size="sm"
                  variant={action === "disconnect" ? "destructive" : "outline"}
                  isLoading={pendingAction === action}
                  disabled={pendingAction !== null && pendingAction !== action}
                  onClick={callbacks[action]}
                >
                  <Icon className="size-2.5" strokeWidth={3} />
                  {actionLabels[action]}
                </LoadingButton>
              )
            })}
          </div>

          {statusMenuAvailable ? (
            <div className="flex">
              <DropdownMenu>
                <DropdownMenuTrigger
                  render={
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={pendingAction !== null}
                    />
                  }
                >
                  <Settings2Icon className="size-2.5" strokeWidth={3} />
                  Status
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-40">
                  <DropdownMenuGroup>
                    <DropdownMenuLabel>Device status</DropdownMenuLabel>
                    <DropdownMenuRadioGroup
                      value={statusControlForStatus(registryEntry.status)}
                    >
                      {statusControlActions.map((control) => {
                        const Icon = actionIcons[control.iconAction]
                        const disabled =
                          pendingAction !== null ||
                          control.action === null ||
                          !availableActions[control.action] ||
                          callbacks[control.action] === undefined

                        return (
                          <DropdownMenuRadioItem
                            key={control.value}
                            value={control.value}
                            disabled={disabled}
                            onClick={() => {
                              if (control.action !== null) {
                                callbacks[control.action]?.()
                              }
                            }}
                          >
                            <Icon />
                            {control.label}
                          </DropdownMenuRadioItem>
                        )
                      })}
                    </DropdownMenuRadioGroup>
                  </DropdownMenuGroup>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          ) : null}
        </CardFooter>
      ) : null}
    </Card>
  )
}
