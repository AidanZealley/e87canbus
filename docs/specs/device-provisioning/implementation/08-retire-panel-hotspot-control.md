# Workstream 8: Retire the panel hotspot control

Status: closure accepted; external validation pending.

## Why this exists

The provisioned Wi-Fi network and the panel hotspot button control the same NetworkManager
connection. The access point now starts automatically and carries the console's only transport, so
the old maintenance-hotspot button can disconnect the console while the coordinator is running.
The hotspot display states also outrank `READY`, which prevents the healthy steady-state display
while the console remains associated.

Workstream 6 raised this conflict and deferred it. Aidan chose full removal in a separate Claude
thread on 2026-09-12 and confirmed that decision in the orchestration thread. The panel becomes a
status indicator with no network authority.

## Task packet

### Outcome

The coordinator panel shows `STARTING`, `READY`, `FAULT` and `OFF` only. It cannot start or stop
the provisioned Wi-Fi network. The obsolete hotspot helper, privileged host path, simulator and UI
operations, and firmware button event are absent.

### Scope

- Delete the host hotspot model and NetworkManager adapter with their focused tests.
- Reduce panel behavior to coordinator status and remove the hotspot dependency and button path
  from physical and simulated runners.
- Remove simulator API models and routes for hotspot state, connection, failure and panel presses.
  Regenerate the OpenAPI document and coordinator client rather than editing generated files.
- Remove hotspot controls and copy from the coordinator panel and simulator UI.
- Remove hotspot display states from coordinator-panel firmware. Keep the physical button wired
  and debounced, but stop emitting its UART event.
- Delete the root hotspot helper and sudo rule. Remove their image installation checks and restore
  `NoNewPrivileges=true` for the coordinator service.
- Update active panel, image and wiring documentation. Extend ADR 0013 to supersede the panel
  control in ADR 0010 while preserving accepted ADR history.
- Update the Wi-Fi specification so no panel action starts or stops the provisioned network.

### Non-goals

- Repurposing the physical button or reserving its UART command.
- Adding a console-link indicator or rebuilding one from wireless station polling.
- Changing access-point, DHCP, firewall, nginx or authorization behavior.
- Renaming hotspot-related comments that describe the provisioned access point rather than the
  removed control path.

### Initial ownership

- `hosts/src/e87canbus/{hotspot,panel}.py`, the NetworkManager hotspot adapter, panel runners and
  focused host tests
- Simulator panel API, `protocol/openapi.json` and generated coordinator-client output
- Coordinator panel and simulator frontend components and tests
- `devices/coordinator-panel/`
- Hotspot helper, sudo rule, coordinator service and coordinator image customization
- `docs/wiring.md`, `images/README.md`, `docs/specs/wifi-device-network.md` and ADR 0013

### Required seams

- Preserve the panel's heartbeat, fault, timeout and graceful-off behavior.
- Leave no host reader for a firmware event that is no longer emitted.
- Remove the controller service's last privileged network operation and its service-account sudo
  rule.
- Collapse the second panel thread if it exists only to isolate slow NetworkManager operations.
- Keep workstream 7 verification behavior and external-gate instructions synchronized with the
  final panel and image behavior.

### Acceptance criteria

- No coordinator code path can deactivate `e87canbus-coordinator-wifi`.
- `READY` is the steady-state panel display on a healthy provisioned coordinator.
- The image contains no hotspot helper or service-account sudo rule.
- Firmware emits no button event and the host has no handler for one.
- Simulator API, generated client and coordinator UI expose no hotspot operation or state.
- A service laptop can associate and reach HTTPS without physical panel action.
- ADR 0013 records retirement of ADR 0010's panel control without rewriting accepted history.
- Active documentation contains no instruction to press the panel button for Wi-Fi.

### Targeted verification

```bash
uv run pytest hosts/tests -q
uv run pytest e87ctl/tests/test_image_build.py e87ctl/tests/test_verify.py -q
uv run ruff check hosts e87ctl
uv run mypy
python3 -m py_compile deploy/bin/e87canbus-provision
for script in images/coordinator/customize.sh images/e87canbus-image-check \
  deploy/bin/e87canbus-firewall; do
  bash -n "$script"
done
```

