# E87 CAN Bus Project — Context Document

> This document summarises the project goals, vehicle platform, hardware architecture, software architecture, and open questions. It is intended as a starting point for AI-assisted development (Claude Code, Windsurf, etc.) so that the full context of design decisions is available without re-explaining from scratch.

---

## Vehicle Platform

- **Car:** 2005 BMW E87 130i (5-door hatch) — UK/Euro spec, not sold in the US
- **Engine:** N52 (silver top) — DME likely **MSD80**
- **Use case:** Track only — road legality is not a concern
- **Interior:** Largely stripped. iDrive controller removed (leaving a dangling K-CAN connector). Interior fusebox exposed. Stereo and associated controls removed.
- **Steering rack:** Retrofitted E9x M3 rack with **Servotronic**; its valve and electrical
  interface have not yet been characterized for this project

### CAN Network Notes

The E87 shares the same CAN architecture as the E90. E90 documentation, DBC files, and message IDs are broadly applicable.

| Bus | Speed | Key Modules |
|---|---|---|
| K-CAN (Komfort) | 100 kbit/s | Body, lighting, MFL steering wheel buttons, iDrive, JB (junction box) |
| PT-CAN (Powertrain) | 500 kbit/s | DME (engine), EGS (gearbox), instrument cluster |
| F-CAN (Chassis) | 500 kbit/s | DSC (ABS/traction control), wheel speed sensors |
| MOST | Optical | Infotainment — not used in this project |

**Important:** The OBD-II port is gated behind a ZGW (central gateway module) which filters traffic. Do not rely on it for raw bus access. Tap buses directly at module connectors.

---

## Physical CAN Access Points

| Bus | Best tap point | Notes |
|---|---|---|
| K-CAN | Dangling iDrive connector behind dash | Already disconnected, clean access, twisted pair visible |
| K-CAN (alternative) | Junction Box (JB) main harness connector | JB is a primary K-CAN node |
| PT-CAN | Junction Box area / engine bay near DME | JB bridges PT-CAN; also accessible at DME connector |
| F-CAN | DSC module connector in engine bay | Candidate tap for vehicle-speed capture |

### Wiring / Tap Method

Preferred approach in order of preference:
1. **Matching OEM connector** — find the correct male plug that mates with the iDrive female connector (likely Molex MX150 or TE Connectivity series). Use ISTA wiring diagrams for the exact part number. Zero modification to the car loom.
2. **Posi-Tap connectors** — pierce-type, reversible, no wire cutting. Use correct size for BMW loom wire gauge (typically 0.35–0.75mm²).
3. **Wago 221 lever nuts (3-port)** — cut wire, rejoin plus tap wire. Best vibration resistance of the non-connector options. Wrap in self-amalgamating tape.

Avoid scotchlocks. Avoid relying on the OBD port for permanent installation.

---

## Planned Features

### 1. Speed-Sensitive Power Steering (Servotronic Control)

**Product goal:** Select speed-sensitive assistance in Auto mode, bounded fixed assistance levels in
Manual mode, and a temporary maximum-assistance selection from the button matrix.

The current implementation proves only hardware-independent control behavior. It selects a
dimensionless `0.0..1.0` assistance value in the simulator. The synthetic simulator speed frame is
not a BMW definition, and the simulated zero-assistance fallback is not evidence of a physical safe
state.

**Physical evidence still required:**

- Verified vehicle-speed captures, including source network, arbitration ID, payload decoding,
  cadence, malformed-traffic behavior, and loss behavior.
- The rack valve's command transport, command range and polarity, response to commands, and any
  available feedback.
- The electrical safe state and behavior during power loss, disconnection, coordinator failure, and
  stale commands.
- The actuator interface and watchdog architecture. It is not yet known whether output should be
  driven by the Pi, a separate controller, an existing vehicle module, or another arrangement.

No physical command value, electrical design, driver component, output waveform, BMW speed ID, or
live actuator grant is selected. Candidate IDs found in old notes remain unverified research and
must not be added to executable protocol code without named captures from this vehicle.

---

### 2. DSC (Traction Control) Off — Single Button Press

**Goal:** Disable DSC/traction control with a single button press. Stock behaviour requires holding the DSC button for several seconds.

**Method:**
- Candump F-CAN or PT-CAN while performing the stock long-press DSC disable
- Identify the CAN frame that the DSC module acts on (appears after the required hold duration)
- Replay that exact frame from the Pi on button press

**Unverified research:** `0x316` and `0x399` appear in old candidate notes. They are not executable
definitions or replay instructions; identify the behavior from named captures on this car before
promoting either value.

**Rolling counter caveat:** Check captured frames for a byte that increments with each transmission. If present, static frame replay won't work — need to implement the counter logic. Inspect 5–10 captures of the same action to identify incrementing bytes.

---

### 3. High Beam Strobe / Flash-to-Pass

**Goal:** Quickly strobe high beams (flash-to-pass style, as used in motorsport) triggered by a single button press.

