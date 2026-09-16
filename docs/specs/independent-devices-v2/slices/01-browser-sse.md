# Slice 01: browser SSE migration

- **Status:** Approved
- **Depends on:** [Architecture and boundaries](../architecture-and-boundaries.md) and
  [Live and device API](../live-and-device-api.md)

## Outcome

The coordinator and driving-console frontends receive live state through SSE. Commands and durable
resource operations remain HTTP. Socket.IO, Engine.IO and the separate live-contract generation
pipeline no longer exist.

This is one slice across both hosts. Splitting it by host would require a temporary dual-transport
design and postpone nearly every deletion.

## Coordinator stream

The coordinator exposes `GET /api/live` with the snapshot, projection and `resource.changed` events
defined by the live API specification. The coordinator admin frontend and the driving console both
consume it through the generated Hey API operation and validate each event with the generated Zod
schema.

The first event supplies complete current state. Later projection events replace one projection;
they are not patches. The frontend reconciles its durable query roots after the initial snapshot.

The existing application stores may change shape where SSE makes the old Socket.IO concepts
unnecessary. They must retain only current state, synchronization state and actual UI state.

## Console-host stream

The console host exposes its separate `GET /api/live` endpoint and OpenAPI document. The driving
console consumes its complete `console.snapshot` events alongside the coordinator stream. A type
from one host is not imported into the other host's contract.

## Connection behavior

Both hosts use bounded subscriber output and disconnect slow consumers. Keepalive comments,
reconnection after every termination mode and atomic initial snapshot registration follow the
approved live API specification.

The browser owns one small reconnect wrapper only if the generated Hey API client does not cover a
required termination case. There is no repository-owned generic streaming framework.

## Removed behavior and code

This slice removes:

- Socket.IO and Engine.IO servers, clients, dependencies and authorization tables;
- the Python live-event registries and both live JSON Schema files;
- the Python and JavaScript live-contract generators and their generated TypeScript mappings;
- protocol-version envelopes and resync messages made unnecessary by initial snapshots;
- trace subscribe and unsubscribe messages, the browser trace store and the trace UI;
- the driving console's connected-device view and live device-registry projection; and
- the coordinator workbench's legacy custom-CAN device cards, network topology and controls that
  depend on that projection.

The simulation CAN trace buffer remains because tests use it. The CAN device registry and ISO-TP
paths also remain because the physical button pad and Servotronic controller still use them. The
simulator's vehicle and coordinator-panel HTTP controls remain. Later slices add new independent
device simulations instead of preserving the retired custom-CAN device UI.

## Outside this slice

This slice does not add device HTTPS routes, device certificates, firmware, network presence or
admin device diagnostics.

## Acceptance

The slice is complete when:

- both frontends start from complete snapshots and update without polling;
- the driving console holds one coordinator stream and one console-host stream;
- durable resource changes invalidate the same query roots as before;
- clean EOF, HTTP failure, read failure and idle timeout all reconnect to a fresh snapshot;
- a slow client cannot block publication or grow an unbounded queue;
- generated browser events pass through generated Zod validation;
- malformed events fail visibly without replacing valid state;
- no runtime or build dependency on Socket.IO or Engine.IO remains;
- no bespoke live-contract schema or generator remains; and
- the remaining vehicle and coordinator-panel simulation controls work; and
- internal simulation and protocol tests retain their trace and custom-CAN coverage.
