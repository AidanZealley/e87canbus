import { useRef } from "react"
import { AlertDialog as AlertDialogPrimitive } from "@base-ui/react/alert-dialog"
import { RotateCcwIcon } from "lucide-react"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogMedia,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"

type ReloadActiveButtonProps = {
  disabled: boolean
  onConfirm: () => void
}

export const ReloadActiveButton = ({
  disabled,
  onConfirm,
}: ReloadActiveButtonProps) => {
  const actionsRef = useRef<AlertDialogPrimitive.Root.Actions>(null)

  const confirm = () => {
    onConfirm()
    actionsRef.current?.close()
  }

  return (
    <AlertDialog actionsRef={actionsRef}>
      <AlertDialogTrigger
        render={
          <Button variant="outline" disabled={disabled}>
            Reload active
          </Button>
        }
      />
      <AlertDialogContent size="sm">
        <AlertDialogHeader>
          <AlertDialogMedia className="bg-destructive/10 text-destructive dark:bg-destructive/20 dark:text-destructive">
            <RotateCcwIcon />
          </AlertDialogMedia>
          <AlertDialogTitle>Reload active values?</AlertDialogTitle>
          <AlertDialogDescription>
            This will discard your draft changes and replace them with the
            active values.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel variant="outline">Cancel</AlertDialogCancel>
          <AlertDialogAction variant="destructive" onClick={confirm}>
            Reload
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
