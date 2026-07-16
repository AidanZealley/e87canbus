# ADR 0007: Let the Servotronic controller own speed-to-assistance mapping

- **Status:** Proposed
- **Date:** 2026-07-14

## Context

The current hardware-independent implementation decodes speed and maps it through a fixed curve in
the coordinator. Its actuator boundary receives an already-selected dimensionless assistance
value. This is useful for simulation but makes continuous Auto behavior dependent on the
coordinator process and its connection to a future Servotronic controller.

The intended physical controller will already own time-critical PWM/current regulation, hardware
limits, command freshness, telemetry and electrical fallback behavior. Keeping the speed mapping
beside that loop could allow Auto assistance to continue when the display or coordinator is
unavailable. The computational saving is negligible; the architectural benefit is local ownership
of the complete real-time decision.

This direction depends on facts not yet established: the verified vehicle-speed source and decode,
whether the controller can safely attach to that network, the Servotronic electrical interface,
the physical safe state, watchdog timing, controller hardware and an authorized profile transport.

## Decision

Propose that the future Servotronic controller own the real-time mapping from directly observed,
validated vehicle speed to assistance and own application of that target to its local actuator
loop.

The coordinator and frontend will own profile authoring and durable named-profile storage. On
explicit activation, the coordinator will transfer a complete versioned profile to the steering
controller. The controller will receive into staging state, validate the schema, interpolation,
point grid, bounds, revision and integrity value, persist it as a last-known-good configuration,
activate it atomically, and acknowledge its active revision/fingerprint.

The full profile is configuration, not a renewable lease. It is sent on explicit activation and
reconciled after startup or reconnect when reported revisions differ. Periodic status may advertise
the active revision/fingerprint, speed freshness, target, measured output and faults; it will not
rewrite the profile at a fixed interval.

The controller must receive vehicle speed without depending on coordinator forwarding for this
independence claim to hold. It will own stale/malformed-speed detection and a hardware-evidence-
backed fallback. Persistence of normal mode, Manual state and temporary maximum-assistance intent
will be decided separately; temporary or calibration overrides must not become persistent merely
because profiles are persistent.

Until this ADR is accepted and its evidence gates are satisfied, the coordinator remains the
implemented assistance-curve evaluator and no physical profile protocol or output behavior is
authorized.

## Consequences

- Auto mapping can operate without the frontend or coordinator once a valid profile is installed
  and a valid direct speed source is present.
- The controller becomes the authoritative physical interpolation implementation and must report
  enough telemetry for supervision.
- Python, TypeScript and controller firmware require a versioned algorithm contract and shared
  conformance vectors so previews and simulation match physical calculation.
- Profile transfer needs staging, integrity checking, acknowledgement, version reconciliation and
  interruption-safe non-volatile storage. A previous valid profile must survive a failed update.
- Profile updates do not need periodic full retransmission, reducing CAN traffic and flash wear.
- The controller's direct connection to a vehicle speed network expands its hardware and protocol
  responsibilities and must be justified by captures and topology evidence.
- The coordinator's current `SetSteeringAssistance` actuator contract will eventually be replaced
  or narrowed by a profile/configuration, mode-intent and telemetry protocol.
- SQLite on the coordinator remains the source for the profile catalog; controller storage is a
  deployed cache of the active last-known-good definition, not a second editable catalog.

## Conditions for acceptance

- A named capture verifies the speed arbitration ID, source network, payload decode, cadence,
  counters/checksums, malformed behavior and loss behavior on this vehicle.
- The selected controller hardware can observe that network without unsafe gatewaying or loading.
- The actuator, current direction/range, feedback, electrical safe state and watchdog behavior are
  characterized.
- Profile encoding, transport IDs, collision checks, sequencing, integrity, acknowledgement and
  update-interruption behavior are specified and tested.
- Boot behavior with valid, missing, corrupt and unsupported stored profiles is defined.
- Loss behavior for speed, coordinator, CAN, controller reset and partial profile transfer is
  tested in simulation and then on bounded hardware.
- The resulting implementation remains consistent with the evidence gate in ADR 0006.
