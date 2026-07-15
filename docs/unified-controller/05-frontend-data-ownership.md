# Phase 5: Frontend live and durable data ownership

## Goal

Move the frontend to one Socket.IO-to-Zustand live-state path and one TanStack Query HTTP path.
Remove component-owned socket listeners, live snapshots in the Query cache, direct component fetches
and broad loading/invalidation behavior. Preserve the current routed `/dev` and `/car` experiences.

This phase addresses the architectural cause of the observed long-running development crash; it
must not work around React development instrumentation or require a changed developer environment.

## Preconditions

- Phase 4 Socket.IO event contracts and reconnect snapshot are `Verified`.
- Phase 3 command/resource functions are available.
- Existing `CarDataProvider`, simulator connection/cache modules and component query consumers have
  been mapped before edits.
- `frontend/AGENTS.md` is followed for every changed frontend file.

## Dependencies

- Add `socket.io-client` as a frontend runtime dependency.
- Continue using the installed Zustand and TanStack Query versions.
- Do not add Redux, RxJS, a normalized cache or another socket wrapper framework.

## One socket owner

Create one transport module outside React that:

- Constructs exactly one Socket.IO client per browser application.
- Owns connect, disconnect, reconnect and protocol-version behavior.
- Registers one listener per fixed server event.
- Applies complete snapshots and topic projections to the live store.
- Clears/replaces state when `boot_id` changes.
- Rejects older/duplicate per-topic revisions.
- Exposes trace subscribe/unsubscribe without exposing the raw socket to components.
- Removes every listener and connection reference during explicit teardown/tests.

React providers may start/stop the singleton for application lifecycle and expose hooks, but they do
not register message listeners or copy socket data into component state.

## Zustand live store

Use one small store for current live state:

```text
connection
boot_id
topic revisions
vehicle
engine
steering
buttons
devices
controller health
```

Requirements:

- Applying `controller.snapshot` atomically replaces every live slice.
- Topic actions replace one complete slice only when its revision is newer.
- State contains current values, not an event log.
- No derived display strings or settings-owned units are stored.
- No server resource such as a settings/profile document is stored.
- No whole-store object is reconstructed when one unchanged topic is received.
- Store actions can be tested without rendering React.

Keep diagnostic trace in a separate fixed-capacity store. Closing the trace UI unsubscribes and may
clear its buffer. The maximum row count is part of the store contract and tests.

## Component subscription policy

Components use the narrowest stable selector that expresses their needs:

```tsx
const speedKph = useLiveStore((state) => state.vehicle.speedKph)
const maximumActive = useLiveStore(
  (state) => state.steering.maximumAssistanceActive,
)
```

Use shallow comparison only for genuinely grouped values. Do not subscribe panels to the entire
store for convenience.

Shared presentation components receive values as props and do not read sockets or API clients.

For smooth gauges, retain authoritative sample values in Zustand and interpolate visual motion
locally with CSS or `requestAnimationFrame` where useful. Do not put animation frames into Zustand
or force React to render at display refresh rate.

## TanStack Query ownership

TanStack Query owns:

- Application settings.
- Steering-profile collection and detail resources.
- Any durable device configuration/calibration resources.
- Operational/development HTTP mutation pending, success and error state.

One API client owns low-level `fetch`, response parsing and the shared problem envelope. Components
consume query options/hooks and mutations; they never call `fetch` directly.

Query policy:

- Use stable exact query keys.
- Give durable resources explicit `staleTime` values.
- Disable focus/reconnect refetch where precise socket invalidation and reconnect reconciliation
  already own freshness.
- On successful resource mutation, replace the exact cache entry from the response.
- On `resources.changed`, invalidate only the matching resource/query.
- After a new socket boot/reconnect snapshot, invalidate the small known durable-resource roots once
  to recover any missed invalidations.
- Do not store live state or trace batches in Query.

Operational command acknowledgements do not invalidate live state. The resulting authoritative
state arrives through Socket.IO.

## Loading and mutation UX

Pending state belongs to the initiating action:

- A simulated RPM input may disable/show progress for its own submit action.
- A maximum-assistance command may indicate pending on that control.
- Saving settings may affect the settings form.

It must not:

- Fade the complete vehicle panel.
- Replace unrelated current telemetry with a loading state.
- Mark all queries fetching.
- Block navigation or adjacent controls without a domain reason.

If a command acknowledgement returns before the live topic update, retain the last authoritative
live value and show only local pending state. Do not optimistically claim physical observation.

## Connection behavior

- Connection loss marks live data unavailable/stale according to the existing UI policy while
  retaining durable Query resources.
- Reconnection waits for `controller.snapshot` before declaring live state synchronized.
- A new `boot_id` atomically replaces previous live state.
- Protocol incompatibility produces one clear application-level error.
- Multiple providers/routes cannot construct duplicate sockets.
- React Strict Mode mount/unmount behavior cannot duplicate listeners.

## Legacy frontend removal

After all current screens consume Zustand/Query ownership:

- Remove frontend use of the raw WebSocket endpoint.
- Remove snapshot Query keys and cache-merging helpers used only for live events.
- Remove direct simulator fetch helpers superseded by mutations.
- Remove broad `isFetching` presentation behavior.
- Preserve backend legacy endpoint until Phase 8 in case external consumers exist.

Document any remaining compatibility import and assign Phase 8 removal.

## Tests

Transport/store:

- One connection and one listener per event across route changes and Strict Mode remounts.
- Complete snapshot replacement and boot change.
- Per-topic older/duplicate revision rejection.
- Disconnect/reconnect synchronization.
- Explicit teardown removes listeners.
- Trace capacity never exceeds its configured bound.

Query/API:

- Every component action reaches a TanStack mutation, not direct fetch.
- Successful resource mutations replace exact cache values.
- Precise resource events invalidate only matching keys.
- Reconnect invalidates known durable roots once.
- Operational command acknowledgements do not invalidate live queries.

Components:

- A vehicle update rerenders subscribed instruments without rerendering unrelated settings/button
  panels.
- A local mutation affects only its control/form pending presentation.
- Connection loss and resynchronization remain honest across `/dev` and `/car`.
- Trace virtualization/bounds preserve current diagnostic usability.

## Browser and memory evidence

Run the application against sustained simulated traffic in React development and production builds.
At minimum inspect:

- Socket connection/listener counts before and after route changes.
- Zustand trace length and current-state object counts.
- TanStack Query cache entry count.
- DOM node count after repeated navigation.
- Browser performance-entry count relevant to the original crash.
- Heap behavior after warm-up and garbage collection.

Run long enough to cover repeated telemetry, commands, trace open/close and background/foreground
cycles. Evidence must show bounded retained structures and no continuing monotonic growth attributable
to application ownership. Do not hide the result by disabling React tooling or changing the dev
environment.

## Completion criteria

- One Socket.IO singleton outside React owns all live events.
- Zustand owns current live state; trace has a separate fixed bound.
- TanStack Query owns every HTTP resource and mutation used by components.
- No component/provider calls `fetch` or attaches socket event listeners directly.
- Live snapshot data is absent from the Query cache.
- Narrow selectors prevent adjacent-topic rerenders.
- Mutation pending state is local and no longer fades unrelated panels.
- Reconnect and boot replacement are deterministic.
- Browser evidence demonstrates bounded listeners, trace, Query entries, DOM and retained live data.
- Existing `/dev` and `/car` behavior passes component and collaborative-browser regression.

