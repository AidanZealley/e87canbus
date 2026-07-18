import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"

import {
  getApplicationSettingsQueryKey,
  updateApplicationSettingsMutation,
} from "@/api/http/@tanstack/react-query.gen"
import type {
  ApplicationSettingsResponse,
  SpeedUnit,
  TemperatureUnit,
} from "@/api/http/types.gen"
import { isApiProblemResponse } from "@/api/is-api-problem"
import { ModeToggle } from "@/components/mode-toggle"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useEffectiveApplicationSettings } from "@/lib/application-settings-query"
import type { ApplicationSettingsDraft } from "./types"
import {
  changeDraftTemperatureUnit,
  settingsDraftMatches,
  settingsToDraft,
  validateSettingsDraft,
} from "./utils"

export const CarSettingsForm = () => {
  const effectiveSettings = useEffectiveApplicationSettings()
  const {
    settings,
    isAuthoritative: settingsAuthoritative,
    error: settingsError,
    isLoading: settingsLoading,
    isRefetching: settingsRefetching,
    refetch: settingsRefetch,
  } = effectiveSettings

  return (
    <section className="min-h-full p-2" aria-labelledby="settings-title">
      <div className="mx-auto grid max-w-3xl gap-2 pb-2">
        <SettingsHeader
          revision={settingsAuthoritative ? settings.revision : null}
        />
        {settingsAuthoritative ? (
          <AuthoritativeSettingsForm settings={settings} />
        ) : (
          <UnavailableSettings
            loading={settingsLoading}
            error={settingsError}
            refetching={settingsRefetching}
            onRetry={settingsRefetch}
          />
        )}
      </div>
    </section>
  )
}

const SettingsHeader = ({ revision }: { revision: number | null }) => (
  <div className="flex items-center gap-3">
    <h1 id="settings-title" className="text-lg font-semibold">
      Settings
    </h1>
    {revision === null ? null : (
      <span className="text-xs text-muted-foreground">
        Loaded revision {revision}
      </span>
    )}
    <div className="ml-auto flex items-center gap-2">
      <span className="text-xs text-muted-foreground">Theme</span>
      <ModeToggle />
    </div>
  </div>
)

const UnavailableSettings = ({
  loading,
  error,
  refetching,
  onRetry,
}: {
  loading: boolean
  error: unknown
  refetching: boolean
  onRetry: () => Promise<void>
}) => (
  <Card size="sm">
    <CardContent className="flex min-h-40 flex-col items-center justify-center gap-3 text-center">
      <p className="text-sm text-muted-foreground">
        {loading
          ? "Loading current settings…"
          : "Current settings unavailable. Saving is disabled."}
      </p>
      {!loading && error !== null ? (
        <Button
          variant="outline"
          disabled={refetching}
          onClick={() => void onRetry()}
        >
          {refetching ? "Retrying…" : "Retry settings"}
        </Button>
      ) : null}
    </CardContent>
  </Card>
)

