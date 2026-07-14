# Phase 6: Smooth, versioned interpolation

## Goal

Add a smooth interpolation algorithm whose numerical output is consistent in Python, TypeScript
and future embedded firmware. Upgrade profiles explicitly; do not merely smooth the chart path.

## Algorithm contract

Use a monotone piecewise cubic Hermite interpolation with a fully specified tangent algorithm,
published as `monotone-cubic-v1`. A suitable definition is the Steffen monotone method used by
D3's monotone curve implementation because it passes through control points and avoids introducing
spurious extrema between them.

The implementation contract must specify:

- Integer input-unit conversion.
- Tangent calculation at interior points and endpoints.
- Behavior below the first and above the last speed.
- Floating-point precision and acceptable conformance tolerance.
- Output clamping to the valid assistance range as a final defensive check.
- Behavior at exact control-point speeds.

Do not describe the contract only as "use Recharts monotone". Recharts is a renderer and cannot be
the firmware or Python specification.

## Authoritative implementations

Phase 6 initially requires:

1. A pure Python evaluator used by coordinator simulation.
2. A pure TypeScript evaluator used for immediate draft preview.
3. Shared language-neutral golden vectors covering all control points and representative points
   between them.

Future firmware implements the same version against the vectors. Keep the algorithm selected by
the profile's interpolation discriminator; do not overwrite the linear function globally.

## Rendering strategy

To ensure the graph represents evaluated values:

1. Evaluate the draft definition at a dense, deterministic sequence of speeds.
2. Plot those samples with a linear SVG path.
3. Render the original control points separately as draggable handles.

This avoids depending on whether Recharts/D3 changes its internal curve implementation and makes
the displayed path use the same TypeScript function as numeric preview. Choose a sample interval
small enough for the display but bounded enough to keep dragging responsive; calculate it once per
draft change, not per animation frame.

The active marker continues to use backend-reported active output when available.

## Profile migration

Existing `linear-v1` profiles retain their behavior forever. Offer an explicit conversion action
that creates a new saved revision or a new profile with `monotone-cubic-v1`. The same points can
produce different intermediate assistance, so activation must be a conscious action.

Unknown interpolation values fail closed in every layer. A future controller that supports only
`linear-v1` must reject a smooth profile with an explicit supported-version response rather than
approximating it silently.

## Shape and policy checks

For every valid non-increasing profile, test that:

- Output remains within `0..1`.
- Output is non-increasing over a dense sampled range.
- Every control point is reproduced exactly within the defined tolerance.
- No interior overshoot or new extremum appears.
- Endpoint extrapolation uses the endpoint value.
- Small or large adjacent speed spans remain finite.

The fixed, strictly increasing speed grid removes zero-width segments. Keep defensive rejection in
the evaluator rather than relying solely on construction-time validation.

## Conformance vectors

Store test vectors in a neutral repository artifact containing:

- Algorithm/schema version.
- Integer control points.
- Evaluation speeds in deterministic integer or rational units.
- Expected assistance at adequate precision.
- Tolerance rules.

Both Python and TypeScript tests must load the same artifact. Generate expected values with one
reviewed reference implementation, then check the artifact into source control; do not regenerate
expected values inside the test under test.

Add cases for flat profiles, one steep transition, repeated assistance values, the built-in curve,
boundaries, and the smallest allowed assistance increment.

## Rollout

1. Land the versioned evaluator and conformance vectors while all active profiles remain linear.
2. Add API acceptance for `monotone-cubic-v1`.
3. Add editor preview and an explicit conversion choice.
4. Activate only in simulator and compare graph, backend calculation and telemetry.
5. Make smooth interpolation available to ordinary saved profiles after cross-language tests pass.

Physical use remains blocked on the existing hardware evidence requirements.

## Completion criteria

- `linear-v1` behavior and saved profiles are unchanged.
- Python and TypeScript pass the same checked-in conformance vectors.
- The editor plots evaluated samples rather than cosmetic smoothing.
- Smooth profiles cannot be activated by a consumer that does not advertise/support their
  interpolation version.
- Bounds, monotonicity, endpoints and absence of overshoot are exhaustively tested.
