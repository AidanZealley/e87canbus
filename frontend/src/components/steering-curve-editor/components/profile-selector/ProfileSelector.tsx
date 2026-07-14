import type { StoredSteeringProfile } from "@/api/steering"
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

type ProfileSelectorProps = {
  profiles: StoredSteeringProfile[]
  selectedProfileId: string | null
  newProfileName: string
  disabled: boolean
  onSelect: (profileId: string | null) => void
  onLoad: () => void
  onNewProfileNameChange: (name: string) => void
  onSaveAs: () => void
}

const NO_PROFILE_VALUE = "no-saved-profile"

export const ProfileSelector = ({
  profiles,
  selectedProfileId,
  newProfileName,
  disabled,
  onSelect,
  onLoad,
  onNewProfileNameChange,
  onSaveAs,
}: ProfileSelectorProps) => (
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
            onSelect(value === NO_PROFILE_VALUE ? null : value)
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
          onClick={onLoad}
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
          onChange={(event) => onNewProfileNameChange(event.target.value)}
        />
        <Button
          variant="outline"
          disabled={disabled || newProfileName.trim().length === 0}
          onClick={onSaveAs}
        >
          Save as
        </Button>
      </div>
    </div>
  </div>
)
