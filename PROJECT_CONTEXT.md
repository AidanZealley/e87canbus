# E87 CAN Bus Project — Context Document

> This document summarises the project goals, vehicle platform, hardware architecture, software architecture, and open questions. It is intended as a starting point for AI-assisted development (Claude Code, Windsurf, etc.) so that the full context of design decisions is available without re-explaining from scratch.

---

## Vehicle Platform

- **Car:** 2005 BMW E87 130i (5-door hatch) — UK/Euro spec, not sold in the US
- **Engine:** N52 (silver top) — DME likely **MSD80**
- **Use case:** Track only — road legality is not a concern
- **Interior:** Largely stripped. iDrive controller removed (leaving a dangling K-CAN connector). Interior fusebox exposed. Stereo and associated controls removed.
- **Steering rack:** Retrofitted E9x M3 rack with **Servotronic** (speed-sensitive hydraulic power steering via solenoid valve)

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
| F-CAN | DSC module connector in engine bay | Primary source for wheel speed |

### Wiring / Tap Method

Preferred approach in order of preference:
1. **Matching OEM connector** — find the correct male plug that mates with the iDrive female connector (likely Molex MX150 or TE Connectivity series). Use ISTA wiring diagrams for the exact part number. Zero modification to the car loom.
2. **Posi-Tap connectors** — pierce-type, reversible, no wire cutting. Use correct size for BMW loom wire gauge (typically 0.35–0.75mm²).
3. **Wago 221 lever nuts (3-port)** — cut wire, rejoin plus tap wire. Best vibration resistance of the non-connector options. Wrap in self-amalgamating tape.

Avoid scotchlocks. Avoid relying on the OBD port for permanent installation.

---

## Planned Features

### 1. Speed-Sensitive Power Steering (Servotronic Control)

**Goal:** Read vehicle/wheel speed from CAN and dynamically adjust Servotronic solenoid current — more assistance at low speed, less at high speed. Manual override mode selectable from button matrix.

**How Servotronic works:** A solenoid valve on the M3 rack bleeds hydraulic pressure. Higher current = less assistance. Normally driven by an OEM Servotronic module reading speed from CAN.

**Preferred approach — bypass OEM module, drive solenoid directly:**
- Pi reads wheel speed from F-CAN (`0x1A0` expected — verify via candump)
- Pi calculates target current from a tunable assistance curve
- Pi outputs PWM → current driver IC → solenoid

**Current driver circuit (do not use raw GPIO):**
- Solenoid is an inductive load requiring constant-current drive
- Recommended ICs: **VNH5019** or **DRV8871** (handle inductive kickback internally, accept PWM input)
- Measure solenoid resistance before choosing driver (expect 5–20Ω on M3 Servotronic solenoid)
- Add flyback diode if not built into chosen IC

**Control modes:**
- **Auto mode:** vehicle speed → lookup/curve → target current (e.g. 0 km/h = 800mA, 100 km/h = 200mA, tunable)
- **Manual mode:** fixed current level set by button presses (8 levels suggested), shown on NeoTrellis LEDs
- **Pit/override:** button hold for maximum assistance

**Alternative approach (simpler, less control):** Spoof the wheel speed CAN message to trick the OEM Servotronic module into thinking the car is going faster or slower than it is. Reversible, no hardware change, but limited precision and harder to implement manual mode.

---

### 2. DSC (Traction Control) Off — Single Button Press

**Goal:** Disable DSC/traction control with a single button press. Stock behaviour requires holding the DSC button for several seconds.

**Method:**
- Candump F-CAN or PT-CAN while performing the stock long-press DSC disable
- Identify the CAN frame that the DSC module acts on (appears after the required hold duration)
- Replay that exact frame from the Pi on button press

**Likely message ID:** Around `0x316` or `0x399` — verify on this specific car.

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
| Steering controller | Future Servotronic actuator node | K-CAN |
| Current driver IC (VNH5019 / DRV8871) | Solenoid driver | GPIO PWM from Pi |
| Servotronic solenoid | Steering assistance actuator | Driven by current driver IC |

### CAN HAT Notes

- MCP2515-based HATs are standard and well supported
- Default clock config on most MCP2515 boards is 500k — must reconfigure to 100k for K-CAN
- Three CAN interfaces are planned on the Pi; hardware selection and physical compatibility remain
  pending
- `python-can` treats them as separate named interfaces (`can0`, `can1`, and `can2`)

### Power

