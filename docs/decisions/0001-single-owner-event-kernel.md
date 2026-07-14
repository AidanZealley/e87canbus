# ADR 0001: Use a single-owner event kernel

- **Status:** Accepted
- **Date:** 2026-07-13

## Context

CAN frames, timers, startup, shutdown, and faults all affect control state. A frame-driven runtime
with multiple mutation entry points could reorder changes, substitute processing time for receive
time, and allow an unbounded backlog to make stale observations appear fresh.

## Decision

`CoordinatorKernel.dispatch` is the only application-state mutation path. It consumes a closed set
of timestamped inputs in order, applies pure transitions to immutable state, commits the new state
and monotonically increasing revision, and only then returns effects for the composition to execute.
Steering modes use tagged values instead of overlapping booleans and hidden saved state, so invalid
mode combinations are not representable. Execution failures return as later typed kernel inputs;
effect execution never recursively re-enters a transition.

Live composition uses one synchronous CAN reader thread per interface. Readers only receive,
timestamp at ingress, and attempt a non-blocking write to a bounded inbox. The main thread alone
dispatches inputs and executes effects. Queue delay never replaces the ingress timestamp, and
control evaluation time cannot move backwards.

## Consequences

- Application decisions are deterministic and testable with injected clocks and plain values.
- Startup, timers, reader failures, overflow, effect failures, and shutdown share one ordered path.
- Queue overflow and repeated reader failure are explicit health failures rather than hidden
  latency.
- Threading and queue primitives remain composition concerns and do not enter the application
  domain.