**Method:**
- Candump K-CAN while pulling the stalk for normal flash-to-pass
- Identify the lighting command frame (sent by MFL/stalk to LCM — Light Control Module)
- Pi sends the frame in a rapid loop for the desired strobe duration

**Suggested pattern:** ~5 cycles of 80ms on / 80ms off (tune to preference).

**Note:** Space messages appropriately — don't flood the LCM. Flash-to-pass is a momentary action so rolling counters are less likely here than on stateful commands, but verify.

---

### 4. Steering Wheel Button (MFL) Remapping

**Goal:** Repurpose the existing MFL (Multi-Functional Steering Wheel) buttons for project controls since the stereo and other original consumers are removed.

**Available buttons (typical E87 MFL):**
- Volume up / down
- Next / Previous track
- Phone pickup / hangup
- Mode / menu

**Method:**
- Candump K-CAN while pressing each MFL button individually
- Record CAN ID and data bytes for press and release events
- Hold each button 2–3 seconds to capture any long-press distinct frames
- Pi listens for these IDs/data patterns and triggers actions

**Rolling counter on MFL:** MFL messages often include an incrementing nibble in one data byte. When listening (not sending), mask out the counter byte during pattern matching. This is receive-only so counter logic is not needed.

**Suggested button mapping:**

| Button | Action |
|---|---|
| Vol + | Assistance level up (manual mode) |
| Vol − | Assistance level down (manual mode) |
| Next / Prev | Mode toggle or secondary functions |
| Phone pickup | Flash-to-pass strobe |
| Phone hangup | DSC off toggle |

---

## Hardware Architecture

### Devices

| Device | Role | Bus connection |
|---|---|---|
| Raspberry Pi Zero 2W + CAN interfaces | Central hub, runs all logic | K-CAN, PT-CAN, and F-CAN |
| Arduino (small CAN board) | Button matrix node | K-CAN |
| Adafruit NeoTrellis | RGB button matrix input/output | Via Arduino (I2C) |
| Future steering actuation boundary | Unknown pending hardware evidence | Not selected |

### CAN HAT Notes

- MCP2515-based HATs are standard and well supported
- Default clock config on most MCP2515 boards is 500k — must reconfigure to 100k for K-CAN
- Three CAN interfaces are planned on the Pi; hardware selection and physical compatibility remain
  pending
- `python-can` treats them as separate named interfaces (`can0`, `can1`, and `can2`)

### Power

- Pi needs stable 5V — use an automotive-grade DC-DC converter (Pololu or DROK) with input capacitance
- Do not power Pi directly from ignition-switched line until tested — brownout during boot can corrupt SD card
- Steering actuation power and protection are not designed; they depend on the verified actuator
  boundary and electrical safe state

### Physical CAN Topology

```
K-CAN  (100k) ──── Pi ──── Arduino + NeoTrellis
                   │
                   └─────── Vehicle K-CAN nodes

PT-CAN (500k) ──── Pi ──── Vehicle PT-CAN nodes

F-CAN  (500k) ──── Pi ──── Vehicle F-CAN nodes
```

These are three independent physical networks. The coordinator does not automatically forward
frames between them; future domain-level bridging must be explicit application behavior.
The physical steering actuation topology is deliberately omitted because it has not been selected
or verified.

---

## Software Architecture

### Monorepo Structure

```
e87canbus/
├── coordinator/                   # Central Raspberry Pi application
│   ├── src/e87canbus/             # Project-specific Python import package
│   │   ├── application/           # Authoritative state and decisions
│   │   ├── features/              # Pure steering-assistance calculations
│   │   ├── protocol/              # Generated wire values and CAN codecs
│   │   ├── adapters/              # Real hardware and OS integrations
│   │   ├── simulation/            # Virtual CAN and device implementations
│   │   ├── api/                   # FastAPI and Socket.IO interface
│   │   └── cli/                   # Executable entry points
│   └── tests/
├── devices/
│   ├── button-pad/                # NeoTrellis/CAN PlatformIO project
│   └── servotronic-controller/    # Future actuator-controller firmware
├── frontend/                      # Simulator and in-car React UI
├── protocol/                      # Protocol source TOML, generated docs, and DBC notes
├── docs/
├── scripts/
└── deploy/
```

### Coordinator — Python Stack

- **Runtime:** Python 3.11+
- **Dependency management:** `pyproject.toml` (PEP 621)
- **Key libraries:** `python-can` for SocketCAN, FastAPI/Uvicorn for the simulator API, and
  `cantools` reserved for verified DBC work
- **Concurrency model:** one synchronous `python-can` reader thread per interface feeding a shared
  bounded queue; the main thread is the sole kernel owner and runs periodic timers

Readers timestamp frames at receipt. The kernel decodes each ordered input, applies a pure immutable
state transition, commits a revision, then returns effects to the composition. Effects can write
only through explicitly granted, rate-limited transmitter capabilities. The visual simulator uses
the same decode, transition, commit, effect, and policy path through simulated external CAN nodes.

