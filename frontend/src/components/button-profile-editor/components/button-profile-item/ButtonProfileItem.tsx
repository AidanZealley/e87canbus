import { useState } from "react"
import { ChevronDownIcon, Trash2Icon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import type { ButtonVisualState } from "../../button-led-presentation"
import type { ButtonCommand, ButtonCommandSlot } from "../../types"
import {
  commandHasActiveState,
  commandLabel,
  defaultColourForCommand,
  sentenceLabel,
} from "../../utils"
import { ButtonAnimationEditor } from "../button-animation-editor"
import { ButtonColourPopover } from "../button-colour-popover"
import { ButtonCommandEditor } from "../button-command-editor"

type ButtonProfileItemProps = {
  buttonIndex: number
  slot: ButtonCommandSlot
  visualState: ButtonVisualState
  disabled?: boolean
  onChange: (slot: ButtonCommandSlot) => Promise<void>
}

export const ButtonProfileItem = ({
  buttonIndex,
  slot,
  visualState,
  disabled = false,
  onChange,
}: ButtonProfileItemProps) => {
  const [expanded, setExpanded] = useState(false)
  const bindingLabel = commandLabel(slot?.command ?? null)
  const detailsId = `button-${buttonIndex}-configuration`

  const changeCommand = (command: ButtonCommand) => {
    if (command === null) return onChange(null)
    return onChange({
      command,
      colour: slot?.colour ?? defaultColourForCommand(command),
      active_colour: slot?.active_colour ?? null,
      animation:
        slot !== null && commandHasActiveState(command) ? slot.animation : null,
    })
  }

  return (
    <section
      className="overflow-hidden rounded-xl border bg-card text-card-foreground"
      aria-label={`Button ${buttonIndex}: ${bindingLabel}`}
    >
      <div className="flex min-w-0 flex-wrap items-center gap-3 p-3">
        <span
          className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-muted font-heading text-lg font-semibold tabular-nums"
          aria-hidden="true"
        >
          {buttonIndex}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{bindingLabel}</p>
          <p className="text-xs text-muted-foreground">
            {sentenceLabel(visualState)}
          </p>
        </div>
        {slot === null ? (
          <span className="text-xs text-muted-foreground">No colour</span>
        ) : (
          <ButtonColourPopover
            buttonIndex={buttonIndex}
            colour={slot.colour}
            disabled={disabled}
            onChange={(colour) => onChange({ ...slot, colour })}
          />
        )}
        <div className="ml-auto flex items-center gap-1">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label={`Clear button ${buttonIndex}`}
            disabled={disabled || slot === null}
            onClick={() => void onChange(null).catch(() => undefined)}
          >
            <Trash2Icon aria-hidden="true" />
          </Button>
          <Button
            type="button"
            variant="outline"
            size="icon"
            aria-label={`${expanded ? "Collapse" : "Configure"} button ${buttonIndex}: ${bindingLabel}`}
            aria-expanded={expanded}
            aria-controls={detailsId}
            onClick={() => setExpanded((current) => !current)}
          >
            <ChevronDownIcon
              className={cn("transition-transform", expanded && "rotate-180")}
              aria-hidden="true"
            />
          </Button>
        </div>
      </div>

      {expanded ? (
        <div
          id={detailsId}
          className="grid gap-5 border-t bg-muted/20 p-4 sm:grid-cols-2"
        >
          <ButtonCommandEditor
            buttonIndex={buttonIndex}
            command={slot?.command ?? null}
            disabled={disabled}
            onChange={changeCommand}
          />
          {slot !== null && commandHasActiveState(slot.command) ? (
            <ButtonAnimationEditor
              buttonIndex={buttonIndex}
              animation={slot.animation}
              disabled={disabled}
              onChange={(animation) => onChange({ ...slot, animation })}
            />
          ) : null}
        </div>
      ) : null}
    </section>
  )
}
