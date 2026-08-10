# Minimal coordinator panel specification

Status: approved for implementation.

## Outcome

Add two small coordinator-side modules, QT Py RP2040 firmware, and the required Pi setup:

- `panel` derives the six-state display, sends it to an output, and receives button presses.
- `hotspot` owns toggle behaviour around a small networking backend.
- Production supplies UART and NetworkManager adapters.
- Simulation runs the same services with in-memory adapters and renders their state in the existing
  panel card.

Implement the smallest complete solution in this document. This is one fixed accessory, not a
reusable peripheral system. Do not add infrastructure or failure handling for possible future
requirements.

## Architecture

```text
                              application composition
                                        |
ControllerLoop -- read-only snapshot --> panel service -- display --> panel output
                                        |                             UART or memory
                                      toggle
                                        v
                                  hotspot service --> hotspot backend
                                                      NetworkManager or memory
```

The panel and hotspot live beside the coordinator kernel. The kernel remains unchanged and unaware
of both. Accessory failures must not change coordinator readiness, enter the kernel, or block CAN
processing.

Application composition projects the existing `ControllerLoop` snapshot to `starting`, `ready`, or
`fault`, and supplies `off` during graceful shutdown. This is a read-only application seam, not a
new kernel input, effect, commit, or topic.

The panel needs only this read-only coordinator state:

```python
CoordinatorStatus = Literal["starting", "ready", "fault", "off"]
```

The panel service owns display-state derivation and button gating. It exposes its current semantic
display state for publication and sends the same value to its configured output. Physical UART
`BUTTON` and the simulator button endpoint both call the same panel-service operation.

The hotspot service exposes the equivalent of two direct typed operations:

```python
def toggle() -> None: ...
def status() -> HotspotStatus: ...
```

It owns the toggle decision so the panel never decides from stale state. Its hardware seam is the
equivalent of:

```python
class HotspotBackend(Protocol):
    def activate(self) -> None: ...
    def deactivate(self) -> None: ...
    def observe(self) -> HotspotObservation: ...
```

Production implements this with NetworkManager; simulation implements it in memory. These direct
interfaces exist because there are two real environments. Do not turn them into a general
ports-and-adapters framework, plugin system, dependency container, or module lifecycle.

## Behaviour

The hotspot state machine is:

| Current state | Button press |
|---|---|
| Disabled | Begin activation |
| Starting | Cancel activation and disable |
| Waiting for client | Disable and disconnect the client |
| Client connected | Disable and disconnect the client |
| Failed | Retry activation |
| Stopping | Ignore |

A press before the coordinator is ready is ignored rather than retained. Hotspot operations are
serialized, and cancelling activation must not allow an earlier request to leave it active later.

The shared Python panel service derives one of the six visible states using this priority:

1. Coordinator off: lights off.
2. Coordinator fault or hotspot failed: solid red.
3. Coordinator starting: travelling white.
4. Hotspot client connected: solid green.
5. Hotspot starting or waiting: pulsing cyan.
6. Otherwise: dim white.

No separate stopping animation is needed.

## UART

Production uses `/dev/ttyAMA3` at 115,200 baud over 3.3 V UART. The panel service sends its final
semantic display state using a fixed newline-delimited ASCII protocol:

```text
Pi -> QT Py: STATUS <display>\n
QT Py -> Pi: BUTTON\n
```

The allowed display values are:

```text
starting ready hotspot_waiting hotspot_connected fault off
```

The Pi sends the complete display state on opening UART and once per second afterwards. This is
also the heartbeat. The QT Py sends one `BUTTON` line per debounced press. Both sides use a small
bounded line buffer and ignore malformed or oversized lines.

There are no acknowledgements, checksums, sequence numbers, retries, deltas, negotiation,
discovery, or protocol versions. The next complete status provides recovery.

## Firmware and wiring

Add a PlatformIO project at `devices/coordinator-panel/` for the Adafruit QT Py RP2040. Firmware
owns exactly five pixels, rendering the received semantic state, button debounce, UART parsing, and
heartbeat timing. It does not derive coordinator or hotspot behaviour. Every RGB channel has a
hard 50% maximum.

The QT Py starts the white travelling animation immediately. It shows red if the first valid status
does not arrive within 60 seconds, or if an established status is absent for three seconds. The
next valid status recovers immediately. After a valid `off`, the lights remain off without further
heartbeats so a graceful Pi shutdown does not become a false fault.

Connections are:

| Function | Connection |
|---|---|
| UART | Pi BCM4/TXD3 to QT Py RX; Pi BCM5/RXD3 to QT Py TX |
| Button | QT Py A0 to ground, using its internal pull-up |
| NeoPixel data | QT Py A3 through the BFF level shifter |
| Power | Pi regulated 5 V and ground to QT Py/BFF |

Use this detachable power path:

```text
Pi 5 V -- 500 mA fuse -- 1 A Schottky diode -- QT Py/BFF 5 V
```

The diode may be a 1N5817 or 1N5819, with its anode toward the Pi and striped cathode toward the QT
Py. Never connect vehicle 12 V or put 5 V on a UART signal. Disconnect the complete Pi harness
before attaching QT Py USB-C.

Do not add further power switching, capacitors, data protection, or live USB isolation unless the
assembled hardware demonstrates a problem.

## Hotspot and Pi setup

