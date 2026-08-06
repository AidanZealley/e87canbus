# Coordinator panel context

Status: Phase 1 simulator and shared coordinator behavior implemented. Phase 2 firmware, physical
adapters, Pi deployment, and bench validation remain pending. The QT Py RP2040 and NeoPixel Driver
BFF have been purchased.

This document records the agreed physical and software design for the in-car coordinator. It keeps
the intended design separate from the currently implemented Raspberry Pi and CAN setup.

Implementation is split into two specifications:

- [Phase 1: simulator and shared behavior](phase-1-simulator.md)
- [Phase 2: physical panel and Pi integration](phase-2-hardware.md)

## Coordinator role

The primary Raspberry Pi is both the application coordinator and the logger. A separate logger Pi
is not required by the current design. Additional Pis remain useful as spare, development, capture,
or isolated experiment machines rather than mandatory permanent nodes.

The coordinator hostname is `e87-coordinator`. The target computer for the next build is a
Raspberry Pi 4 with 2 GB RAM running headless Raspberry Pi OS Lite.

The supported physical build retains all three CAN interfaces:

| Interface | Network | Bitrate | Current purpose |
|---|---|---:|---|
| `can0` | K-CAN | 100 kbit/s | Primary application and button-pad network |
| `can1` | PT-CAN | 500 kbit/s | Native powertrain capture and potentially faster readings |
| `can2` | F-CAN | 500 kbit/s | Native chassis capture and research |

Current vehicle investigation indicates that the JBBF gateways the data presently needed from
PT-CAN and F-CAN onto K-CAN. Most application functionality can therefore use K-CAN alone. Direct
PT-CAN and F-CAN access may still expose additional values such as brake pressure, provide readings
at their native cadence, and improve capture and reverse-engineering work.

This does not introduce hardware-specific profile branches. The default `bench` profile continues
to represent the complete three-network physical bench. The extra interfaces can remain idle when
an experiment needs only K-CAN.

## Enclosure

The glovebox is removed. An aluminium panel will cover the exposed fusebox and JBBF, and the
printed coordinator enclosure will bolt externally to that panel. The aluminium panel is only a
mounting surface; it does not contain the controls or act as the light diffuser.

The enclosure should:

- Keep the Pi, CAN HAT stack, front-panel controller, and internal wiring together.
- Expose all Raspberry Pi ports along one side rather than consuming a USB port internally.
- Present one accessible hotspot button.
- Include a thin translucent printed light pipe along one edge for coordinator status.
- Provide strain relief, electrical clearance from the aluminium panel, and access for servicing.

The light pipe should be spaced far enough from the LEDs to blend their individual hotspots. Its
final material, wall thickness, LED spacing, and internal reflections will be established with a
printed test piece before the enclosure geometry is fixed.

## Front-panel hardware

The front panel uses:

- One Adafruit QT Py RP2040, product 4900.
- One Adafruit NeoPixel Driver BFF, product 5645.
- Five 5 V WS2812B- or SK6812-compatible addressable RGB pixels.
- One normally-open momentary hotspot button.
- A short four-conductor locking harness between the Pi stack and the QT Py.
- A three-conductor connection from the BFF to the LED strip.
- A two-conductor connection from the QT Py to the button.

The BFF contains the 3.3 V to 5 V data-level shifter and a three-pin JST-PH LED connector. The
initial build therefore does not add a separate Pixel Shifter or loose series resistor and bulk
capacitor. Wiring will be kept short and LED brightness will be capped in firmware. If physical
testing reveals startup glitches or power-related flicker, protection or bulk capacitance should be
added as a deliberate board-mounted change rather than as loose loom components.

The QT Py and BFF may be permanently soldered back-to-back because they form one installed device.
The QT Py USB-C connection is only for initial programming or servicing and does not occupy a Pi
USB port in normal use.

### Pi to QT Py connection

The installed transport is 3.3 V UART, not USB:

| Pi connection | QT Py connection | Purpose |
|---|---|---|
| 5 V | 5 V power input | Front-panel controller and LED power |
| GND | GND | Common logic and power reference |
| BCM14 / TXD | RX | Pi commands to the panel |
| BCM15 / RXD | TX | Button events and panel status to the Pi |

BCM14 and BCM15 do not overlap the maintained CAN allocation, which uses BCM7-13, BCM16-22, and
BCM25. The UART harness must be unplugged before connecting the QT Py USB-C port for programming
unless the final power-path design has been verified to prevent competing supplies or back-power.

The BFF uses QT Py pin A3 for NeoPixel data by default. The hotspot button will use an otherwise
free GPIO such as A0 and ground, with the RP2040's internal pull-up and firmware debounce. Final pin
names and connector orientation must be confirmed against the assembled boards before making the
loom.

## Indicator behaviour

The five LEDs show one coordinator state at a time:

