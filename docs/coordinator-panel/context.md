# Coordinator panel context

Status: approved feature definition. See [the implementation specification](spec.md) for the
approved implementation.

The coordinator panel is a small physical status display and hotspot control mounted in the
coordinator enclosure. A matching simulator card lets us experience the behaviour before building
the hardware.

## Feature list

### Physical panel

- Five individually addressable RGB lights arranged as one short strip behind a light pipe.
- One normally-open momentary button.
- An Adafruit QT Py RP2040 soldered back-to-back with an Adafruit NeoPixel Driver BFF.
- A short five-pixel WS2812B- or SK6812-compatible 5 V strip.
- No screen, menus, additional controls, or permanent internal USB connection.

The Pi powers and communicates with the panel through a detachable four-wire GPIO harness carrying
5 V, ground, transmit, and receive. USB-C is used only while flashing or servicing the QT Py, with
the Pi harness disconnected.

### Status display

The lights communicate six visible states:

| State | Appearance |
|---|---|
| Coordinator starting | Travelling white light |
| Ready, hotspot disabled | Dim white |
| Hotspot starting or waiting for a client | Pulsing cyan |
| Hotspot client connected | Solid green |
| Coordinator, panel-link, or hotspot operation fault | Solid red |
| Coordinator shut down normally or unpowered | Off |

Firmware limits every colour channel to at most 50% brightness. The animations should remain clear
without being distracting in a dark car interior.

The QT Py begins the startup animation as soon as it boots. It allows 60 seconds for the first
coordinator status and then shows red if none arrives. After communication has been established, it
shows red when status has been absent for three seconds and recovers immediately on the next valid
complete status.

The red fault indication covers only the important failures selected for this version:

- The coordinator reports a fatal condition that prevents normal operation.
- An established panel heartbeat is lost, including because the coordinator stops unexpectedly.
- Enabling or disabling the hotspot fails explicitly.

Malformed panel communication is ignored. It does not create additional visible failure modes.

### Hotspot button

The button toggles one predefined Raspberry Pi NetworkManager hotspot:

- A press while the hotspot is disabled begins activation.
- A press while it is starting cancels activation and disables it.
- A press while it is active disables it and disconnects its client.
- A press after a failed activation retries it.
- A press while the hotspot is stopping is ignored.
- A press before the coordinator is ready is ignored and is not queued for later.

The hotspot starts disabled after every boot. It is intended for one client, but the first version
does not add bespoke connection-limit enforcement. It uses a strong WPA password supplied during
Pi setup and does not share an internet connection from Ethernet.

### Simulator

- The simulator includes a visual card matching the five-light panel and button.
- It demonstrates all visible states, hotspot toggling, cancellation, and client
  connection/disconnection.
- It runs the same coordinator-side panel and hotspot services as production, replacing only UART
  and NetworkManager with in-memory adapters.
- The frontend card renders the panel service's current display state; it does not own a separate
  copy of the panel or hotspot rules.
- It models observable panel and hotspot behaviour, not UART bytes, RP2040 execution, electrical
  behaviour, or NetworkManager internals.

## Design intent

The panel and hotspot are coordinator accessories, not vehicle-control responsibilities. Their
code remains outside the coordinator kernel in separate modules connected by small, explicit
interfaces. A failure in either accessory must not change kernel state, prevent the coordinator
from becoming ready, or interrupt CAN processing.

The application surrounding the kernel knows about these modules. It projects readiness and fatal
health from the existing read-only `ControllerLoop` snapshot into the panel service. The kernel
itself does not know that the panel or hotspot exists.

The implementation is deliberately specific to this hardware and deployment. It should solve the
features above directly rather than becoming a general peripheral, networking, or module
framework.
