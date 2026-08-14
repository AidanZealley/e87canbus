# ADR 0012: K-CAN cockpit display with coordinator-owned configuration

- **Status:** Proposed
- **Date:** 2026-08-12

## Context

A future embedded cockpit display should start quickly and fit in front of the existing KOMBI
without requiring another Raspberry Pi or another Ethernet connection. The original KOMBI remains
installed and usable: the new display mounts on a quick release in front of it, so it can be
removed for factory warnings, diagnostics and service resets.

The KOMBI is a K-CAN node. The JBBF gateways the selected powertrain information required by the
KOMBI from PT-CAN onto K-CAN. A cockpit connected to K-CAN can therefore observe verified live
signals such as engine speed and road speed without asking the coordinator to duplicate them.

The coordinator nevertheless owns project configuration such as shift-warning and displayed RPM
limits. The cockpit needs that configuration promptly at startup and must recover when either
device restarts or configuration changes.

## Decision

Build the cockpit around an ESP32-P4 and LVGL. The final display size, resolution and interface
remain open pending an in-car visibility and mounting trial. Touch is not required, although a
display that includes it is acceptable. Software-controlled backlight brightness is required.

Connect the cockpit to K-CAN through a suitable external CAN transceiver. It directly decodes live
vehicle values from capture-backed K-CAN definitions. It does not require Ethernet and the
coordinator does not republish live values already present on K-CAN merely for the cockpit.

The coordinator remains authoritative for semantic cockpit configuration. The cockpit combines
that configuration with live K-CAN values to produce presentation-only behavior such as warnings,
colour changes and RPM-limit effects. Layout, colours and animations remain cockpit firmware
concerns; the coordinator does not send a remote UI description. Cockpit calculations do not own
or imply vehicle-control behavior.

Use the existing device-registry pattern for the cockpit: the same generated HELLO, WELCOME and
HEARTBEAT layouts and the same device-session, controller-session and lease semantics. Add a
distinct cockpit role and distinct provisional CAN IDs rather than sharing another device's IDs.
The cockpit's configuration transfer similarly uses the existing bounded ISO-TP implementation on
its own request/response IDs.

Configuration synchronization is hybrid:

1. On boot, the cockpit validates and immediately applies its last complete configuration snapshot
   from local non-volatile storage. If none is valid, it uses explicit conservative defaults and
   indicates that configuration is not yet synchronized.
2. It immediately enters the normal registry HELLO/WELCOME flow.
3. After WELCOME, it requests a complete configuration snapshot over ISO-TP. It also requests one
   whenever the coordinator session or advertised configuration revision changes.
4. It validates the version, length and integrity of the complete response, applies it atomically,
   then persists it. A partial or invalid response never replaces the active snapshot.

Cached configuration provides immediate last-known-correct startup, but cannot prove that no
configuration changed while the cockpit was off. The cockpit distinguishes cached from confirmed
configuration internally and becomes confirmed after synchronization with the current coordinator
session. The exact on-screen treatment of that brief state remains a UI decision.

All project CAN IDs remain provisional until checked against representative captures from this
vehicle. Native K-CAN signal definitions likewise require named capture evidence before they are
treated as executable definitions.

Use Deutsch DT-family connectors consistently with the other project devices. The enclosure keeps
the ESP32-P4 USB service port accessible from the side. The quick-release mounting and final pin
allocation remain open pending the physical mock-up.

For the initial build, power the ESP32-P4 board from the voltage its selected development board
actually accepts, normally regulated 5 V at USB/VBUS, rather than applying vehicle voltage to an
ESP pin. A fused switched vehicle circuit provides over-current protection but does not itself
provide voltage regulation or automotive transient protection. An initial installation therefore
still needs an appropriate 12 V-to-5 V supply module between the fusebox and the ESP board. A later
reusable automotive input module may incorporate reverse-polarity, cranking and transient
protection after its requirements are established. The variable-voltage input of a separate CAN
HAT must not be assumed to protect or power the ESP board unless the selected hardware explicitly
provides a suitable regulated output.

## Consequences

- The cockpit can show live data independently of the coordinator, while project-specific display
  behavior follows coordinator configuration.
- Normal live signals add no duplicate coordinator traffic to 100 kbit/s K-CAN.
- Startup rendering does not wait for the coordinator, while session-aware synchronization repairs
  stale cached configuration promptly.
- The cockpit becomes another registered device and requires generated protocol additions,
  collision-validated IDs and coordinator integration before in-car transmission is enabled.
- Retaining the KOMBI avoids making the first cockpit version responsible for every factory
  warning, diagnostic and service function.
- Display selection, mechanical geometry, connector pinout, native signal catalogue, brightness
  source, power-module design and detailed fault presentation remain deferred.