- Pi needs stable 5V — use an automotive-grade DC-DC converter (Pololu or DROK) with input capacitance
- Do not power Pi directly from ignition-switched line until tested — brownout during boot can corrupt SD card
- Solenoid driver powered from 12V rail with appropriate fusing

### Physical CAN Topology

```
K-CAN  (100k) ──── Pi ──── Arduino + NeoTrellis ──── Steering controller
                   │
                   └─────── Vehicle K-CAN nodes

PT-CAN (500k) ──── Pi ──── Vehicle PT-CAN nodes

F-CAN  (500k) ──── Pi ──── Vehicle F-CAN nodes

Pi GPIO (PWM) ──── Current driver IC ──── Servotronic solenoid
```

These are three independent physical networks. The coordinator does not automatically forward
frames between them; future domain-level bridging must be explicit application behavior.

---

## Software Architecture

### Monorepo Structure

```
e87canbus/
├── coordinator/                   # Central Raspberry Pi application
│   ├── src/e87canbus/           # Project-specific Python import package
│   │   ├── application/           # Authoritative state and decisions
│   │   ├── features/              # Steering, strobe, DSC, button mapping
│   │   ├── protocol/              # CAN frame encoding and decoding
│   │   ├── adapters/              # Real hardware and OS integrations
│   │   ├── simulation/            # Virtual CAN and device implementations
│   │   ├── api/                   # FastAPI and WebSocket interface
│   │   └── cli/                   # Executable entry points
│   └── tests/
├── devices/
│   ├── button-pad/                # NeoTrellis/CAN PlatformIO project
│   └── steering-controller/       # Future actuator-controller firmware
├── frontend/                      # Simulator and in-car React UI
├── protocol/                      # Cross-device CAN definitions and DBC notes
├── docs/
├── scripts/
└── deploy/
```

### Coordinator — Python Stack

- **Runtime:** Python 3.11+
- **Dependency management:** `pyproject.toml` (PEP 621)
- **Key libraries:**
  - `python-can` — CAN interface abstraction
  - `cantools` — DBC file decoding, symbolic message access
  - `RPi.GPIO` or `pigpio` — PWM output to solenoid driver
- **Concurrency model:** `asyncio` with `python-can`'s async interface (preferred over raw threads)

**Future concurrent tasks:**

```python
# Task 1 — CAN listener
# K-CAN: watch for MFL button frames → push to event queue
# PT-CAN: receive verified powertrain signals
# F-CAN: read wheel speed → update shared state

# Task 2 — Steering control loop (10–50ms tick)
# Read current speed from shared state
# Auto mode: map speed → target current via curve
# Manual mode: use fixed level from button events
# Write PWM duty cycle to GPIO

# Task 3 — Event handler
# Pop events from queue
# MFL vol+/- → adjust manual assistance level
# MFL phone pickup → trigger strobe coroutine
# MFL phone hangup → send DSC-off CAN frame
# Button matrix events → same actions + mode toggle
```

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

**Button-pad responsibilities:**
- Poll NeoTrellis for button events
- Send custom CAN message to Pi on button press/release (ID `0x700`, data byte = button index)
- Receive CAN messages from Pi to update NeoTrellis LED colours/states

### Provisional K-CAN Message Protocol (Coordinator ↔ Button Pad)

The current bench and simulation use `0x700` and `0x701` on K-CAN. They must not be treated as
collision-free merely because they are in the high standard-ID range.

| ID | Direction | Description |
|---|---|---|
| `0x700` | Button pad → coordinator | Button event (byte 0 = button index, byte 1 = press/release) |
| `0x701` | Coordinator → button pad | LED state update (byte 0 = button index, byte 1 = colour code) |

*Document full protocol in `protocol/custom_ids.md` — keep `can_ids.h` in the button-pad firmware in sync manually.*

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
6. **Connect second CAN interface to F-CAN** — verify wheel speed message at `0x1A0`
7. **Sniff F-CAN session:** drive at various speeds, hold DSC button for full duration, log DSC-off event
8. **Build solenoid driver circuit on bench** — measure solenoid resistance first, select IC, test PWM control independently
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
- [ ] Measure Servotronic solenoid resistance at connector
- [ ] Scope solenoid signal wire to confirm PWM vs analog vs CAN-commanded
- [ ] Verify wheel speed message ID on F-CAN (expect `0x1A0`)
- [ ] Verify DSC-off command ID (expect `0x316` or `0x399`) and confirm presence/absence of rolling counter
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
