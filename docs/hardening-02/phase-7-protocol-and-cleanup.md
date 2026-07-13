# Phase 7 — Protocol Source of Truth and Migration Cleanup

## Goal

Remove remaining migration scaffolding and make the provisional project protocol's Python,
firmware, and documentation representations impossible to drift silently.

## Protocol source of truth

Add one machine-readable protocol definition under `protocol/`, using a standard-library-readable
format such as TOML. It owns:

- custom arbitration IDs;
- payload lengths and byte positions;
- button pressed/released values; and
- LED colour codes.

Add a small generator script that produces or validates:

- a generated Python constants module used by codecs and `CustomCanIds`;
- `devices/button-pad/include/can_ids.h`; and
- the generated constants/tables in `protocol/custom_ids.md`.

The script supports `--check`, exits non-zero on drift, and does not rewrite unrelated prose around
the generated Markdown section. Tests invoke its parsing/generation functions without shelling out;
CI invokes `--check`.

If generation is judged disproportionate during implementation, the minimum acceptable deviation is
to extend the existing drift test to parse all three artifacts, including payload lengths and byte
positions. Record that deviation explicitly; checking only IDs and colour values is insufficient.

## Cleanup audit

- Delete compatibility aliases, old controller/runtime entry points, old event unions, and temporary
  adapters left by phases 2–6.
- Remove `RateLimitedCanBus` and obsolete TX-policy field names.
- Ensure `protocol/can.py` contains wire values/codecs and capability protocols only, not application
  types or policy implementation.
- Either expose runtime network health through the diagnostic snapshot and use it in live/simulator
  status, or delete any field still written but never read.
- Update `PROJECT_CONTEXT.md`'s repository map so `features/` describes only code that exists.
- Reconcile the systemd documentation: the existing unit is bench ping-pong, not the live
  three-network runner. Do not silently change deployment behavior in this cleanup phase.

## Architecture guards

Add inexpensive tests for important import and composition constraints:

- application/domain modules do not import protocol, runtime, simulation, adapters, FastAPI,
  threading, or queue;
- protocol wire-codec modules do not import application types;
- simulation browser commands cannot construct application domain events directly; and
- default live composition exposes no transmit capability.

These may parse imports with the standard library; do not add an architecture-test dependency for a
small package.

## Documentation

Update the architecture maps and safety sections to describe:

- timestamped bounded ingress;
- immutable domain state and transitions;
- controlled effects and explicit TX capabilities;
- single-owner live and simulator kernels;
- application-level TX disable versus kernel/hardware listen-only; and
- phase 8's external prerequisites.

## Acceptance criteria

- Changing any generated/protocol constant in one artifact alone fails `--check` and tests.
- No compatibility mutation path from the pre-kernel architecture remains.
- No runtime state is written without a consumer or documented future contract.
- Import-direction guards pass.
- Repository documentation describes the code that actually exists.
- All backend and frontend checks pass.

