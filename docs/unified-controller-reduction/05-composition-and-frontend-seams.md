# Phase 5: Composition and frontend seams

## Goal

Remove construction, configuration and consumption layers that no longer select real variability.
Leave one obvious way to build each supported mode and one obvious way for the frontend to consume
live versus durable state.

Minimum production reduction: **200 lines**.

## Preconditions

- Phases 1-4 are `Verified`.
- Supported live/simulated/device-role matrices are documented from current behavior.
- Frontend route/browser acceptance is green after publication reduction.

## Backend composition

Inspect:

- Composition selection dataclasses/enums and validation.
- CLI-to-API construction and import-string application setup.
- Live/simulated adapter factories and test injection seams.
- Configuration values that never vary in a supported deployment.
- Startup/lifespan functions that only forward the same owners.

Prefer explicit `live` and `simulated` constructors sharing small common functions over a generic
builder with many optional parameters when that reduces concepts and code. Preserve startup
validation for conflicting authorities and output grants. Do not make physical capability selection
implicit to save configuration code.

## Frontend seams

Inspect:

- `LiveDataProvider`, transport owner, live/trace stores and route ownership.
- API helper wrappers returning `void` or forwarding an unchanged request.
- Duplicate live contract aliases and selectors.
- Component-local availability conversions repeated across screens.
- Query helpers with one call site and no cache policy.

Preserve:

- One socket instance/listener set outside route components.
- Zustand-only current live state and Query-only durable resources.
- Narrow selectors and localized pending/error UI.
- Trace subscription cleanup and fixed retention.
- 800x480 route behavior and light/dark presentation.

Remove a wrapper only when the resulting call remains clear and typed. Do not inline transport
lifecycle details into components or merge live and durable stores.

## Tests and browser matrix

- Retain ownership, reconnect, store merge and route acceptance tests.
- Remove tests for deleted one-caller wrappers after behavior is covered at the surviving boundary.
- Exercise `/dev` and all `/car` routes in light/dark at 800x480.
- Repeat same-document route cycles and confirm one socket/listener set.
- Exercise pending, success, failure and resource-conflict states touched by changed code.

## Verification

Run all backend/frontend/static/generated checks from Phase 2, relevant CLI/lifecycle tests, the
browser matrix and `git diff --check`.

## Completion criteria

- At least 200 net production lines are removed.
- Supported live/simulated composition remains explicit and invalid authority/output combinations
  still fail before startup.
- At least one backend construction layer or frontend consumption wrapper is removed without adding
  another abstraction.
- The frontend still owns exactly one socket and retains the live/durable boundary.
- Browser layout, localized mutation states and reconnect behavior remain correct.
- No test-only production factory, deprecated import or forwarding facade remains.

