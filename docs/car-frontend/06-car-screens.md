# Phase 6: In-car screens

## Goal

Build the complete initial overview, drive, steering and settings experiences using the Phase 5
foundation. The screens are purpose-built for the car layout rather than responsive variants of the
development workbench.

## Overview: `/car`

The overview is a sparse status screen.

### Steering status

Show:

- Mode: Auto, Manual or Maximum.
- Manual level as one-based `Level N of 8`.
- Effective assistance as rounded percent.
- Active saved-profile name when provenance matches a current saved revision.
- `Modified`/`Unsaved curve` when the active definition differs from its saved source.

The card is read-only. Do not add mode or assistance controls.

Resolve the profile name from the existing profile catalog query. An unavailable catalog must not
hide the active curve's functional state; show a neutral unknown/modified label instead.

### Temperatures and device role

- Show oil and coolant gauges using effective settings and Phase 5 severity.
- Invalid readings use an em dash and explicit state.
- Do not add speed or RPM to this page.
- Place the minimal button-pad source/connection footer at the bottom. Unknown evidence must remain
  visibly unknown.

## Drive: `/car/drive`

Use a modern motorsport hierarchy:

- Dominant rounded whole-number speed.
- Unit label from settings (`mph` or `km/h`).
- Wide segmented horizontal RPM bar.
- Smaller numeric RPM value.
- Oil-temperature gauge.
- Coolant-temperature gauge.

Primary instruments fit within the car content viewport without document scrolling at 800x480.
Temperature critical state remains within its gauge. RPM state is static color emphasis only. Stale
or disconnected values render as unavailable, never as frozen old readings.

## Steering: `/car/steering`

Create a dedicated touch/pointer editor around existing steering domain and chart behavior. Do not
mount the full development `SteeringCurveEditor` card.

### Supported workflow

1. Select an existing saved profile.
2. Copy its definition into a browser-local draft.
3. Drag points directly on the chart within existing domain constraints.
4. Compare draft curve with current speed marker/effective active assistance.
5. Revert the draft to the selected saved definition.
6. Choose Apply.
7. Confirm activation in a concise dialog.
8. Activate the complete draft through the existing curve activation endpoint.

Applying does not create or update a saved profile. Profile creation, rename, overwrite and deletion
remain in `/dev`.

### State rules

- Keep selected saved profile, local draft, dirty state, pending activation and last error explicit.
- Do not replace a dirty draft when a WebSocket active-state update arrives.
- Changing the selected profile with a dirty draft requires confirmation or an explicit discard.
- Revert does not mutate the backend.
- Apply remains disabled when the draft is invalid or already matches active state.
- Pending activation prevents duplicate submissions.
- Server response/snapshot is authoritative for active state.
- Include saved provenance only when the submitted draft exactly matches that saved revision;
  modified drafts activate without false saved provenance.
- Editing and Apply remain available at any speed.

### Chart interaction

- Reuse existing curve evaluation, constrained point update and Recharts primitives where doing so
  keeps behavior consistent.
- Support pointer events for mouse, pen and touch.
- Preserve fixed X positions and monotonic assistance constraints from the current curve domain.
- Show the active current-speed marker/effective assistance, never a draft value mislabeled active.
- Omit point tables, save/delete actions and development-only explanatory text.
- Fit the primary chart and actions in the 800x480 content area.

The confirmation dialog names the chosen source profile when available and states that the draft
will become active without overwriting the saved profile.

## Settings: `/car/settings`

Build a vertically scrollable local form with:

- Speed unit.
- Temperature unit.
- Oil warning and critical thresholds.
- Coolant warning and critical thresholds.
- Shift stage 1 RPM.
- Shift stage 2 RPM.
- Redline RPM.
- Light/Dark/System `ModeToggle`.

### Form behavior

- Initialize from authoritative settings, not fallback defaults.
- The rest of the car UI may use fallback defaults, but saving is disabled until a revision loads.
- Maintain a local draft; do not update global query data while typing.
- Unit-selector changes immediately re-project threshold inputs without persisting.
- Convert Fahrenheit edits back to canonical Celsius rounded to 0.1 C on Save.
- Run client validation matching backend ordering/ranges, while treating the server as authority.
- Use one explicit Save action for the complete document.
- Show pending, saved, validation, persistence and revision-conflict states.
- A failed Save retains the draft.
- On revision conflict, display current-revision context and offer Reload Current Settings; do not
  silently merge or discard.
- Reload requires confirmation if it would discard a dirty draft.
- No field auto-saves.
- Theme changes remain immediate/local and are independent from the settings Save action.

## Navigation and error policy

- All pages render inside the icon-only car layout.
- No page adds a link to `/`, `/dev` or developer tooling.
- Shared connection/configuration banners remain visible above page content.
- Page-specific mutation errors stay near the responsible action.
- Use concise operator-facing language, not API-port troubleshooting copy.

## Tests

Overview:

- Auto, Manual and Maximum labels.
- One-based manual level and effective percent.
- Saved, modified and unavailable profile labels.
- Valid/warning/critical/stale temperatures.
- Physical, emulated and observer source presentation, unknown connection evidence, output fault
  and missing-role fallback.

Drive:

- mph/km/h and C/F rendering.
- Never-observed/stale values are em dashes.
- Every RPM stage including above redline.
- Temperature state remains local to its gauge.

Steering:

- Selecting loads a local draft without activating.
- Drag updates only the draft and respects curve constraints.
- Dirty draft survives external active updates.
- Revert changes no backend state.
- Apply requires confirmation.
- Cancel performs no request.
- Confirm activates once and does not save.
- Modified draft does not claim false saved provenance.
- Selection change cannot silently destroy a dirty draft.
- Active marker never uses draft data.

Settings:

- Form initializes only from authoritative settings.
- Unit changes preserve canonical meaning.
- Client validation matches domain ordering.
- Save sends a complete document and expected revision.
- Success adopts authoritative response.
- Failure/conflict retains the draft.
- Conflict reload behavior is explicit.
- Theme change does not mutate application settings.

Routes:

- Each page renders at its stable URL.
- Car pages contain no escape link.
- Shared banner remains during child navigation.

## Completion criteria

- All four screens implement the specified workflow and data states.
- Overview and drive primary content fit at 800x480 without horizontal overflow.
- Steering keeps draft, saved and active state distinct.
- Settings are atomic, revision-aware and canonical-unit safe.
- Missing data and failures remain visible and honest.
- No physical-output, BMW decoding or kiosk authority is added.
