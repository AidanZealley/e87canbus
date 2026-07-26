import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import type { ButtonLedRgb } from "../../button-led-presentation"
import { restingButtonLedRgb } from "../../button-led-presentation"
import { BUTTON_COLOUR_PRESETS } from "../../constants"
import {
  type ButtonColour,
  colourHasVisibleRestingState,
  hexToRgb,
  rgbCss,
  rgbToHex,
} from "../../colour"

type ButtonColourPopoverProps = {
  buttonIndex: number
  colour: ButtonLedRgb
  disabled?: boolean
  onChange: (colour: ButtonColour) => Promise<void>
}

export const ButtonColourPopover = ({
  buttonIndex,
  colour,
  disabled = false,
  onChange,
}: ButtonColourPopoverProps) => {
  const [open, setOpen] = useState(false)
  const savedHex = rgbToHex(colour)
  const [draft, setDraft] = useState(savedHex)
  const [showError, setShowError] = useState(false)
  const draftRgb = hexToRgb(draft)
  const faintColour = restingButtonLedRgb(colour)
  const draftError =
    draftRgb !== null && !colourHasVisibleRestingState(draftRgb)
      ? "Choose a brighter colour so the inactive LED does not render as off."
      : null

  const commit = async (value: string) => {
    const rgb = hexToRgb(value)
    if (rgb === null || !colourHasVisibleRestingState(rgb)) {
      setShowError(true)
      return
    }
    const normalized = rgbToHex(rgb)
    setDraft(normalized)
    setShowError(false)
    if (normalized === savedHex) return
    try {
      await onChange(rgb)
    } catch {
      return
    }
  }

  return (
    <Popover
      open={open}
      onOpenChange={(nextOpen) => {
        setOpen(nextOpen)
        setDraft(savedHex)
        setShowError(false)
      }}
    >
      <PopoverTrigger
        render={
          <Button
            type="button"
            variant="outline"
            className="h-8 gap-0 overflow-hidden p-1"
            aria-label={`Button ${buttonIndex} colour: full ${savedHex}, faint ${rgbToHex(faintColour)}`}
            disabled={disabled}
          />
        }
      >
        <span
          className="h-full w-7 rounded-l-sm border border-black/15"
          style={{ backgroundColor: rgbCss(colour) }}
          aria-hidden="true"
        />
        <span
          className="h-full w-7 rounded-r-sm border border-l-0 border-black/15"
          style={{ backgroundColor: rgbCss(faintColour) }}
          aria-hidden="true"
        />
      </PopoverTrigger>
      <PopoverContent
        side="bottom"
        align="end"
        className="w-[min(20rem,calc(100vw-2rem))] p-4"
      >
        <div className="grid gap-4">
          <div>
            <p className="text-sm font-medium">Button {buttonIndex} colour</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Full colour and its faint inactive rendering.
            </p>
          </div>
          <div className="grid grid-cols-[4rem_1fr] items-end gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor={`button-${buttonIndex}-native-colour`}>
                Picker
              </Label>
              <Input
                id={`button-${buttonIndex}-native-colour`}
                type="color"
                className="h-9 cursor-pointer p-1"
                value={draftRgb === null ? savedHex : rgbToHex(draftRgb)}
                disabled={disabled}
                onInput={(event) => {
                  setDraft(event.currentTarget.value.toUpperCase())
                  setShowError(false)
                }}
                onChange={(event) => void commit(event.currentTarget.value)}
              />
            </div>
            <div className="grid gap-1">
              <span className="text-xs font-medium">Selected colour</span>
              <output className="text-sm font-medium tabular-nums">
                {draftRgb === null ? savedHex : rgbToHex(draftRgb)}
              </output>
            </div>
          </div>
          <div className="grid gap-1.5">
            <span className="text-xs font-medium">Presets</span>
            <div className="flex flex-wrap gap-2">
              {BUTTON_COLOUR_PRESETS.map((preset) => (
                <Button
                  key={preset.name}
                  type="button"
                  size="icon"
                  variant="outline"
                  className="size-7 p-1"
                  aria-label={`Use ${preset.name} ${rgbToHex(preset.colour)}`}
                  disabled={disabled}
                  onClick={() => void commit(rgbToHex(preset.colour))}
                >
                  <span
                    className="size-full rounded-sm border border-black/15"
                    style={{ backgroundColor: rgbCss(preset.colour) }}
                    aria-hidden="true"
                  />
                </Button>
              ))}
            </div>
          </div>
          <p
            id={`button-${buttonIndex}-colour-help`}
            className={
              showError && draftError !== null
                ? "text-xs text-destructive"
                : "text-xs text-muted-foreground"
            }
            aria-live="polite"
          >
            {showError && draftError !== null
              ? draftError
              : "Inactive brightness is derived automatically at 8/255."}
          </p>
        </div>
      </PopoverContent>
    </Popover>
  )
}