```bash
cd frontend
pnpm api:generate
pnpm api:check
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

Run the native coordinator-panel PlatformIO tests. Confirm generated diffs contain only the
removed hotspot operations. Docker image assembly, NetworkManager and physical Pi checks remain
external and must not be claimed on the implementation host.

## External validation

- Gate and placement: complete provisioned pair, after closure and before acceptance.
- Status: `Pending`
- Candidate and instructions: Test `f4c775f36f05292615308828ac7151aa5d64bdb1` using the
  procedure in workstream 7, updated for the status-only panel.
- Required evidence: All evidence listed in workstream 7 plus a healthy steady-state `READY`
  display and confirmation that panel presses do not change the provisioned network.
- Attempts and lasting decisions: `TBD`
- Resume condition: All workstream 7 and 8 physical evidence passes on one exact candidate.

## Implementation handoff

- Base commit: `87441b224e69b1a91a845148dbb2cdc590121daf`
- Outcome: Retired the complete coordinator-panel hotspot authority. The physical and simulated
  panels now expose only coordinator `STARTING`, `READY`, `FAULT` and `OFF` status. NetworkManager
  autoconnect remains the sole owner of the provisioned access point.
- Files changed: Deleted the host hotspot service, NetworkManager adapter, root helper, sudo rule
  and their focused tests. Reduced the panel domain, UART adapter, physical and simulated runners,
  simulator API and tests. Regenerated `protocol/openapi.json` and the coordinator HTTP client.
  Removed coordinator and simulator UI controls and hotspot presentation. Reduced coordinator-panel
  firmware and tests to four display states without emitting button events. Updated coordinator
  image package/install wiring and checks, the controller unit, active panel/image/wiring
  documentation, the Wi-Fi specification, ADR 0013 and the combined physical-gate procedure.
- Decisions: Removed the operation and state contracts rather than retaining aliases. The physical
  runner now uses one thread for its one-second UART heartbeat because it no longer waits on
  NetworkManager. UART I/O failure still stops heartbeats so firmware reaches `FAULT`; orderly
  shutdown still sends `OFF`. Firmware continues to read and debounce the wired button but does
  nothing with a press. `CoordinatorStatus` is the one host, simulator API and frontend status type;
  there is no duplicate display field or alias. ADR 0013 now explicitly supersedes ADR 0009's
  hotspot mechanism and button handling while preserving its panel-isolation decision. ADRs 0009
  and 0010 remain unchanged as accepted history.
- Simplification pass: Removed the second panel thread, button queue, host UART reader, hotspot
  state machine, simulated hotspot backend, four simulator mutations, six-state display logic,
  duplicate panel-display type and API field, now-unused `iw` package and privileged service path.
  No button command, alternate network control or replacement indicator remains.
- Verification: `uv run pytest e87ctl/tests/test_image_build.py e87ctl/tests/test_verify.py
  hosts/tests -q` passed (`893 passed`). Ruff passed for `hosts` and `e87ctl`; mypy passed over 142
  source files. Shell syntax passed for the coordinator image hook, image checker and firewall
  helper; the provisioning consumer compiled; the coordinator-panel logic header passed a C++17
  syntax check; and `git diff --check` passed. `pnpm api:generate` regenerated the source-derived
  contracts. Frontend API checks, lint, typecheck, all tests and both production builds passed (`6`
  coordinator-client files with `18` tests, `24` console files with `101` tests and `21` coordinator
  files with `89` tests). PlatformIO is not installed on this host, so the native coordinator-panel
  test command was unavailable and is not claimed. Docker image assembly, NetworkManager and
  physical Pi behavior remain at the documented external gate.
- Specification drift: Aidan approved making the panel status-only. The Wi-Fi specification and
  ADR 0013 now record that behavior. Naming both ADR 0009 and ADR 0010 in ADR 0013 corrects the
  source-history reference within that approved removal; it does not broaden the behavior change.

## Independent review

- Reviewer: Claude Code Opus at medium effort through the configured read-only review command.
- Verdict: Changes required.
- Required findings:
  1. The workstream 7 and 8 verification commands passed several paths to one `bash -n` invocation.
     Bash parses only the first path as a script and treats the rest as arguments, so the records
     overclaimed syntax coverage.
  2. `PanelDisplay` duplicated `CoordinatorStatus`, and the simulator API returned both identical
     values. This left two names and fields for one status-only concept after the hotspot states
     disappeared.
- Optional observations: Reflow the two documentation artifacts; return the effective simulated
  status instead of storing a temporary field initialized only by refresh; replace new
  path-deletion assertions with tests of the durable privilege boundary; remove the unobservable
  wiring debounce bench instruction; make ADR 0013 precise about which part of ADR 0009 it
  supersedes; and protect the single-thread UART write-failure behavior with one focused test.
- Questions for orchestrator: Whether retaining the wired pull-up button and debouncer leaves an
  unnecessary concept, and whether historical raspberry-pi-image-building records should also be
  rewritten to remove their accepted hotspot descriptions.

## Resolution

- Finding dispositions: Accepted both required findings. The shell commands now loop over existing
  paths and invoke `bash -n` once per file. `CoordinatorStatus` now flows directly through the panel
  domain, UART adapter, physical runner, simulator model, generated API and frontend. Promoted all
  optional cleanup because each removes misleading text, duplicate state or an implementation-only
  assertion. Keep the wired pull-up and debouncer because Aidan explicitly approved that packet
  boundary; firmware emits no event and the host has no reader. Keep accepted image-building
  records immutable; current specifications, active documentation and this workflow record the
  replacement behavior.
- Simplification/deletion pass: Deleted `PanelDisplay`, `derive_display`, their ceremonial focused
  test and the simulator's duplicate `display` field. Simulated refresh returns the effective
  status to the response builder instead of storing transient state. Image and deployment tests now
  protect `NoNewPrivileges` and the absence of an effective service-account sudo grant rather than
  named deleted paths. The new UART write-failure test proves that an I/O fault stops heartbeats and
  does not send graceful `OFF`.
- Final verification: The full targeted verification passed after remediation: `835` host tests
  and `58` focused `e87ctl` tests (`893` total), Ruff, mypy over `142` source files, provisioning
  script compilation, corrected per-file shell parsing and `git diff --check`. OpenAPI and client
  regeneration were clean; frontend API checks, lint, typecheck, `208` tests and both production
  builds passed. A direct C++17 syntax check of `panel_logic.h` passed. PlatformIO remains
  unavailable on this host, so its native test and the documented physical checks are not claimed.

## Closure review

- Reviewer: Claude Code Opus at medium effort through the configured read-only review command.
- Verdict: Accepted.
- Remaining required findings: None. The reviewer verified both required corrections and every
  promoted cleanup, including the durable privilege checks and UART failure behavior. PlatformIO,
  image assembly, NetworkManager and physical Pi behavior remain assigned to external validation.
- Accepted commit: `TBD`
