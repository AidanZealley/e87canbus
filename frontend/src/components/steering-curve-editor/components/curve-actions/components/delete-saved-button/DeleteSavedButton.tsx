import { useRef, useState } from "react"
import { AlertDialog as AlertDialogPrimitive } from "@base-ui/react/alert-dialog"
import { Trash2Icon } from "lucide-react"

import type { SteeringProfileResponse } from "@/api/http/types.gen"
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

type DeleteSavedButtonProps = {
  profile: SteeringProfileResponse | null
  pending: boolean
  deleting: boolean
  onConfirm: (profile: SteeringProfileResponse) => void
}

export const DeleteSavedButton = ({
  profile,
  pending,
  deleting,
  onConfirm,
}: DeleteSavedButtonProps) => {
  const actionsRef = useRef<AlertDialogPrimitive.Root.Actions>(null)
  const [targetProfile, setTargetProfile] = useState(profile)

  const confirm = () => {
    if (!targetProfile) return
    onConfirm(targetProfile)
    actionsRef.current?.close()
  }

  return (
    <AlertDialog
      actionsRef={actionsRef}
      onOpenChange={(open) => {
        if (open) setTargetProfile(profile)
      }}
    >
      <AlertDialogTrigger
        render={
          <Button variant="destructive" disabled={!profile || pending}>
            {deleting ? "Deleting…" : "Delete saved"}
          </Button>
        }
      />
      <AlertDialogContent size="sm">
        <AlertDialogHeader>
          <AlertDialogMedia className="bg-destructive/10 text-destructive dark:bg-destructive/20 dark:text-destructive">
            <Trash2Icon />
          </AlertDialogMedia>
          <AlertDialogTitle>Delete saved profile?</AlertDialogTitle>
          <AlertDialogDescription>
            This will permanently delete {targetProfile?.name}. This action
            cannot be undone.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel variant="outline">Cancel</AlertDialogCancel>
          <AlertDialogAction variant="destructive" onClick={confirm}>
            Delete
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
