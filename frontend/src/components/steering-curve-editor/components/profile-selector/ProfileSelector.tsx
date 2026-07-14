import { useShallow } from "zustand/react/shallow"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useSteeringCurveEditorStore } from "../../store-context"

const NO_PROFILE_VALUE = "no-saved-profile"

export const ProfileSelector = () => {
  const {
    profiles,
    selectedProfileId,
    newProfileName,
    disabled,
    selectProfile,
    loadSelected,
    setNewProfileName,
    saveAs,
  } = useSteeringCurveEditorStore(
    useShallow((state) => ({
      profiles: state.profiles,
      selectedProfileId: state.selectedProfileId,
      newProfileName: state.newProfileName,
      disabled: state.pendingAction !== null,
      selectProfile: state.selectProfile,
      loadSelected: state.loadSelected,
      setNewProfileName: state.setNewProfileName,
      saveAs: state.saveAs,
    }))
  )

  return (
    <div className="grid gap-3 rounded-lg border bg-muted/30 p-3 lg:grid-cols-2">
      <div className="grid gap-2">
        <Label htmlFor="saved-profile">Saved profile</Label>
        <div className="flex gap-2">
          <Select
            value={selectedProfileId ?? NO_PROFILE_VALUE}
            items={[
              { label: "No saved selection", value: NO_PROFILE_VALUE },
              ...profiles.map((profile) => ({
                label: `${profile.name} · r${profile.revision}`,
                value: profile.profile_id,
              })),
            ]}
            disabled={disabled}
            onValueChange={(value) =>
              selectProfile(value === NO_PROFILE_VALUE ? null : value)
            }
          >
            <SelectTrigger id="saved-profile">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NO_PROFILE_VALUE}>
                No saved selection
              </SelectItem>
              {profiles.map((profile) => (
                <SelectItem key={profile.profile_id} value={profile.profile_id}>
                  {profile.name} · r{profile.revision}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            variant="outline"
            disabled={disabled || selectedProfileId === null}
            onClick={loadSelected}
          >
            Load saved
          </Button>
        </div>
      </div>

      <div className="grid gap-2">
        <Label htmlFor="new-profile-name">New profile name</Label>
        <div className="flex gap-2">
          <Input
            id="new-profile-name"
            maxLength={100}
            placeholder="e.g. Wet track"
            value={newProfileName}
            disabled={disabled}
            onChange={(event) => setNewProfileName(event.target.value)}
          />
          <Button
            variant="outline"
            disabled={disabled || newProfileName.trim().length === 0}
            onClick={() => void saveAs()}
          >
            Save as
          </Button>
        </div>
      </div>
    </div>
  )
}
