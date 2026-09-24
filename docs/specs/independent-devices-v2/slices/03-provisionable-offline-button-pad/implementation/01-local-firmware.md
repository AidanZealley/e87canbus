# Workstream 1: local firmware and CAN reception

Status: not started.

## Task packet

### Outcome

An ESP32 button pad renders a safe local scene, scans the physical keys, and receives K-CAN frames
in listen-only mode without Wi-Fi or coordinator access.

### Scope

- Create `devices/button-pad/` with PlatformIO ESP32 Dev Module, explicit 8 MB flash and the
  checked-in partition table from the board reference.
- Implement the small ESP32 renderer and strict whole-envelope validation against the Slice 02
  scene. Restore one `e87cfg` NVS value atomically or use a compiled safe scene. Leave an invalid
  stored value unable to change any active scene entry.
- Scan NeoTrellis using measured I2C pins and physical order. Assigned presses flash locally at
  the safe brightness ceiling; unassigned presses do nothing. Do not implement remote delivery.
- Configure TWAI GPIO26/27 at 100 kbit/s, listen-only. Bound frame draining, accept valid standard
  frames and discard payloads. Do not decode, trace, transmit or change LEDs from CAN contents.
- Record assembled PCB revision, pins, logical mapping, measured brightness ceiling and bench
  wiring in the device README. Add a native PlatformIO test environment for scene validation.
- Pin PlatformIO as an `e87ctl` dependency and update both lockfiles so `uv run pio` works in a
  fresh checkout. Workstream 2's build command uses this same executable.

### Non-goals

Wi-Fi, TLS, HTTP, SSE, coordinator feedback, BMW signal decoding, SD use, OTA and a shared
firmware framework. The identity partition is reserved here; provisioning owns its contents.

### Initial ownership

`devices/button-pad/**`, `e87ctl/pyproject.toml`, root `uv.lock` and `e87ctl/uv.lock` for
PlatformIO. The coordinator-panel project stays separate. Any obsolete AVR material identified
here is handed to Workstream 3 for removal, not preserved as an adapter.

### Required seams

The `e87cfg` partition and envelope format follow the first-delivery document; no guessed
alternate schema. Workstream 2 consumes this PlatformIO project and partition table. Workstream 3
uses the partition names and offsets for safe flashing.

### Acceptance criteria

- PlatformIO builds for the selected ESP32 with explicit 8 MB layout.
- Boot does not wait for network state; compiled scene is safe on absent or invalid `e87cfg`.
- Native scene tests prove complete valid input applies and invalid input leaves the prior scene
  intact. Workstream 3 owns physical power-cycle, press and CAN proof at H2.
- The compiled scene and renderer use the H1 measured current limit; the firmware contains no
  guessed LED ceiling.
- README records measured hardware facts, revision and bench wiring.

### Targeted verification

Run `uv run pio run -d devices/button-pad` and
`uv run pio test -d devices/button-pad -e native`. The lead records the build and native test
results. Physical behavior remains pending at H2 in Workstream 3.

### External validation

- Gate and placement: H1 before pin-dependent code.
- Status: Pending.
- Candidate and instructions: inspect the assembled board and NeoTrellis wiring, confirm exposed
  I2C pins and each key position. Remove the microSD card before flashing a minimal LED test.
  Use a current-limited bench supply and initially low brightness. Measure full-white current
  across all 16 LEDs, increasing only within
  the supply and board limits, and choose a ceiling at or below the measured safe value. Keep
  vehicle power and CAN disconnected during this measurement.
- Required evidence: PCB revision, pin and key map, supply setting, measured full-white current,
  chosen safe brightness and bench wiring.
- Attempts and lasting decisions: `TBD`
- Resume condition: measured H1 facts are recorded before pin-specific implementation.

## Implementation handoff

- Base commit: `TBD`
- Outcome: `TBD`
- Files changed: `TBD`
- Decisions: `TBD`
- Verification: `TBD`
- Known limitations or external checks: `TBD`
- Specification drift: `TBD`

## Independent review

- Reviewer: `TBD`
- Verdict: `TBD`
- Required findings: `TBD`
- Optional observations: `TBD`
- Questions: `TBD`

## Resolution

- Finding dispositions: `TBD`
- Simplification/deletion pass: `TBD`
- Final verification: `TBD`

## Closure review

- Verdict: `TBD`
- Remaining required findings: `TBD`