Verified speed decoding and an isolated actuator boundary are prerequisites for the later steering
failsafe. No speed ID, DSC replay, strobe command, or Servotronic output is executable without
capture or hardware evidence.

### Arduino — PlatformIO

Use **PlatformIO** (VS Code extension) instead of Arduino IDE. Enables:
- Version-controlled `platformio.ini` dependency management
- CLI builds and flashes
- Proper monorepo integration

```ini
[env:arduino_uno]
platform = atmelavr
board = uno
framework = arduino
lib_deps =
    adafruit/Adafruit NeoTrellis
    mcp_can
```

**Current button-pad milestone responsibilities:**
- Emit bench-only synthetic press/release events on `0x700`.
- Validate complete DLC-8 LED snapshots received on `0x701` and replace all 16 stored colours only
  after every nibble is known.
- Report the stored values through one rendering boundary. Physical NeoTrellis scanning and pixel
  rendering remain unimplemented until the actual hardware topology and electrical limits are
  verified.

### Provisional K-CAN Message Protocol (Coordinator ↔ Button Pad)

The current bench and simulation use `0x700` and `0x701` on K-CAN. They must not be treated as
collision-free merely because they are in the high standard-ID range.

| ID | Direction | Description |
|---|---|---|
| `0x700` | Button pad → coordinator | Button event (byte 0 = button index, byte 1 = press/release) |
| `0x701` | Coordinator → button pad | Complete 16-colour LED snapshot (DLC 8; even index in low nibble, odd index in high nibble) |

`protocol/custom.toml` is the source of truth. Its generator updates the Python constants, firmware
header, and the marked table section in `protocol/custom_ids.md`; `--check` detects drift.

Validate both IDs against a real K-CAN capture before any in-car transmission. Future simulated
speed, RPM, lighting, oil-temperature, and coolant-temperature signals must be encoded as real
network-specific CAN frames and pass through the same protocol-routing path as physical traffic.
No BMW DBC definition is verified or active in the current milestone.

---

## Development Environment

- **IDEs:** VS Code, Windsurf
- **Version control:** Git monorepo, hosted on GitHub
- **Pi development:** SSH into Pi or `rsync` / `git pull` to deploy
- **Arduino development:** PlatformIO extension in VS Code
- **AI pairing:** Claude Code pointed at repo root — see repo structure above

---

## First Steps / Recommended Order of Work

1. **Verify ISTA laptop is working** — needed for E87 wiring diagrams and OEM connector part numbers
2. **Identify iDrive connector part number** from ISTA — source matching male plug
3. **Connect Pi HAT to K-CAN via iDrive connector** — verify bus access with `candump`
4. **Sniff K-CAN session:** press every MFL button (short and long), operate lights. Log everything.
5. **Cross-reference with E90 DBC files** — confirm message IDs match. Community sources: search GitHub for `e90_can` or `bmw_dbc`
6. **Connect second CAN interface to F-CAN** — capture candidate vehicle-speed traffic and verify
   its identity and payload from evidence rather than a placeholder ID
7. **Sniff F-CAN session:** drive at various speeds, hold DSC button for full duration, log DSC-off event
8. **Characterize the steering actuator boundary safely** — document command transport, range,
   polarity, feedback, failure behavior, and electrical safe state before selecting hardware
9. **Build Arduino + NeoTrellis node on bench** — test custom CAN messages Pi ↔ Arduino in loopback
10. **Integrate** — bring all systems together once each component is bench-tested

Before connecting any project hardware to the car, verify custom-ID collisions, K-CAN-compatible
transceivers, the termination strategy, actual vehicle bitrate, all firmware automatic-transmit
behavior, electrical isolation, and grounding. The current button-pad test firmware transmits once
per second and is bench-only.

---

## Open Questions / To Verify on the Car

- [ ] Confirm DME variant is MSD80 (affects PT-CAN message formats)
- [ ] Confirm DSC module variant (likely Bosch DSC8)
- [ ] Confirm whether Servotronic module was retained or deleted in rack swap
- [ ] Identify the steering command transport and characterize its electrical range and polarity
- [ ] Determine valve response, available feedback, electrical safe state, and watchdog requirements
- [ ] Decide the controller topology only after the actuator evidence is recorded
- [ ] Verify the vehicle-speed source and payload on F-CAN from named captures
- [ ] Identify the DSC-off command from named captures and confirm any rolling counter
- [ ] Identify exact MFL connector pinout and CAN IDs from candump session
- [ ] Confirm iDrive connector part number from ISTA wiring diagrams

---

## Reference Resources

- `python-can` docs: https://python-can.readthedocs.io
- `cantools` docs: https://cantools.readthedocs.io
- PlatformIO docs: https://docs.platformio.org
- Community E90 DBC files: search GitHub for `e90_can`, `bmw_dbc`, `opendbc`
- BMW E87/E90 forums: E90Post, Bimmerforums (search for K-CAN message IDs)
- ISTA-D: BMW dealer diagnostic tool — use for wiring diagrams and connector part numbers
