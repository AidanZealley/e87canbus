# Coordinator panel bench evidence

Status: pending assembled-hardware validation.

Copy this file to an evidence note for each tested hardware revision. Record observed results,
dates, firmware version, and links to photos or captures. Do not mark Phase 2 complete from host or
native tests alone.

## Build under test

- Date:
- Tester:
- Pi model and OS release:
- Source revision (`git rev-parse HEAD`):
- Firmware record (`/var/lib/e87canbus/coordinator-panel-firmware-version`):
- QT Py/BFF/strip revisions:
- LED spacing, diffuser material, and brightness ceiling:
- Hotspot interface and NetworkManager version:

## Electrical checks before power

- [ ] QT Py/BFF labels, orientation, A3 pixel data, and free A0 button input confirmed.
- [ ] Pi TX/RX crossed to QT Py RX/TX; 3.3 V UART and common ground confirmed.
- [ ] QT Py USB-C competing-supply/back-power behavior resolved before simultaneous connection.
- [ ] Five-pixel 5 V run, ground, connector polarity, and strain relief checked.

Evidence/notes:

## Panel and UART behavior

- [ ] Immediate travelling white animation with the Pi off.
- [ ] Linux starts within the 60-second grace and converges to the commanded state.
- [ ] Boot beyond the grace turns red, then recovers when Pi state arrives.
- [ ] Established UART loss turns red after approximately two seconds and reconnect recovers.
- [ ] Duplicate button sequence and malformed/oversized input do not create an extra action.
- [ ] Graceful service shutdown sends `off` and remains dark after heartbeat loss.
- [ ] Restart and fatal controller/CAN failure show the approved startup and fault states.

Evidence/notes and measured timings:

## Hotspot behavior

- [ ] Hotspot is off after boot and has `connection.autoconnect=no`.
- [ ] Press before readiness and press during a transition are discarded.
- [ ] Ready press enables the hotspot and shows pulsing cyan.
- [ ] Laptop arrival shows green; departure returns to pulsing cyan.
- [ ] Active-state press disables the hotspot and returns to dim white.
- [ ] NetworkManager command/inspection failure shows red and leaves no optimistic active state.
- [ ] Service shutdown leaves the managed hotspot off.
- [ ] The service account can operate only the fixed helper commands and UUID.

Evidence/notes, including accepted neighbour states:

## Visual and repeated-power observations

- [ ] All six colours/states are correct at the intended viewing angle.
- [ ] Startup travel is approximately 1.4 s with 140 ms adjacent stagger.
- [ ] Cyan pulse is approximately 1.8 s with a smooth ease-in-out character.
- [ ] Brightness is suitable in a dark cabin; no flicker or supply glitch is visible.
- [ ] Light-pipe blending is sufficient to choose final spacing and enclosure geometry.
- [ ] Repeated cold boots do not activate the hotspot or retain unexpected state.

Evidence/notes:

## Acceptance decision

- Result: pending / accepted / rejected
- Required hardware, firmware, host, or enclosure changes:
- Follow-up issue/spec link:
