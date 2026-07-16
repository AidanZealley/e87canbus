# Phase 2 — Kernel registry and gating

[Overview](README.md) · [Implementation log](implementation-log.md) ·
[Agent prompt](phase-agent-prompt.md) ·
[Previous phase](phase-1-specification-and-protocol.md) ·
[Next phase](phase-3-live-contract-and-car-ui.md)

## 1. Objective

Make the single-owner controller kernel the canonical registry owner, execute
the symmetric handshake through normal CAN effects, and enforce every
device-dependent boundary on the server.

## 2. Dependencies and starting state

- Phase 1 must be completed and recorded in the implementation log.
- Generated registry IDs/codecs and catalogue types are authoritative.
- The kernel already owns application state, timing inputs, commits, and
  ordered effects.
- Live and simulated runtimes already route effects through
  `EffectExecutor`/`SafeCanTransmitter`.

## 3. In scope

- Immutable runtime registry entries and transition logic.
- Controller boot/session generation.
- HELLO/ACK/heartbeat/fault/reboot/incompatibility/timeout processing.
- Registry effects through the existing output policy.
- Input, output, command, and activation gating.
- Output synchronization when a role becomes active.
- Maximum-assistance clearing on Servotronic loss.
- Origin-aware effect failures and temporary red button feedback.
- Nonfatal optional-device health behavior.
- Publication topics only on meaningful changes.

## 4. Explicitly out of scope

- Final Socket.IO and frontend model migration.
- `/dev` lifecycle endpoints or device cards.
- Physical firmware.
- Capability negotiation or duplicate quarantine.
- Physical Servotronic CAN commands.

## 5. Required implementation changes

1. Add immutable registry state for both catalogue roles to
   `CoordinatorKernel`; it is not part of durable application state.
2. Generate one nonzero 16-bit controller session per kernel boot and retain it
   for that kernel lifetime.
3. Let protocol routing return typed registry observations as well as
   application events.
4. On compatible configured `HELLO`, install the new device session as
   `pending` and emit `WELCOME_ACK` when K-CAN TX is available.
5. On a first matching heartbeat, transition to `active` or `fault`; on later
   heartbeats refresh the lease and acknowledge without publishing unless a
   public field changes.
6. Evaluate ordinary and incompatible timeouts from `TimerElapsed` using the
   injected monotonic time.
7. Add a typed raw/routed CAN controller effect for acknowledgements and
   execute it through `SafeCanTransmitter`.
8. Gate button input and LED output on active `button_pad`.
9. Gate mode, manual level, maximum assistance, and curve/profile activation on
   usable Servotronic: active registry plus a healthy output adapter.
10. Clear maximum assistance whenever Servotronic leaves active. Retain normal
    mode, level, and active curve, but reject changes until recovery.
11. On activation, send the complete current button LED state or current normal
    Servotronic output exactly once as applicable.
12. Introduce an effect-request wrapper with an optional originating button
    index. Preserve that origin through synchronous executor failures.
13. Add independent per-button red-feedback deadlines to application state.
14. Recompute and emit canonical `buttons.led_colours` on feedback start and
    expiry. Feedback LED-send failures carry no origin and cannot recurse.
15. Make optional registry, device-status, and Servotronic adapter failures
    nonfatal. Preserve existing documented fatal controller/network failures.

## 6. Public interfaces and types

Kernel-visible values must include equivalents of:

```text
RegistryHelloObserved
RegistryHeartbeatObserved
DeviceRegistryEntry
SendRegistryFrame
EffectRequest(effect, origin_button_index | null)
ButtonCommandFailed(button_index, occurred_at)
ButtonFeedbackDeadlineReached(now)
```

The registry entry contains public diagnostics plus private lease/sequence
tracking. Private fields must not leak into the later live contract.

Unavailable HTTP work raises a dedicated domain/service exception that phase 3
maps to:

```json
{
  "error": {
    "code": "feature_unavailable",
    "message": "<specific dependency and status>"
  }
}
```

Profile repository CRUD bypasses this availability check. Activation does not.

## 7. Expected files/modules affected

