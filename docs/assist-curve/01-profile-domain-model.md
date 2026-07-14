# Phase 1: Profile domain model

## Goal

Introduce one versioned, immutable representation of a steering assistance profile. It must be
usable by configuration, persistence, the API, the simulator and a future wire encoder without any
of those concerns leaking into the domain value.

This phase does not add persistence, endpoints, UI, CAN messages or hot activation.

## Decisions to encode

### Separate definition from stored metadata

The curve calculation consumes a `SteeringCurveDefinition`. A saved profile wraps that definition
with identity and revision metadata. Suggested Python values are:

```python
class CurveInterpolation(StrEnum):
    LINEAR_V1 = "linear-v1"
    MONOTONE_CUBIC_V1 = "monotone-cubic-v1"


@dataclass(frozen=True)
class SteeringCurvePoint:
    speed_deci_kph: int
    assistance_per_mille: int


@dataclass(frozen=True)
class SteeringCurveDefinition:
    schema_version: int
    interpolation: CurveInterpolation
    points: tuple[SteeringCurvePoint, ...]


@dataclass(frozen=True)
class StoredSteeringProfile:
    profile_id: str
    name: str
    revision: int
    definition: SteeringCurveDefinition
    created_at: str
    updated_at: str
```

Exact module names may follow the package structure, but persistence and Pydantic types must map to
these domain concepts rather than replacing them.

### Deterministic units

Store and hash integer units:

- Speed: tenths of km/h (`speed_deci_kph`).
- Assistance: per-mille (`assistance_per_mille`, `0..1000`).

The API can additionally expose convenient decimal projections, but integers are authoritative.
They avoid language-specific float serialization and give a future embedded representation a
defined resolution. Calculation functions may convert them to float at their boundary.

### Fixed editing grid, explicit stored speeds

Version 1 uses a fixed number of points and the UI permits vertical movement only. Speeds should
still be included in every definition rather than inferred from array position. That makes saved
data self-describing and allows a later schema to support a different grid.

The version-1 grid is exactly eight points:

| Index | Speed (km/h) | `speed_deci_kph` |
|---:|---:|---:|
| 0 | 0 | 0 |
| 1 | 10 | 100 |
| 2 | 20 | 200 |
| 3 | 30 | 300 |
| 4 | 60 | 600 |
| 5 | 100 | 1000 |
| 6 | 160 | 1600 |
| 7 | 250 | 2500 |

Define that tuple once as a domain constant. The denser low-speed points provide useful control in
the range where assistance is most likely to change, `30` and `100 km/h` preserve the breakpoints
of the current built-in curve, and `160` and `250 km/h` retain explicit high-speed control. The
`250 km/h` endpoint defines the editor domain; it is not a verified vehicle signal or actuator
limit. Evaluation below `0` or above `250 km/h` holds the nearest endpoint value.

Changing the point count or speed tuple after profiles exist requires a new schema version or an
explicit migration. Version 1 never infers an alternate grid from the number of submitted values.

### Validation

A definition is valid only when:

- `schema_version` is supported.
- `interpolation` is supported. Phase 1 accepts only `linear-v1`; reserve the smooth value without
  accepting it until Phase 6 is complete.
- Point count exactly matches the version-1 grid.
- Speeds exactly match the version-1 grid, are non-negative and strictly increasing.
- Assistance values are integers in `0..1000`.
- All values are ordinary integers rather than booleans.

The initial product should also enforce non-increasing assistance as speed rises. If unrestricted
curves are desired, make that a conscious domain-policy change with tests; do not implement the
constraint only in the UI.

A stored profile additionally requires:

- A stable opaque ID. UUID text is sufficient.
- A trimmed, non-empty name with an explicit maximum length.
- A positive revision.
- UTC timestamps in one canonical representation.

Reject invalid input. Do not sort points, clamp assistance, or silently substitute an interpolation
version at a storage/API boundary.

## Canonical representation and fingerprint

Define canonical bytes for a curve definition and a SHA-256 fingerprint over those bytes. A
canonical JSON representation is adequate if it specifies key order, compact separators, UTF-8
encoding and integer-only numeric fields. The fingerprint is an identity check, not a security or
safety authorization mechanism.

The active projection will later use the fingerprint to answer:

- Does the browser draft equal the active definition?
- Does the active definition exactly match a saved revision?
- Does a future controller report the expected definition?

Profile name, database revision and timestamps must not be part of the definition fingerprint.

## Migration from current configuration

The existing `SteeringConfig.auto_assistance_curve` contains three float pairs. Introduce a helper
that constructs the initial built-in definition explicitly. Do not leave two independent default
curves in different modules.

The version-1 built-in definition samples the current linear curve onto the fixed grid, rounded to
the nearest per-mille:

| Speed (km/h) | Assistance per-mille | Assistance percent |
|---:|---:|---:|
| 0 | 1000 | 100.0% |
| 10 | 889 | 88.9% |
| 20 | 778 | 77.8% |
| 30 | 667 | 66.7% |
| 60 | 381 | 38.1% |
| 100 | 0 | 0.0% |
| 160 | 0 | 0.0% |
| 250 | 0 | 0.0% |

The integer quantization introduces at most half a per-mille of assistance error at a sampled
point. Tests should assert the documented integer values and use the defined calculation tolerance
when comparing the old float curve.

During this phase, the existing coordinator can continue consuming the definition through a
projection to its current float tuples. Removing the old field belongs to Phase 3.

## Tests

Add unit tests covering:

- The built-in definition is valid and stable.
- Every invalid field and boundary is rejected.
- Wrong point count and altered fixed speeds are rejected.
- Duplicate and out-of-order speeds are rejected.
- Increasing assistance is rejected if monotonic policy is enabled.
- Canonical serialization and fingerprint are stable across construction order.
- Metadata changes do not change the definition fingerprint.
- Integer values round-trip to calculation floats at the defined resolution.
- Unsupported schema and interpolation versions fail closed.

Use table-driven invalid cases so API and persistence tests can reuse the same fixtures later.

## Completion criteria

- There is one immutable domain representation and one built-in default.
- Validation is callable independently of FastAPI and SQLite.
- No persistence or frontend dependency is imported by the domain module.
- The current linear calculation can consume a valid definition without behavior drift.
- Unit and fingerprint contracts are documented in code and fully tested.