`scripts/setup_pi.sh` provisions one NetworkManager connection named `e87canbus-hotspot` for the
physical `car` and `bench` profiles. It uses the Pi's built-in Wi-Fi, does not autoconnect, does not
route internet from Ethernet, assigns the coordinator `10.42.0.1`, and starts disabled. Avahi
publishes `e87.local`, and a systemd socket bound only to the hotspot address proxies port 80 to the
loopback controller. Runtime may inspect, activate, and deactivate this connection but may not
create or edit connections.

The hotspot is intended for one client. Do not add custom maximum-client enforcement, client
identity, MAC filtering, remembered clients, or a general Wi-Fi API. Use the simplest available
system observation to distinguish no associated client from at least one.

Setup must also:

- Enable UART3 as `/dev/ttyAMA3`; leave the Linux serial console disabled on the primary UART.
- Give the existing `e87canbus` account UART access.
- Install the minimal serial, NetworkManager, and client-observation dependencies.
- Give the unprivileged service account the practical permission needed to operate the fixed
  connection while preserving unrelated connections.
- Be safe to rerun.

Use ordinary system permissions such as a small Polkit rule. Do not add a privileged daemon or
general command-execution abstraction. Only add a fixed argument-validating helper if target Pi
evidence shows the direct permission approach cannot work.

On first provisioning, setup asks for the WPA password twice using a silent prompt and validates
NetworkManager's accepted length without printing it. For unattended setup it accepts
`--hotspot-password-file <path>`. Rerunning setup without a password preserves an existing one.
The secret is not placed in the repository, command line, or coordinator environment.

The simulator profile neither requests a password nor changes host UART or networking.

Hotspot commands do not retry automatically. A command failure becomes `failed` and is logged. A
later button press is the retry. A successful later observation clears the failure.

## Firmware upload

Add `scripts/coordinator_panel_upload.sh` following the existing button-pad upload workflow:

```bash
./scripts/coordinator_panel_upload.sh
UPLOAD_PORT=/dev/ttyACM0 ./scripts/coordinator_panel_upload.sh
```

Document that the first flash or firmware recovery may require manually entering the RP2040 USB
bootloader. USB is not the installed transport.

## Simulator

Retain the existing reusable `CoordinatorPanel` frontend component. The simulated application runs
the same panel and hotspot services used by production with an in-memory hotspot backend and panel
output. It publishes the panel service's current display state to the frontend. The card is a pure
renderer, and its current component-local behaviour state should be removed.

The simulator button endpoint calls the same panel-service button operation used by physical UART.
Client connect/disconnect and failure controls change only the in-memory hotspot backend; the
shared hotspot and panel services derive every resulting transition and display state.

The simulator must demonstrate:

- Coordinator starting, ready, fault, and off.
- Hotspot enable, cancellation by a second press, and disable.
- Client connect and disconnect.
- Hotspot failure and retry.

Do not duplicate the state machine in the simulator or frontend. Do not execute `nmcli`, open
serial ports, emulate UART bytes or RP2040 instructions, or build a simulated networking subsystem.

The browser simulator validates the shipped coordinator-side behaviour, not firmware execution.
Firmware rendering and link-loss logic use host-native tests and a physical bench check.

## Explicit failure handling

This is the complete failure list for this version:

| Failure | Behaviour |
|---|---|
| Coordinator fatal | Report coordinator `fault`; show red |
| No first status for 60 seconds | Firmware shows red |
| Established status absent for three seconds | Firmware shows red until valid status returns |
| Hotspot activation or deactivation fails | Hotspot becomes `failed`; show red |
| Pi provisioning fails | Setup exits unsuccessfully with a useful message |
| UART line is malformed or too long | Ignore it |

Do not add backoff, automatic recovery, persistence, degraded modes, extra visible failures, or a
serial reconnection state machine.

## Verification

Use focused tests for:

- Shared coordinator/hotspot state to semantic display selection.
- Hotspot state plus button press to action.
- UART encoding, parsing, heartbeat timeout, and debounce.
- NetworkManager command and observed-state mapping.
- One composed button-to-hotspot-to-display path using the shared services.
- Simulator controls publishing the shared display state to the frontend renderer.

Use fakes at UART and NetworkManager boundaries. Do not test every state permutation, malformed
input, retry, timing, or concurrency path. Physical brightness, UART, hotspot client observation,
and cancellation need one short bench check after implementation.

## Acceptance criteria

- The simulator demonstrates all agreed appearances and hotspot behaviour.
- Production and simulation use the same panel service, hotspot service, and display derivation.
- The frontend contains no separate hotspot or panel transition rules.
- The kernel has no panel or hotspot changes.
- The physical panel receives status each second and reports debounced presses.
- Firmware enforces the heartbeat timings and 50% brightness ceiling.
- The predefined hotspot starts disabled, toggles from the button, and disconnects its client when
  disabled.
- Accessory failures do not affect coordinator readiness or CAN processing.
- The setup script provisions a fresh Pi without exposing the password.
- QT Py firmware builds and uploads through the documented PlatformIO workflow.

## Non-goals

- A general local-controls service or module framework.
- Support for other panels, microcontrollers, pixel layouts, or runtime LED configuration.
- Runtime hotspot configuration, internet sharing, automatic activation, or persisted state.
- Remote firmware updates or live USB while the Pi harness is connected.
- Ignition shutdown, Pi power-loss protection, enclosure CAD, or light-pipe validation.
- Comprehensive integration or fault-injection testing.