- `coordinator/src/e87canbus/runtime.py`
- `coordinator/src/e87canbus/application/state.py`
- `coordinator/src/e87canbus/application/events.py`
- `coordinator/src/e87canbus/application/controller.py`
- registry-domain/controller module introduced in phase 1
- `coordinator/src/e87canbus/protocol/router.py`
- `coordinator/src/e87canbus/output.py`
- `coordinator/src/e87canbus/service.py`
- `coordinator/src/e87canbus/live.py`
- `coordinator/src/e87canbus/simulation/runtime.py`
- operational command/activation use cases
- runtime, controller, command-gateway, live, reliability, and output tests

## 8. Detailed implementation sequence

1. Implement a pure registry transition function with fake-clock unit tests.
2. Add registry state/session to the kernel and route decoded observations.
3. Add acknowledgement effects and executor support.
4. Integrate lease expiry into the existing timer path.
5. Add changed-topic calculation based on public registry equality, not lease
   timestamp changes.
6. Add feature-availability selectors and gate decoded inputs, effects, and
   submitted commands at the owner boundary.
7. Add activation synchronization and maximum clearing.
8. Add origin-aware effects and immediate steering effects for button actions
   whose synchronous result must be attributable.
9. Add feedback overlays/deadlines and extend `next_deadline` scheduling to the
   earliest application deadline.
10. Update live/simulated executor failure feedback without retry loops.
11. Add integration and reliability tests before exposing the new projection.

## 9. Edge cases and failure behavior

- Repeated `HELLO` for the same pending session may be acknowledged without a
  lifecycle publication.
- Latest compatible `HELLO` replaces an existing session and moves to pending.
- Frames for a displaced device or controller session are ignored.
- An unsupported configured identity becomes incompatible even when live TX is
  unavailable; absence of TX is configuration, not a send failure.
- A real attempted CAN send raising an error retains existing controller-health
  behavior. A missing TX capability silently leaves registration pending.
- Fault heartbeats remain contact and receive acknowledgements.
- Button frames received before active registration are ignored, not queued.
- Effects suppressed while unavailable are not replayed. Only the explicit
  activation synchronization emits current state.
- A button feedback failure must never generate another feedback request.
- Ordinary idempotent/unassigned button presses do not flash red.

## 10. Required tests and verification commands

Test at minimum:

- not-found, pending, active, stale, incompatible, fault, and disabled states;
- registration, repeated registration, reboot, controller restart, and timeout;
- healthy/fault recovery and opaque status retention;
- unknown/malformed/wrong-session/out-of-order frame rejection;
- duplicate sequence re-acknowledgement without state publication;
- live no-TX pending behavior;
- no devices-topic change for ordinary heartbeat traffic;
- legacy button input ignored before registration;
- LED and steering effects gated and synchronized after activation;
- every operational HTTP command and activation unavailable path;
- profile CRUD independence;
- maximum assistance clearing and retained normal state;
- optional faults not changing global readiness;
- 500 ms independent feedback, expiry, extension, and recursion prevention.

Run focused suites followed by the full coordinator suite:

```text
uv run pytest coordinator/tests/test_can_protocol.py coordinator/tests/test_runtime.py coordinator/tests/test_application_controller.py coordinator/tests/test_command_gateway.py coordinator/tests/test_output.py coordinator/tests/test_live.py coordinator/tests/test_reliability.py
uv run pytest coordinator/tests
```

## 11. Exit criteria

- The kernel is the sole registry owner in live and simulated composition.
- Every acknowledgement uses the normal effect/TX policy path.
- All server-side gates are enforced regardless of frontend state.
- Heartbeats renew leases without externally meaningful update storms.
- Optional-device loss and faults remain nonfatal.
- Button rejection/failure feedback is canonical, bounded, and independently
  timed.
- Required coordinator tests pass.

## 12. Required implementation-log update

Update the phase 2 status row and append a detailed entry to
[the implementation log](implementation-log.md). Include state-machine choices,
availability exceptions/messages, effect-model changes, timing tests, health
behavior, and all verification results. Record any public projection work left
for phase 3.

## 13. Handoff notes for phase 3

Phase 3 projects the registry; it must not move registry ownership into API or
frontend code. Public equality should omit private heartbeat/sequence fields,
and frontend status must derive from the server projection rather than infer
connection from CAN traffic.