const AuthoritativeSettingsForm = ({
  settings,
}: {
  settings: ApplicationSettingsResponse
}) => {
  const queryClient = useQueryClient()
  const update = useMutation({
    ...updateApplicationSettingsMutation(),
    onSuccess: (committed) =>
      queryClient.setQueryData(getApplicationSettingsQueryKey(), committed),
  })
  const [authoritative, setAuthoritative] = useState(settings)
  const [draft, setDraft] = useState<ApplicationSettingsDraft>(() =>
    settingsToDraft(settings)
  )
  const [lastSavedRevision, setLastSavedRevision] = useState<number | null>(
    null
  )
  const [lastError, setLastError] = useState<string | null>(null)
  const [conflictRevision, setConflictRevision] = useState<number | null>(null)
  const [confirmReload, setConfirmReload] = useState(false)
  const dirty = !settingsDraftMatches(draft, authoritative)

  if (settings.revision > authoritative.revision) {
    setAuthoritative(settings)
    if (!dirty) setDraft(settingsToDraft(settings))
  }

  const reload = () => {
    setAuthoritative(settings)
    setDraft(settingsToDraft(settings))
    setLastError(null)
    setConflictRevision(null)
    setLastSavedRevision(null)
    setConfirmReload(false)
  }

  const save = async () => {
    if (update.isPending) return
    const validation = validateSettingsDraft(draft)
    if (validation.request === null) {
      setLastError(validation.error)
      return
    }
    setLastError(null)
    setConflictRevision(null)
    try {
      const committed = await update.mutateAsync({ body: validation.request })
      setAuthoritative(committed)
      setDraft(settingsToDraft(committed))
      setLastSavedRevision(committed.revision)
    } catch (error) {
      if (
        isApiProblemResponse(error) &&
        error.error.code === "settings_revision_conflict"
      ) {
        setConflictRevision(error.error.current_revision ?? null)
        setLastError(
          `Settings changed elsewhere${error.error.current_revision ? ` (revision ${error.error.current_revision})` : ""}. Your draft was retained.`
        )
        await queryClient.invalidateQueries({
          queryKey: getApplicationSettingsQueryKey(),
        })
      } else {
        setLastError(
          error instanceof Error
            ? error.message
            : "Settings could not be saved."
        )
      }
    }
  }

  const temperatureSuffix = draft.temperatureUnit === "f" ? "°F" : "°C"
  const setField = <Field extends keyof ApplicationSettingsDraft>(
    field: Field,
    value: ApplicationSettingsDraft[Field]
  ) => {
    setDraft((current) => ({ ...current, [field]: value }))
    setLastError(null)
    setLastSavedRevision(null)
  }

  return (
    <>
      <Card size="sm">
        <CardHeader>
          <CardTitle>Display units</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-3">
          <SelectField
            label="Speed unit"
            value={draft.speedUnit}
            items={[
              { value: "mph", label: "mph" },
              { value: "kmh", label: "km/h" },
            ]}
            onChange={(value) => setField("speedUnit", value as SpeedUnit)}
          />
          <SelectField
            label="Temperature unit"
            value={draft.temperatureUnit}
            items={[
              { value: "c", label: "Celsius" },
              { value: "f", label: "Fahrenheit" },
            ]}
            onChange={(value) => {
              setDraft((current) =>
                changeDraftTemperatureUnit(current, value as TemperatureUnit)
              )
              setLastError(null)
              setLastSavedRevision(null)
            }}
          />
        </CardContent>
      </Card>

      <Card size="sm">
        <CardHeader>
          <CardTitle>Temperature thresholds</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <NumberField
            label={`Oil warning (${temperatureSuffix})`}
            value={draft.oilWarning}
            onChange={(value) => setField("oilWarning", value)}
          />
          <NumberField
            label={`Oil critical (${temperatureSuffix})`}
            value={draft.oilCritical}
            onChange={(value) => setField("oilCritical", value)}
          />
          <NumberField
            label={`Coolant warning (${temperatureSuffix})`}
            value={draft.coolantWarning}
            onChange={(value) => setField("coolantWarning", value)}
          />
          <NumberField
            label={`Coolant critical (${temperatureSuffix})`}
            value={draft.coolantCritical}
            onChange={(value) => setField("coolantCritical", value)}
          />
        </CardContent>
      </Card>

      <Card size="sm">
        <CardHeader>
          <CardTitle>Shift thresholds</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-3 gap-3">
          <NumberField
            label="Shift stage 1 RPM"
            value={draft.shiftStage1Rpm}
            step="1"
            onChange={(value) => setField("shiftStage1Rpm", value)}
          />
          <NumberField
            label="Shift stage 2 RPM"
            value={draft.shiftStage2Rpm}
            step="1"
            onChange={(value) => setField("shiftStage2Rpm", value)}
          />
          <NumberField
            label="Redline RPM"
            value={draft.redlineRpm}
            step="1"
            onChange={(value) => setField("redlineRpm", value)}
          />
        </CardContent>
      </Card>

      <div className="sticky bottom-0 flex items-center gap-2 rounded-lg border bg-background/95 p-2 backdrop-blur">
        <Button
          disabled={!dirty || update.isPending}
          onClick={() => void save()}
        >
          {update.isPending ? "Saving…" : "Save settings"}
        </Button>
        {conflictRevision !== null ||
        draft.sourceRevision !== settings.revision ? (
          <Button
            variant="outline"
            onClick={() => (dirty ? setConfirmReload(true) : reload())}
          >
            Reload Current Settings
          </Button>
        ) : null}
        <p className="min-w-0 text-xs text-muted-foreground" aria-live="polite">
          {lastError ??
            (lastSavedRevision === null
              ? dirty
                ? "Unsaved changes"
                : "Settings are current"
              : `Saved revision ${lastSavedRevision}`)}
        </p>
      </div>

      <AlertDialog open={confirmReload} onOpenChange={setConfirmReload}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Reload current settings?</AlertDialogTitle>
            <AlertDialogDescription>
              This will discard the unsaved settings draft and load revision{" "}
              {settings.revision}.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep draft</AlertDialogCancel>
            <AlertDialogAction onClick={reload}>
              Discard and reload
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

const NumberField = ({
  label,
  value,
  step = "0.1",
  onChange,
}: {
  label: string
  value: string
  step?: string
  onChange: (value: string) => void
}) => {
  const id = label.toLowerCase().replaceAll(/[^a-z0-9]+/g, "-")
  return (
    <div className="grid gap-1">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        type="number"
        inputMode="decimal"
        step={step}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  )
}

const SelectField = ({
  label,
  value,
  items,
  onChange,
}: {
  label: string
  value: string
  items: { value: string; label: string }[]
  onChange: (value: string) => void
}) => {
  const id = label.toLowerCase().replaceAll(" ", "-")
  return (
    <div className="grid gap-1">
      <Label htmlFor={id}>{label}</Label>
      <Select
        value={value}
        items={items}
        onValueChange={(nextValue) => {
          if (nextValue !== null) onChange(nextValue)
        }}
      >
        <SelectTrigger id={id} className="w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {items.map((item) => (
            <SelectItem key={item.value} value={item.value}>
              {item.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}
