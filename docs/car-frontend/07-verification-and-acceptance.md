# Phase 7: Integrated verification and acceptance

## Goal

Verify the complete routed frontend and supporting coordinator work as one integrated feature.
Focused phase tests are prerequisites, not substitutes for repository-wide checks and visual
inspection at the intended 800x480 viewport.

## Preconditions

- Phases 1-6 are at least `Implemented` in `implementation-log.md`.
- No phase has an unresolved data-contract or migration blocker.
- The working tree is understood and unrelated changes are preserved.
- Backend simulator and frontend development server can run together with an isolated test database.

## Automated repository checks

Run from repository root unless the command requires `frontend/`:

```text
uv run pytest -q
uv run ruff check .
uv run mypy coordinator/src/e87canbus
uv run python scripts/generate_custom_protocol.py --check
bash -n scripts/*.sh

pnpm test
pnpm lint
pnpm typecheck
pnpm build

git diff --check
```

Use the package-manager version declared by the frontend. Do not update unrelated dependencies or
regenerate protocol artifacts unless the implementation genuinely changes their source.

Record exact counts, warnings and failures in the implementation log. A pre-existing warning may
be documented, but a new warning caused by this roadmap must be resolved or explicitly blocked.

## Contract acceptance

Verify through API tests or direct inspection:

- Existing version-1 SQLite database upgrades once to version 2.
- Profiles and settings survive restart.
- Settings conflicts preserve the committed winner.
- All simulator telemetry uses synthetic extended PT-CAN identifiers.
- Live `ProtocolRouter` ignores those identifiers.
- Per-signal silence produces stale/null independently.
- Device role projection and reset are deterministic.
- Initial and reconnect WebSocket snapshots contain complete engine and device projections.
- Settings change publication causes another client to refetch.
- Existing steering, speed, button-pad and trace behavior has no regression.

## Collaborative-browser setup

Use the product-native collaborative preview. Start the backend with a temporary or explicitly
selected development database, start Vite, and navigate through the environment port rather than a
host-specific URL. Set the viewport to 800x480 when the preview supports it; otherwise use its
closest fixed viewport and record the limitation.

Do not use a production profile database for destructive settings/profile checks.

## Visual matrix at 800x480

Inspect both light and dark themes:

- `/car` overview.
- `/car/drive`.
- `/car/steering`.
- `/car/settings`.
- Connection unavailable/reconnecting banner.
- Settings-fallback indicator.
- Never-observed engine telemetry.
- Stale engine telemetry after silence.
- Normal, warning and critical oil temperature.
- Normal, warning and critical coolant temperature.
- RPM below stage 1, at stage 1, at stage 2 and at/above redline.
- Emulated, observer and absent button-pad presentation; known and unknown connection evidence.
- Steering dirty state and confirmation dialog.
- Settings validation, save success and revision conflict.

For every view check:

- No horizontal document overflow.
- No clipped labels, units, icons, focus rings or dialogs.
- Primary overview/drive instruments fit without vertical document scrolling.
- Settings can scroll to every field and action.
- Contrast is readable in both themes.
- Status is not communicated by color alone.
- Em dashes/status labels replace missing numeric values.
- Sidebar active/focus states remain clear.
- No `/car` surface exposes a development/chooser link.

Assess touch usability qualitatively. Do not reject solely against an arbitrary pixel measurement
and do not add fixed-size assertions. Record controls that should be revisited on the physical
display.

## Functional browser scenarios

### Routing and theme

1. Load `/`, enter `/dev`, return with the dev home control and enter `/car`.
2. Direct-load every car child route and refresh it.
3. Visit an unknown car route and confirm recovery exposes only `/car`.
4. Change theme in dev and confirm it persists.
5. Change theme in car settings and confirm it is independent of settings Save.

### Telemetry and warnings

1. Use `/dev` to set speed, RPM and both temperatures.
2. Observe `/car/drive` using the authoritative snapshot.
3. Cross warning and critical thresholds, then lower values around the 3 C hysteresis boundaries.
4. Silence one signal and advance/wait past one second; only it becomes stale.
5. Stop/restart the backend and confirm live values become unavailable during loss/reconnection.

### Device role and observation

1. Run `/dev` with the emulated role and confirm explicit press/release controls are enabled, use
   generated wire traffic and display decoded LED observation.
2. Run with the observer role and confirm the source is labeled, connection/observation are unknown,
   wire controls are disabled and synchronized semantic controller commands remain available.
3. Reset and confirm the session identity changes, old virtual resources are released and device
   and vehicle projections return to their documented initial values.

### Settings

1. Change speed and temperature units plus thresholds/RPM stages and Save.
2. Reload and restart the coordinator; confirm persistence.
3. Edit Fahrenheit thresholds and confirm canonical Celsius round-trip.
4. Create a stale revision using two clients; confirm conflict retains the losing draft and offers
   explicit reload.
5. Make settings unavailable; confirm car screens use defaults with a fault indicator and Save is
   disabled.

### Steering

1. Select a saved profile and drag a point.
2. Confirm no request or runtime change occurs during drag.
3. Cancel Apply and confirm no activation.
4. Confirm Apply and verify active state changes without a profile database write.
5. Receive an external active update while dirty and confirm the draft survives.
6. Attempt to change profile while dirty and confirm explicit discard handling.

## Desktop regression

At a normal desktop viewport:

- Mode chooser is balanced and keyboard navigable.
- `/dev` retains its current workbench content, grids, trace and dialogs.
- Vehicle and explicit emulator controls do not make existing cards unusable.
- Dev connection error continues to provide detailed troubleshooting.

## Documentation and handoff

- Update frontend/coordinator README files for new routes, commands, settings path and simulation
  boundaries where appropriate.
- Ensure public JSON shapes in docs agree with implementation.
- Append a Phase 7 log entry containing exact automated results and browser scenarios.
- Record any physical-display-only tuning as remaining work, not as silently verified.

## Completion criteria

- All relevant automated checks pass.
- Every matrix state has been visually inspected in light and dark at the target viewport or a
  recorded tooling limitation remains.
- Required browser workflows pass without data-state ambiguity.
- Existing dev/simulator behavior is regression checked.
- Migration, reconnect, conflict and stale-data failure modes are demonstrated.
- No phase is marked `Verified` without satisfying its own completion criteria.
- Remaining physical touchscreen tuning is explicitly documented for the user rather than encoded
  as an arbitrary automated size rule.
