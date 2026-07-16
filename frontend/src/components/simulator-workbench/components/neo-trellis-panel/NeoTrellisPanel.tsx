import { NeoTrellisButton } from "./components/neo-trellis-button"

export type NeoTrellisButtonState = {
  index: number
  rgb: readonly [red: number, green: number, blue: number]
}

type NeoTrellisPanelProps = {
  buttons: NeoTrellisButtonState[]
  emulatorControlsAvailable: boolean
  onClick: (index: number) => void
}

export const NeoTrellisPanel = ({
  buttons,
  emulatorControlsAvailable,
  onClick,
}: NeoTrellisPanelProps) => (
  <section className="grid gap-4" aria-label="Button-pad emulator exercise">
    {!emulatorControlsAvailable ? (
      <p className="text-xs text-muted-foreground">
        Wire-level button controls are available only for the active emulated role.
      </p>
    ) : null}
    <div className="grid grid-cols-4 gap-2">
      {buttons.map(({ index, rgb }) => (
        <div key={index} className="flex min-w-0 flex-col gap-1">
          <NeoTrellisButton
            index={index}
            rgb={rgb}
            disabled={!emulatorControlsAvailable}
            onClick={onClick}
          />
        </div>
      ))}
    </div>
  </section>
)
