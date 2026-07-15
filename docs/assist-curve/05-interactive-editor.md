# Phase 5: Interactive curve editor

## Goal

Build a shadcn/Recharts curve editor in the shared React frontend. A user can drag fixed-speed
points vertically, compare draft/active/saved state, apply the draft, and manage saved profiles.

The first implementation uses `linear-v1`. It must not draw a smooth line until Phase 6 changes the
runtime algorithm.

## Component structure

Follow `frontend/AGENTS.md`. A likely structure is:

```text
src/components/steering-curve-editor/
├── SteeringCurveEditor.tsx
├── index.ts
├── types.ts
├── utils.ts
└── components/
    ├── curve-chart/
    │   ├── CurveChart.tsx
    │   ├── DraggableCurvePoint.tsx
    │   └── index.ts
    ├── profile-selector/
    │   ├── ProfileSelector.tsx
    │   └── index.ts
    └── curve-actions/
        ├── CurveActions.tsx
        └── index.ts
```

Keep domain-shaped API types in the API boundary and editor-local view types in `types.ts`. Integer
units remain authoritative even if chart values are projected to km/h and percent.

## Chart choice

Add the shadcn chart component and Recharts v3. Use:

- `ChartContainer` for theme and sizing.
- Numeric `XAxis` and `YAxis` with explicit domains.
- `Line` with `type="linear"` for the active calculation.
- Custom SVG point children or custom dots for drag handles.
- Recharts scale and inverse-scale hooks to translate values and pointer coordinates.

Do not rely on HTML drag-and-drop. Use pointer events, which support mouse, pen and touch through
one interaction model.

## Drag interaction

Only Y changes. X always comes from the fixed version-1 grid.

On pointer down:

1. Record the point index.
2. Capture the pointer on the SVG handle.
3. Suppress chart tooltip behavior for the active pointer if it interferes.

On pointer move:

1. Convert the pointer to a chart-relative Y coordinate.
2. Convert pixels to the Y-axis data value.
3. Clamp to `0..1000` per-mille.
4. Snap to the chosen increment, initially 10 per-mille (1%).
5. Enforce the domain monotonic constraint against neighboring points.
6. Replace only browser draft state.

On pointer up/cancel, release capture and retain the draft. Use a larger transparent hit circle
than the visible point so it works on the five-inch touchscreen. Set `touch-action: none` only on
the interactive chart/handles, not the whole page.

## Accessible precision controls

Dragging cannot be the only input mechanism. Provide:

- A focusable handle or adjacent numeric field for every point.
- Arrow keys for one increment and Page Up/Down for a larger increment.
- A visible speed label and assistance value for the focused point.
- Proper accessible names such as `Assistance at 60 km/h`.
- Focus indication and error/status announcements.

The chart should remain understandable with tooltips disabled. Use assistance percent on the Y
axis and speed km/h on the X axis.

## Editor state machine

Track explicit values rather than deriving everything from one mutable array:

```text
activeDefinition
draftDefinition
selectedSavedProfile
savedCatalog
pendingAction
lastError
```

Derive:

- `draftMatchesActive` from definition fingerprint/canonical equality.
- `draftMatchesSelectedSaved` likewise.
- Whether Apply, Save, Revert and Delete are enabled.

Never replace a dirty draft because a background Socket.IO snapshot arrives. If active state
changes elsewhere, retain the draft and show that its base is stale, offering explicit reload or
compare actions.

## Actions and feedback

- **Apply:** activate the current draft; disable while pending; replace active projection only from
  authoritative Socket.IO state after the acknowledgement.
- **Save:** create or update using the selected saved revision; update local catalog from the
  committed server response.
- **Save as:** require a new name and create a new profile ID.
- **Revert:** copy the authoritative active definition into draft after confirmation if dirty.
- **Load saved:** copy the selected saved definition into draft without applying it.
- **Delete:** require explicit confirmation and expected revision.

Show compact, persistent badges for Draft changed, Saved, Active and conflict. Do not communicate
these states by color alone.

## Current-speed visualization

When a speed sample is available, draw a non-interactive marker on the active curve and show the
current evaluated assistance. It must use active, not draft, values. A separate preview readout may
show the draft result at the same speed, clearly labeled.

Stale or absent speed should hide the evaluated marker and retain the existing warning semantics.

## Responsive behavior

- Test at the proposed five-inch display resolution and ordinary desktop sizes.
- Maintain a minimum chart height so Recharts can measure correctly.
- Keep action targets large enough for in-car touch use.
- Avoid dialogs or tooltips that cover the point being dragged.
- Do not make editing available on the glanceable drive screen; place it in a deliberate settings
  surface.

## Tests

### Pure utility tests

- Integer/display conversions.
- Clamp, snap and neighbor monotonic bounds.
- Definition equality/fingerprint handling.
- Dirty-state derivation.
- Active versus draft evaluation.

### Component tests

- Pointer movement updates only Y and only the selected point.
- Pointer cancel ends dragging safely.
- Keyboard and numeric input produce the same result as dragging.
- Apply does not save and Save does not apply.
- Dirty draft survives an external active-state update.
- Revision conflict retains the draft and offers reload.
- Pending actions prevent duplicate requests.
- Active/current-speed marker never uses draft data.

### Browser verification

- Mouse and touch/pen emulation on desktop.
- Actual target touchscreen before in-car use.
- Light/dark theme, narrow layout and reconnect behavior.
- Drag at chart extremes and across scrollable page boundaries.

## Completion criteria

- A user can edit, apply, save, load, revert and delete without confusing the three states.
- Every point has drag and non-drag input methods.
- No API or disk activity occurs during pointer movement.
- The line visibly matches `linear-v1` runtime output.
- External changes and revision conflicts never silently destroy a draft.