| State | Appearance |
|---|---|
| Coordinator software starting | White travelling animation |
| Coordinator ready, hotspot disabled | Dim white |
| Hotspot enabled, waiting for a client | Pulsing cyan |
| At least one hotspot client connected | Solid green |
| CAN or coordinator service fault | Solid red |
| Shutting down or unpowered | Off |

The RP2040 owns pixel timing and animation rendering. The Pi sends semantic states rather than
individual animation frames. Brightness should be intentionally low for an in-cabin indicator.

The RP2040 starts the white travelling animation immediately after its firmware boots, without
waiting for Linux. Once the coordinator service is ready it sends the current state over UART. A
heartbeat allows the RP2040 to show red if an established coordinator connection stops responding.
The initial boot grace period and heartbeat timeout still need to be selected and tested.

A button press before the coordinator is ready must not be queued for later execution. It may be
ignored or acknowledged locally, but it must not unexpectedly enable the hotspot after startup.

State priority is:

1. Shutdown or power loss: off.
2. Fatal coordinator or required CAN failure: red.
3. Hotspot active with a client: green.
4. Hotspot active without a client: pulsing cyan.
5. Coordinator ready: dim white.
6. Otherwise: white travelling startup animation.

A lost panel link is a special case rather than an input to this derivation. The Pi cannot command
the LEDs while the link is unavailable, so the RP2040 detects missed state refreshes and selects
red locally. The Pi separately publishes the link fault for browser diagnostics. When the link
recovers, the Pi sends the complete current semantic state and the panel converges without replaying
missed transitions.

## Hotspot button

There is one external button. It toggles a predefined NetworkManager hotspot connection:

```text
ready
  -> button press
hotspot active, waiting
  -> client associates and becomes reachable
client connected
  -> button press
hotspot disabled, ready
```

The hotspot is disabled by default and must not autoconnect. Its SSID, password, interface, fixed
address, and service-account permissions will be created during Pi setup. The first implementation
may treat any reachable hotspot client as the laptop; a MAC-specific identity rule is unnecessary
unless other clients make that ambiguous.

There is no external reset button. An exposed hard-reset control creates too much risk of accidental
SD-card corruption. Removing it does not make ignition power cycling graceful: power-loss handling
and any ignition-controlled shutdown or hold-up supply remain a separate reliability requirement.

## Firmware responsibilities

The QT Py firmware should be a small compiled C++ PlatformIO project. It owns only:

- Immediate startup animation.
- The six visual states and their animations.
- Button input and debounce.
- A small versioned UART protocol.
- Pi heartbeat monitoring and link-loss indication.
- A conservative brightness limit.

It does not own hotspot policy, CAN health interpretation, network management, or application state.
Those remain Pi responsibilities, with hotspot and panel behavior owned by a sibling local-controls
service rather than the vehicle controller kernel.

## Coordinator responsibilities

The Pi software will need:

- A UART panel adapter using `/dev/serial0`.
- A NetworkManager hotspot adapter that can only activate, inspect, and deactivate the managed
  hotspot connection.
- One state derivation that combines service readiness, expected CAN availability, hotspot status,
  client presence, and shutdown.
- An independently owned local-controls service beside the vehicle controller, connected to it only
  through a narrow starting, ready, fault, or shutting-down condition.
- Separate publication of panel-link health for diagnostics; the RP2040 owns the unreachable
  panel's physical link-loss indication.
- Publication of the derived panel state for the visual simulator and diagnostics.

The existing service account should remain unprivileged. NetworkManager permission should be as
narrow as practical, and the controller service should not be made root merely to toggle a hotspot.

## Simulator design

The simulator already runs the coordinator, so it does not need a second simulated coordinator
like the external simulated button-pad node. It needs an in-memory implementation of the local
front-panel and hotspot adapters.

The workbench should display a compact representation of the coordinator enclosure with five LEDs
and the hotspot button. Development controls should operate causes rather than assign LED colours
directly:

- Tap the hotspot button.
- Connect or disconnect a simulated laptop.
- Restart the simulated coordinator.
- Inject or recover an applicable CAN or service fault.

The same sibling service and state derivation then drive both the physical UART adapter and
simulated presentation without placing local I/O in the vehicle controller's owner loop.
The browser may render the selected animation with CSS, while the embedded animation code is tested
independently. The simulator does not need to emulate RP2040 instructions or NeoPixel wire timing.

## Phased implementation

The current setup script does not configure this panel. Work is divided at the point where the
behavior has been implemented and approved in the simulator:

1. [Phase 1](phase-1-simulator.md) defines the shared state model, implements in-memory adapters,
   publishes local-control state, and adds the coordinator enclosure to the simulator workbench.
2. [Phase 2](phase-2-hardware.md) adds the UART and NetworkManager adapters, QT Py firmware, Pi
   provisioning, and physical validation without changing the approved behavior.
