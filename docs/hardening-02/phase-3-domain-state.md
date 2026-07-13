# Phase 3 — Explicit Immutable Domain State

## Goal

Replace mutable fields that can contradict one another with frozen domain values that encode only
legal application states. Preserve all current button and snapshot behavior.

## Steering state

The current maximum-assistance implementation splits one concept across a mode, a level, a boolean,
and a private optional saved tuple. Represent it directly:

```python
@dataclass(frozen=True)
class NormalSteering:
    mode: SteeringMode
    manual_level: int

@dataclass(frozen=True)
class MaximumAssistance:
    previous: NormalSteering

SteeringState = NormalSteering | MaximumAssistance
```

- Auto mode retains the remembered manual level in `NormalSteering`.
- Entering maximum assistance wraps the complete normal state.
- Exiting restores `previous`; assistance up/down then converts it to manual without nudging on the
  first press, preserving the existing contract.
- Snapshot fields such as `maximum_assistance_active`, `steering_mode`, and
  `manual_assistance_level` are derived projections. They are not separately stored.
- Delete `_pre_maximum_assistance_state` and the assertion it requires.

## Speed state

Store the observation, not a mutable validity flag:

```python
@dataclass(frozen=True)
class SpeedSample:
    speed_kph: float
    observed_at: float
    source_network: CanNetwork
```

- Application state contains `speed_sample: SpeedSample | None`.
- Speed validity is derived from the sample timestamp, evaluation time, and configured timeout.
- `vehicle_speed_kph` and `speed_valid` remain in external snapshots for frontend compatibility but
  are projections.
- Negative decoded speed remains clamped at the domain boundary.
- No domain function reads `time.monotonic()`.

## State update style

- Make the authoritative application state a frozen dataclass.
- During this phase, `ApplicationController` may remain the public facade, but each handler replaces
  the whole state value instead of mutating fields in place.
- Keep button dispatch explicit and local. A dispatch dict or `match` over a button action is fine;
  do not introduce handler registration or a generic event bus.
- CAN health either becomes part of an explicit runtime-health value or remains runtime-owned. It
  must not be copied into the immutable domain state merely to preserve its current location.

## Characterization tests

Before changing state representation, add a table-driven characterization test covering:

- every mapped button from Auto and Manual;
- maximum assistance entered from both modes;
- mode, up, down, and maximum presses while maximum assistance is active;
- release and unknown-button no-ops;
- manual-level bounds; and
- fresh, boundary-age, stale, and never-observed speed projections.

Run the same table against the old controller before replacement and keep only the behavioral
assertions after replacement.

## Out of scope

- Pure transition/effect return values; phase 4 adds them.
- New application behavior or outputs.
- A verified speed decoder.

## Acceptance criteria

- No boolean plus nullable saved value represents maximum assistance.
- No independently mutable `speed_valid` field exists in authoritative state.
- Application state is frozen and replaced atomically.
- Existing serialized snapshot behavior is unchanged.
- All button characterization cases pass without accessing private controller fields.
- All checks pass.

