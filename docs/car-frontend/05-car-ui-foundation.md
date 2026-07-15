# Phase 5: Shared car UI foundation

## Goal

Build the long-lived data, formatting, warning and instrument foundation shared by all `/car`
screens. This phase consumes the committed settings, engine-telemetry and device contracts from
Phases 2-4; it must not invent fallback API shapes.

## Component boundaries

Follow `frontend/AGENTS.md`. A likely structure is:

```text
src/components/
├── car-layout/
├── telemetry-value/
├── temperature-gauge/
├── rpm-bar/
└── device-status-footer/
```

Each directory uses a PascalCase component file and named `index.ts` re-export. Keep pure conversion
and warning utilities with the car UI foundation and test them directly. Use shadcn primitives for
buttons, alerts, selections and cards; custom gauges are appropriate because shadcn has no
automotive instrument primitive.

## Long-lived car data owner

The `/car` layout must own one connection to the existing snapshot/query system and expose a context
or similarly direct hook boundary to its route children. It provides:

- Current application and steering-controller snapshot.
- Device array.
- Connection state.
- Authoritative settings query state.
- Effective settings: authoritative data or compiled defaults.
- Whether defaults are active because settings failed.
- Derived oil and coolant warning severity with persistent hysteresis.

Do not mount separate WebSocket connections in each child page. Route changes must not reset
hysteresis or throw away cached settings/profile data.

Refactor current simulator hooks only as much as needed to make them reusable outside
`SimulatorWorkbench`. Preserve existing query keys, merge ordering, trace behavior, heartbeat and
reconnect semantics. Avoid a second parallel snapshot store.

## Connection and configuration faults

The car layout reserves a compact top banner:

- Show it while the initial snapshot is unavailable or the WebSocket is reconnecting/disconnected.
- Use concise in-car wording rather than the dev workbench's port-8000 instructions.
- On connection loss, live telemetry consumers render unavailable even if an old query snapshot is
  still cached.
- Navigation and cached static/profile/settings views remain usable.

If settings fail to load:

- Use compiled defaults matching the backend seed.
- Show a compact configuration-fault indicator.
- Preserve a separate error value for the settings screen Retry action.
- Never label defaults as successfully loaded settings.

## Canonical conversions

Implement pure utilities:

```text
km/h -> mph: value * 0.621371
C -> F: value * 9 / 5 + 32
F -> C: (value - 32) * 5 / 9
```

Presentation rules:

- Display speed as a rounded whole number.
- Display temperatures as rounded whole numbers.
- Settings-form Fahrenheit values convert back and round canonical Celsius to one decimal place.
- Unit changes affect display/form projection, not the physical meaning of canonical thresholds.
- Use a true em dash for absent values and an explicit `Unavailable` or `Stale` label.

## Temperature severity and hysteresis

Define:

```text
normal | warning | critical | unavailable
```

For a valid reading:

- Promote to warning immediately at or above warning threshold.
- Promote to critical immediately at or above critical threshold.
- Once critical, remain critical until strictly below `critical - 3 C`.
- After leaving critical, remain warning if still in the warning band.
- Once warning, remain warning until strictly below `warning - 3 C`.

For never-observed/stale/disconnected readings:

- Immediately become unavailable.
- Clear warning/critical presentation.
- Do not run thresholds against a null or old value.

Store oil and coolant severity in the long-lived car owner so navigation does not reset the state.
When settings thresholds change, re-evaluate against the current valid value without retaining an
impossible severity from the old thresholds.

Colors:

- Warning: named Tailwind amber utilities.
- Critical: destructive token or named Tailwind red utilities.
- Unavailable: muted tokens.
- Never communicate severity with color alone.
- No flashing, audio, acknowledgement or full-screen overlay.

## RPM stage derivation

Derive a presentation stage from effective settings:

```text
normal | stage_1 | stage_2 | redline | unavailable
```

- Invalid/disconnected RPM is unavailable.
- Below stage 1 is normal.
- Stage 1 is amber.
- Stage 2 is red/destructive.
- Redline and above receives strongest static red emphasis.
- Clamp visual bar position at redline, but preserve actual numeric RPM.
- Do not flash.

## Reusable instruments

### Telemetry value

One component handles label, value, unit and unavailable/status text without ever substituting
zero. It accepts already formatted display data rather than reading API state directly.

### Temperature gauge

Accept label, canonical/current display value, unit, telemetry status and derived severity. It is
responsible for local gauge styling only. Critical presentation must not obscure other dashboard
instruments.

### RPM bar

Render a wide segmented horizontal scale driven by redline and stages. Segment count and layout may
be selected for clear 800x480 rendering; they are presentation details, not persisted settings.
Use CSS/Tailwind and semantic markup unless an SVG materially improves scale rendering.

### Device footer

Render the button-pad role with its label, selected source and evidence-backed connection state.
Show output faults distinctly. A null connection is explicitly unknown; an absent role is an
unavailable capability. Do not infer device state from controller desire, network-node strings or
the separate simulated steering actuator. Keep the visible footprint minimal and expose detail
accessibly.

## Responsive and styling rules

- Target 800x480 landscape first and avoid horizontal overflow.
- Use current Oxanium typography.
- Use theme tokens and named Tailwind colors only.
- Keep car-specific styles out of global dev layout behavior.
- Use normal shadcn sizes and adjust locally where composition requires it; do not introduce a
  global control-size constant or pixel assertions.
- Settings may scroll vertically; primary overview/drive instruments should fit the viewport.

## Tests

Pure utilities:

- mph and temperature conversion including negative values and rounding.
- Fahrenheit threshold round-trip to nearest 0.1 C.
- All severity transitions and exact hysteresis boundaries.
- Critical-to-warning-to-normal demotion.
- Invalid data immediately clears severity.
- Settings changes re-evaluate severity.
- Every RPM stage and above-redline clamping.

Provider/data flow:

- Only one car snapshot subscription exists across route changes.
- Connection loss masks live readings as unavailable.
- Settings failure selects defaults and sets the fault flag.
- Settings recovery replaces defaults with authoritative data.
- Warning state survives car child-route navigation.

Components:

- No missing value renders numeric zero.
- Severity/status has visible text or accessible labeling beyond color.
- Device footer handles all states and missing entries.
- Instruments render in light and dark theme without raw colors.

## Completion criteria

- Every car page can consume one stable data/settings boundary.
- Conversion, freshness masking, hysteresis and RPM stages are pure and tested.
- Reusable instruments represent unavailable data honestly.
- Connection/settings failures have compact shared presentation.
- Foundation components fit the 800x480 shell without deciding final physical control sizes.
