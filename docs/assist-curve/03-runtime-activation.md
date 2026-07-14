# Phase 3: Runtime profile activation

## Goal

Allow a validated curve definition to replace the coordinator's active Auto curve at runtime while
preserving the single-owner event model. Activation is in-memory in this phase and may use an
unsaved definition.

This phase does not add HTTP endpoints or controller synchronization.

## Active value

Represent the active projection explicitly:

```python
@dataclass(frozen=True)
class ActiveSteeringCurve:
    definition: SteeringCurveDefinition
    fingerprint: str
    activation_revision: int
    saved_profile_id: str | None
    saved_profile_revision: int | None
```

The optional saved reference is present only when the active definition exactly matches that saved
revision. `activation_revision` is runtime-local and monotonically increases on a successful
change. It is distinct from kernel revision and saved-profile revision.

## Single-owner activation path

Add one typed kernel input carrying an already-loaded and validated activation request. All
activation requests enter the same ordered inbox/owner used for timers and other state-changing
inputs. An API task or repository callback must never replace a mutable configuration field.

The transition must:

1. Revalidate the domain value at the trust boundary.
2. Compare its fingerprint with the current active definition.
3. Commit the new immutable active value and increment revisions if it changed.
4. Publish a snapshot containing the new active projection.
5. If Auto mode has a fresh speed sample, emit a newly calculated assistance effect immediately;
   do not wait for an unrelated later timer tick.
6. Preserve Manual and temporary-maximum behavior. A curve change must not silently change mode.

Activating the identical definition is idempotent. It may update the saved-profile association if
the bytes match, but must not create a spurious actuator command or activation revision unless that
metadata is intentionally part of the public state contract.

## Move the curve out of static configuration

`SteeringConfig` may retain fixed policy such as speed timeout and manual-level count. The active
curve must move into kernel-owned runtime state (or an equivalently immutable kernel-owned value)
because it changes at runtime.

Pure transition and projection functions should accept the active definition explicitly. Avoid a
service locator, global repository or callback from the calculation function.

Startup composition performs I/O before constructing/starting the kernel:

1. Load the configured startup saved profile if one exists.
2. Validate it.
3. Otherwise select the built-in definition and report why fallback was used.
4. Construct the kernel with that initial active value.

The kernel performs no database I/O.

## Future consumer seam

Define activation in terms of a consumer result rather than assuming in-process calculation
forever. In this phase the coordinator consumer accepts synchronously. A later implementation may
enter `activating`, send the profile, and become `active` only after a controller acknowledgement.

Do not add a fake acknowledgement or CAN protocol now. Ensure only that API/frontend code will be
able to consume an activation status projection such as:

```text
active | activating | activation_failed
```

For the current coordinator consumer, successful activation can transition directly to `active`.

## Failure semantics

- Invalid requests are rejected before commit and leave the old curve active.
- Calculation/effect failure follows the existing typed output-failure path.
- Database failure is irrelevant to Apply-without-Save and cannot invalidate an already active
  in-memory definition.
- Restart restores the configured startup saved profile or built-in definition, not an unsaved
  active draft.
- Activation supplies no additional live output capability.

## Snapshot/publication changes

Expose at least:

- Definition and fingerprint.
- Activation revision and status.
- Optional matching saved profile ID/revision.
- Interpolation and schema versions.

WebSocket snapshots remain authoritative after reconnect. A browser must be able to reconstruct
active state without replaying earlier activation events.

## Tests

- Built-in definition is active on ordinary startup.
- Valid definition activation changes the next Auto calculation.
- Fresh Auto speed causes an immediate recalculated effect.
- Manual and maximum modes do not change because a curve is activated.
- Identical activation is idempotent.
- Invalid definition leaves active state and output unchanged.
- Activation is ordered deterministically relative to a speed observation and timer.
- Activation revision and kernel revision semantics are distinct and tested.
- Snapshot round-trip includes the complete authoritative active projection.
- Restart behavior distinguishes unsaved active state from startup saved state.
- Output failure during the post-activation effect follows existing fatal-health behavior.

## Completion criteria

- No mutable active curve remains inside static `SteeringConfig`.
- Exactly one ordered owner can change the active definition.
- Existing steering tests pass with the built-in profile.
- Hot activation has deterministic output and publication behavior.
- The activation boundary can later become asynchronous without changing profile storage.
