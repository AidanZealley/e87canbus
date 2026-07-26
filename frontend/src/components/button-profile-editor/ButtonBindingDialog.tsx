import { useForm } from "@tanstack/react-form"

import { LoadingButton } from "@/components/loading-button"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { ButtonCommand } from "./types"
import {
  commandToFormValue,
  commandTypeOptions,
  formValueToCommand,
} from "./utils"

type ButtonBindingDialogProps = {
  buttonIndex: number
  command: ButtonCommand
  open: boolean
  onOpenChange: (open: boolean) => void
  onApply: (command: ButtonCommand) => Promise<void>
}

const steeringModeOptions = [
  { value: "auto", label: "Automatic" },
  { value: "manual", label: "Manual" },
]

const assistanceDirectionOptions = [
  { value: "1", label: "Increase" },
  { value: "-1", label: "Decrease" },
]

const maximumStateOptions = [
  { value: "true", label: "Enabled" },
  { value: "false", label: "Disabled" },
]

export const ButtonBindingDialog = ({
  buttonIndex,
  command,
  open,
  onOpenChange,
  onApply,
}: ButtonBindingDialogProps) => {
  const form = useForm({
    defaultValues: commandToFormValue(command),
    onSubmit: async ({ value }) => {
      try {
        await onApply(formValueToCommand(value))
      } catch {
        return
      }
      onOpenChange(false)
    },
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xs">
        <DialogHeader>
          <DialogTitle>Edit button {buttonIndex}</DialogTitle>
          <DialogDescription>
            Choose the command sent when this button is pressed. LED appearance
            is previewed from its saved colour and current vehicle state. A dim
            amber preview means live state is unavailable.
          </DialogDescription>
        </DialogHeader>
        <form
          className="grid gap-4"
          onSubmit={(event) => {
            event.preventDefault()
            event.stopPropagation()
            void form.handleSubmit()
          }}
        >
          <form.Field name="type">
            {(field) => (
              <div className="grid gap-2">
                <Label htmlFor="button-command">Command</Label>
                <Select
                  value={field.state.value}
                  items={commandTypeOptions}
                  onValueChange={(value) =>
                    field.handleChange(value as (typeof field.state)["value"])
                  }
                >
                  <SelectTrigger id="button-command" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {commandTypeOptions.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
          </form.Field>
          <form.Subscribe selector={(state) => state.values.type}>
            {(type) => (
              <>
                {type === "select_steering_mode" ? (
                  <form.Field name="mode">
                    {(field) => (
                      <div className="grid gap-2">
                        <Label htmlFor="steering-mode">Mode</Label>
                        <Select
                          value={field.state.value}
                          items={steeringModeOptions}
                          onValueChange={(value) =>
                            field.handleChange(value as "auto" | "manual")
                          }
                        >
                          <SelectTrigger id="steering-mode" className="w-full">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="auto">Automatic</SelectItem>
                            <SelectItem value="manual">Manual</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    )}
                  </form.Field>
                ) : null}
                {type === "adjust_manual_assistance" ? (
                  <form.Field name="delta">
                    {(field) => (
                      <div className="grid gap-2">
                        <Label htmlFor="assistance-direction">Direction</Label>
                        <Select
                          value={field.state.value}
                          items={assistanceDirectionOptions}
                          onValueChange={(value) =>
                            field.handleChange(value as "-1" | "1")
                          }
                        >
                          <SelectTrigger
                            id="assistance-direction"
                            className="w-full"
                          >
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="1">Increase</SelectItem>
                            <SelectItem value="-1">Decrease</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    )}
                  </form.Field>
                ) : null}
                {type === "set_manual_assistance_level" ? (
                  <form.Field name="level">
                    {(field) => (
                      <div className="grid gap-2">
                        <Label htmlFor="assistance-level">Level</Label>
                        <Input
                          id="assistance-level"
                          type="number"
                          min={0}
                          step={1}
                          required
                          value={field.state.value}
                          onBlur={field.handleBlur}
                          onChange={(event) =>
                            field.handleChange(event.target.value)
                          }
                        />
                      </div>
                    )}
                  </form.Field>
                ) : null}
                {type === "set_maximum_assistance" ? (
                  <form.Field name="enabled">
                    {(field) => (
                      <div className="grid gap-2">
                        <Label htmlFor="maximum-state">State</Label>
                        <Select
                          value={field.state.value}
                          items={maximumStateOptions}
                          onValueChange={(value) =>
                            field.handleChange(value as "true" | "false")
                          }
                        >
                          <SelectTrigger id="maximum-state" className="w-full">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="true">Enabled</SelectItem>
                            <SelectItem value="false">Disabled</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    )}
                  </form.Field>
                ) : null}
              </>
            )}
          </form.Subscribe>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <form.Subscribe selector={(state) => state.isSubmitting}>
              {(isSubmitting) => (
                <LoadingButton type="submit" isLoading={isSubmitting}>
                  Apply binding
                </LoadingButton>
              )}
            </form.Subscribe>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
