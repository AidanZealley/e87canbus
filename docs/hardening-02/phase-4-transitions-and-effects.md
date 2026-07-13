# Phase 4 — Pure Transitions and Controlled Effects

## Goal

Separate deciding from doing. Application logic becomes a deterministic transition from state plus
one domain event to new state plus effects; routing, authorization, rate policy, and I/O happen only
after the state commit.

## Domain events and transitions

Define the small closed set of application events that currently exists, for example:

- `ButtonPressed(button_index)`
- `ButtonReleased(button_index)` if releases remain relevant to a future feature; otherwise discard
  releases in the decoder rather than carrying a permanent no-op event.
- `SpeedObserved(sample)`
- `ControlTimerElapsed(now)`
- `IngressFaultObserved(...)` reserved for phase 5 health behavior.

Define:

```python
@dataclass(frozen=True)
class Transition:
    state: ApplicationState
    effects: tuple[ApplicationEffect, ...]
```

The transition function accepts configuration explicitly, reads no clock, performs no logging or
I/O, and never mutates its input state. Event types that need time carry it explicitly; there is no
second implicit `now` argument whose meaning could differ from the event's observation time.

## Effects

Start with effects that correspond to verified behavior only:

```python
@dataclass(frozen=True)
class SetButtonLed:
    button_index: int
    colour: LedColour
```

Do not add `SetSteeringCurrent` until phase 8's prerequisites are met. The protocol router maps
domain effects to encoded transmit intents; the application does not select a CAN network.

## Capability-based output boundary

- Split receive and transmit protocols so an RX-only composition does not hold a writable bus in
  its effect executor.
- The executor owns `Mapping[CanNetwork, SafeCanTransmitter]`. Absence from this mapping is the TX
  denial mechanism; retain a warning if a routed effect targets an unavailable capability.
- Raw `SocketCanBus` objects are private to composition. Application/runtime code receives only the
  narrow capability it needs.
- The simulator gives the coordinator the same safe transmitter, while simulated external devices
  retain unrestricted in-memory transmitters.

## Final rate policy

Replace the temporary identical-frame limiter with an explicit per-network bounded window. All IDs
and payloads on a network share its one-second budget, so neither alternating payloads nor spreading
traffic across IDs can bypass the flood bound.

Do not add a per-ID burst allowance derived from the number of frames in a current application
transaction. Message-shape migrations belong in their own hardening pass, and actuator refreshes
will require a separate evidence-derived policy in phase 8. Use named config fields
`network_window_s` and `max_frames_per_network_window`. Implement with a plain deque and injected
time; do not add a token-bucket library. A dropped effect is logged and never queued for later
delivery.

Move this policy out of `protocol/can.py` into a small output-policy module next to the runtime or
effect executor. `protocol/can.py` returns to frame types and wire codecs only.

## Commit order

For one input:

1. Decode a domain event.
2. Calculate the transition.
3. Commit the returned state.
4. Assign a revision in phase 5.
5. Execute effects in returned order.

An effect failure does not roll state backward. It is logged now and becomes a runtime fault input in
phase 5.

## Tests

- Transition tests are pure table tests with literal state, event, expected state, and effects.
- Calling a transition twice with equal inputs produces equal outputs.
- Application modules import no CAN frame or adapter types.
- A default executor has no transmit capability.
- Explicit simulator TX sends expected LED frames.
- Alternating payloads on one ID and payloads spread across IDs share the network budget.
- The network window refills deterministically.
- Receive-only capabilities have no `send` method available to the consumer type.

## Acceptance criteria

- Application decisions perform no I/O, logging, clock reads, or in-place mutation.
- Every coordinator transmission passes through one executor and the network safety window.
- `protocol/can.py` contains no rate-policy implementation.
- The misleading `min_identical_frame_gap_s` field and old `RateLimitedCanBus` are deleted.
- All checks pass.
