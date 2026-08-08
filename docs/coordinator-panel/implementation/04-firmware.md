# Workstream 4: QT Py firmware and upload workflow

Status: closure review.

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

- Base commit: `84f11c84a5a5d62ff73a747a891630b91e0cc738`
- Outcome: Added the five-pixel QT Py RP2040 firmware, host-native tests, repository-level upload
  script, and device wiring/build/upload documentation. The firmware immediately renders startup,
  accepts exactly the six final semantic status lines, reports debounced presses, and implements
  first-status, established-link, recovery, and graceful-off timing.
- Files changed: `devices/coordinator-panel/platformio.ini`,
  `devices/coordinator-panel/include/panel_logic.h`,
  `devices/coordinator-panel/src/main.cpp`,
  `devices/coordinator-panel/test/test_panel_logic/test_main.cpp`,
  `devices/coordinator-panel/README.md`, `scripts/coordinator_panel_upload.sh`, and this record.
- Firmware structure and directness justification: One header contains the small hardware-free
  parser, status timer, button debounce, and six renders so native tests exercise the meaningful
  protocol and timing risks directly. The Arduino entry point owns only A0 input, the A3 five-pixel
  strip, and the QT Py pins labelled TX/RX through `Serial2`; the board variant maps `Serial1` to
  A1/A0, so using it would conflict with the required button pin. Every hardware pixel write comes
  from the render function's 127/255 per-channel ceiling. No configuration, persistence, protocol
  machinery, or coordinator behaviour was added. A simplification pass removed unnecessary
  lifetime indirection and left one direct nonblocking loop.
- Verification: PlatformIO 6.1.18 `pio test -e native` passed all four focused tests; `pio run -e
  qtpy_rp2040` built successfully for `adafruit_qtpy` (40,092 bytes flash, 8,804 bytes RAM). `bash
  -n scripts/coordinator_panel_upload.sh`, its executable-bit check, and `git diff --check` passed.
  `shellcheck` was unavailable. No upload was attempted without attached hardware.
- Hardware checks still required: Actual USB upload/bootloader recovery; five-pixel order and GRB
  colour; perceived travelling-white, dim-white, and cyan-pulse brightness; A0 debounce; labelled
  3.3 V UART at 115,200 baud; first-status and established heartbeat faults/recovery; graceful-off
  latch; and operation through the fused, diode-protected harness. USB and the Pi harness must not
  be connected together.
- Specification drift: `None`.

## Independent review

- Reviewer: `Codex /root/ws4_review`
- Verdict: `Accepted`
- Required findings: `None`. The clean QT Py build targets the RP2040 board and its variant maps
  `Serial2` to the pins labelled TX/RX (GPIO20/GPIO5), independently of A0 (GPIO29). The firmware
  parses only the six exact newline-terminated status payloads in one 63-byte bounded parser,
  discards oversized input until the next newline, and emits exactly `BUTTON\n` on each debounced
  pressed transition. All five A3 pixels are written exclusively from a renderer capped at 127 per
  channel. Unsigned elapsed-time subtraction protects the 60-second startup, three-second
  established-link, and 30 ms debounce boundaries across `millis()` rollover; valid status
  immediately recovers a timeout, while valid `off` remains latched. The upload script follows the
  existing repository-relative/optional-`UPLOAD_PORT` convention and the device README documents
  bootloader recovery and disconnecting the complete Pi harness before USB.
- Optional observations: `None`.
- Questions for orchestrator: `None`.

## Resolution

- Finding dispositions: No required findings; no remediation was needed.
- Simplification/deletion pass: Reread the parser, timing, debounce, render, and hardware loop as a
  complete path after review. They retain one display value, one bounded line buffer, and one
  direct nonblocking loop; there are no duplicate states, façade exports, compatibility paths,
  configuration hooks, persistence, retries, or implementation-detail tests to remove. The four
  native tests remain focused on the protocol, timing, debounce, and brightness risks.
- Final verification: A clean `pio run -e qtpy_rp2040 --target clean && pio run -e qtpy_rp2040`
  succeeded for the QT Py RP2040 (40,092 bytes flash, 8,804 bytes RAM); `pio test -e native`
  passed all four tests. `bash -n scripts/coordinator_panel_upload.sh`, the script executable-bit
  check, `git diff --check`, and the `.pio/` ignore check passed. Physical upload and all hardware
  checks listed in the implementation handoff remain pending.

## Closure review

- Verdict: `Accepted`
- Remaining required findings: `None`. No remediation was required after the accepted independent
  review, and the reviewed firmware, native tests, upload script, and device documentation remain
  unchanged. No release-blocking defect was introduced.
- Accepted commit: `TBD`
