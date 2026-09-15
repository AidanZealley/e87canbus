# Device lifecycle tooling whole-feature review

Status: focused closure accepted; physical-evidence decision pending.

## Reviewer task packet

Review the complete integration branch against the recorded starting commit and all three approved
product documents. Read accepted handoffs and external evidence, but independently inspect the
combined diff and surrounding code.

Audit CLI/package boundaries, destructive-disk safety, secret lifecycle, cryptographic identity,
strict artifact validation, first-boot atomicity, unique host identity, application packaging,
network isolation, TLS and application authorization, console failure behavior, status accuracy,
dependency direction, generated contracts, test value, documentation agreement and deletion of
the superseded path.

Confirm that recovery packages, private keys, passwords, images and bundles are absent from Git and
logs. Treat recorded macOS and Pi results as external evidence; do not infer hardware success from
fixtures. Reject optional hardening that exceeds the approved threat model unless it exposes a
concrete acceptance or correctness failure.

Run the repository-wide commands from workstream 7 and any focused checks needed to investigate
the final diff. Record unavailable platform checks honestly rather than substituting weaker claims.

## Initial whole-feature review

- Reviewer: Claude Code Opus at medium effort through the configured read-only review command.
- Branch, base and reviewed head: `feature/device-lifecycle-tooling`,
  `7d7c2387c0d6b1135eeec842b08cc8ee9a827ef3` through
  `6053ef99e9961a06efb09c81bb428bcdb3d852c1`.
- Verification run: `uv run pytest -q` passed (`980 passed`); mypy passed over 142 source files;
  Ruff, import contracts, generated protocol, frontend API generation check, lint, typecheck, 208
  frontend tests, both production frontend builds, provisioning-consumer compilation, per-file
  shell syntax and `git diff --check` passed. Docker ARM64 builds, image builds, macOS tooling,
  Raspberry Pi behavior and PlatformIO were unavailable on the review host and were not claimed.
- Acceptance-criteria audit: The reviewer accepted the CLI boundary, destructive writer,
  secret lifecycle, cryptographic identity, artifact validation, first-boot atomicity, host
  identity, application packaging, network isolation, TLS and authorization, status contracts,
  dependency direction, generated artifacts, superseded-path deletion and test value. No secret,
  recovery package, image or application bundle is tracked. The physical gate record does not
  enumerate several originally required hardware checks described below.
- Required findings by owner:
  1. Orchestrator with workstreams 7 and 8: the accepted physical report does not record real
     `e87ctl verify coordinator|console` runs, laptop DHCP and authorization checks, panel-button
     invariance, console disconnect/no-replay recovery, distinct machine IDs, Ethernet-disconnected
     operation or the invalid-bundle disposable-card result. Either supply that evidence or record
     an explicit accepted limitation before completing the workflow.
  2. Workstream 7 with workstream 1: CI passed several paths to one `bash -n` invocation, which
     parsed only the first shell file and silently treated the remaining paths as arguments. It
     also treated the Python provisioning consumer as shell and omitted the image hooks/checker.
  3. Workstream 6: the firewall helper fell through after its existing-table replacement branch
     and applied the nftables configuration a second time, duplicating rules on every reload.
- Optional observations: One recovery sidecar helper had no production caller; provisioning
  collapses several safe-to-display errors into a generic disk error; two files have untidy blank
  spacing; an unmount failure can obscure an earlier write failure; two unset development CORS
  variables become harmless empty origins; the application builder and Pi images intentionally use
  different package drift policies; and one accepted historical image-building record links to a
  later-deleted setup script.
- Questions: Whether to supply or explicitly waive the missing physical evidence, and whether the
  intentionally retained but ignored panel-button debouncer should remain.
- Verdict: Changes required.

## Orchestrator triage

- Accepted findings and owners: Accept all three required findings. The evidence gap remains with
  the orchestrator pending Aidan's decision. A fresh Workstream 7 owner corrected CI to parse every
  shell file separately and compile the provisioning consumer as Python. A fresh Workstream 6
  owner made the firewall execute exactly one nftables load in either branch. Promote the unused
  recovery helper observation to Workstream 2 because removing its sole test and 27 lines of dead
  code completes the requested simplification pass without changing a public boundary. Fresh
  owners were used because the original implementation-agent sessions were no longer available in
  the current orchestration context.
- Rejected findings and reasons: Keep the wired button input and debouncer because Aidan explicitly
  approved retaining that inert firmware boundary; no event or host reader exists. Keep accepted
  historical implementation records immutable. Do not expand this final correction batch into
  user-facing error redesign, package-policy changes or speculative handling of rare secondary
  failures when none blocks an acceptance criterion.
- Deferred optional observations: Generic provisioning-error wording, blank-line style, unmount
  error precedence, harmless empty development CORS origins and the application-builder snapshot
  policy. Record them as non-blocking observations; do not add machinery for them here.
- Drift requiring user decision: The original gate requires evidence not present in the accepted
  `eda0d12` report. Completing without it requires Aidan to approve an explicit limitation. The
  mechanical DSI/display spacer is already approved as separate hardware integration work and does
  not block this software workflow.

Return each accepted correction to its original workstream owner in one batch. Use a new owner only
when the original is unavailable, and record why.

## Focused closure

- Reviewed head: The complete uncommitted remediation diff on
  `6053ef99e9961a06efb09c81bb428bcdb3d852c1`, subsequently committed as
  `ce16ae39f564774b53aa4ab2e0ee55aed81049df`,
  `06462fe30af212546f28f67d60b5d256d90b9243` and
  `08700e459c90287273858b3c3caf0b5afcc0f577`.
- Finding outcomes: Claude Code Opus at medium effort verified that CI parses each intended shell
  file and compiles the Python consumer, firewall startup and reload each perform exactly one
  fail-closed nftables load, and removing `write_ca_sidecar` leaves the atomic public recovery
  workflow unchanged. No remediation defect was found.
- Final simplification assessment: Net subtractive. Removed 27 lines of dead helper and test code;
  added no flags, wrappers, aliases, compatibility paths or parallel firewall implementation.
- Remaining blockers: The accepted `eda0d12` physical report does not enumerate all evidence in
  the original workstream 7 and 8 gate procedure. Supply the remaining evidence or approve an
  explicit accepted limitation. Mechanical display spacing is already separate hardware work.
- Verdict: Accepted with no further remediation cycle; the evidence decision remains outside code
  closure.

## Orchestrator completion record

- Final head and verification: Code corrections end at
  `08700e459c90287273858b3c3caf0b5afcc0f577`. Final verification passed: `979` Python tests,
  mypy over 142 source files, Ruff, import contracts, generated protocol checks, provisioning
  consumer compilation, per-file shell syntax, frontend API checks, lint, typecheck, `208` tests,
  both production builds and `git diff --check`.
- External validation pending: Both documented gates are marked `Passed`. Completion still awaits
  the decision whether to supply the physical checks absent from the `eda0d12` report or accept
  them as explicit evidence limitations.
- Specification drift: No unrecorded implementation drift. Aidan classified mechanical
  DSI/display spacing as separate hardware integration work rather than a software gate blocker.
- Completion report delivered: `TBD`
