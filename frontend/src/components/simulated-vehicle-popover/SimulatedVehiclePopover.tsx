import { useMutation, useQuery } from "@tanstack/react-query"
import { CarFrontIcon, PowerIcon } from "lucide-react"

import { getRuntimeConfigurationOptions } from "@/api/http/@tanstack/react-query.gen"
import { Button } from "@/components/ui/button"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { LiveSimulatedVehicleControls } from "@/components/simulator-workbench/LiveSimulatedVehicleControls"
import { setSimulatedVehicleRunning } from "@/components/simulator-workbench/simulated-vehicle-power"
import { useLiveStore } from "@/live/live-store"

export const SimulatedVehiclePopover = () => {
  const runtime = useQuery({
    ...getRuntimeConfigurationOptions(),
    staleTime: Infinity,
  })
  const synchronized = useLiveStore((state) => state.connection.synchronized)
  const isRunning = useLiveStore(
    (state) => state.connection.synchronized && state.vehicle.speed_valid
  )
  const power = useMutation({
    mutationFn: setSimulatedVehicleRunning,
  })

  if (!runtime.data?.capabilities.simulated_vehicle) return null

  return (
    <div className="fixed right-3 bottom-3 z-40">
      <div className="relative size-14">
        <div className="absolute right-12 bottom-0 z-10 rounded-full bg-background">
          <Button
            type="button"
            size="icon-lg"
            variant={isRunning ? "destructive" : "success"}
            className="rounded-full border-0 shadow-xl"
            aria-label={
              isRunning ? "Stop simulated car" : "Start simulated car"
            }
            disabled={!synchronized || power.isPending}
            onClick={() => power.mutate(!isRunning)}
          >
            <PowerIcon aria-hidden="true" />
          </Button>
        </div>
        <Popover>
          <PopoverTrigger
            render={
              <Button
                type="button"
                size="icon"
                className="size-14 rounded-full shadow-lg"
                aria-label="Open simulated vehicle controls"
              />
            }
          >
            <CarFrontIcon className="size-6" aria-hidden="true" />
          </PopoverTrigger>
          <PopoverContent className="max-h-[calc(100svh-7rem)] w-[min(28rem,calc(100vw-2rem))] overflow-y-auto p-0">
            <LiveSimulatedVehicleControls />
          </PopoverContent>
        </Popover>
      </div>
    </div>
  )
}
