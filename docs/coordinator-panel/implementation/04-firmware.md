# Workstream 4: QT Py firmware and upload workflow

Status: not started.

## Task packet

### Outcome

Add the minimal PlatformIO firmware for the QT Py RP2040 and the same repository-level USB upload
experience used by the other devices. Host verification should cover meaningful firmware logic;
physical rendering and UART remain explicitly unverified until bench work.

### Scope

- Add `devices/coordinator-panel/` with one QT Py RP2040 PlatformIO environment.
- Render the six received semantic display values on exactly five pixels through BFF pin A3.
- Enforce the hard 50% per-channel ceiling.
- Start the travelling white animation immediately.
- Parse bounded `STATUS <display>` lines and send one `BUTTON` line per debounced A0 press.
- Implement the 60-second first-status grace, three-second established timeout, immediate recovery,
  and latched graceful `off` behaviour.
- Keep testable parsing, timeout, debounce, and display selection separate from hardware calls only
  where doing so directly enables valuable host tests.
- Add `scripts/coordinator_panel_upload.sh` with optional `UPLOAD_PORT` matching the existing device
  workflow.
- Document the firmware build, USB upload, bootloader recovery, pins, and the requirement to unplug
  the Pi harness.

### Non-goals

- Coordinator/hotspot state derivation in firmware.
- Protocol versions, acknowledgements, checksums, sequences, negotiation, or retries.
- Runtime configuration, EEPROM state, remote updates, or arbitrary pixel commands.
- Exact browser animation-frame matching.
- Live USB while connected to the Pi harness.

### Initial ownership

- `devices/coordinator-panel/**`.
- `scripts/coordinator_panel_upload.sh`.
- Device-local/native firmware tests if they add meaningful confidence.
- This workstream record.

Do not change Pi protocol code. If the accepted UART contract cannot be implemented as written,
return the issue to the orchestrator and workstream 3 owner.

### Required seams

- Receive exactly the six-value `STATUS <display>\n` contract accepted in workstream 3.
- Emit exactly one `BUTTON\n` per debounced physical press.
- Use labelled QT Py UART pins, A0 button with internal pull-up, and A3 NeoPixel data.

### Acceptance criteria

- PlatformIO resolves dependencies and builds for the QT Py RP2040.
- Firmware has one bounded line parser and ignores invalid input.
- Brightness cannot exceed the agreed limit through any appearance/animation path.
- Startup, ready, hotspot waiting, connected, fault, and off select the agreed rendering.
- Heartbeat timing and off behaviour match the specification.
- Upload script uses repository-relative paths and optional `UPLOAD_PORT` consistently with the
  existing button-pad script.
- Tests focus on state/parser/timing risks rather than every animation frame or malformed byte.

### Targeted verification

```bash
cd devices/coordinator-panel && pio run
cd devices/coordinator-panel && pio test -e native  # only if a native test environment is added
```

The agent also runs the upload script's non-destructive/static checks available without hardware
and records that an actual upload remains pending.

## Implementation handoff

- Base commit: `TBD`
- Outcome: `TBD`
- Files changed: `TBD`
- Firmware structure and directness justification: `TBD`
- Verification: `TBD`
- Hardware checks still required: `TBD`
- Specification drift: `TBD`

## Independent review

- Reviewer: `TBD`
- Verdict: `TBD`
- Required findings: `TBD`
- Optional observations: `TBD`
- Questions for orchestrator: `TBD`

## Resolution

- Finding dispositions: `TBD`
- Simplification/deletion pass: `TBD`
- Final verification: `TBD`

## Closure review

- Verdict: `TBD`
- Remaining required findings: `TBD`
- Accepted commit: `TBD`
