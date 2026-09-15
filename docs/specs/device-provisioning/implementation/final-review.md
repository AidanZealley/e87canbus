# Device lifecycle tooling whole-feature review

Status: accepted.

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

## Aidan's post-closure decisions

- Broaden the corrected CI syntax coverage to the three general hardware shell scripts and the
  application-builder shell script. Compile both Python-shebang build/provisioning helpers rather
  than passing them to `bash -n`.
- Surface the original message from the existing safe recovery, artifact, application-build,
  provisioning and disk exception types. Unexpected exceptions retain the generic provisioning
  failure message.
- When card writing and final unmount both fail, retain the write/readback failure as the primary
  message and append the cleanup failure. An unmount-only failure still fails normally.
- Remove every remaining active coordinator-panel button concept: firmware input setup, debounce
  logic, tests, wiring asset and current documentation. Preserve historical ADR and implementation
  records until the planned documentation cleanup.
- Keep the fixed application-builder Debian snapshot. Its reproducible build-toolchain role is
  intentionally distinct from the rolling Raspberry Pi image package policy.
- No production CORS correction is needed. The installed systemd override already replaces the
  base command and supplies only the console origin.

### Post-closure review and resolution

- Reviewer: Claude Code Opus at medium effort through the configured read-only command.
- Initial verdict: Changes required. The implementation was accepted, but the current Wi-Fi
  specification retained one obsolete physical-button sentence and this record had not
  superseded the earlier decisions. The reviewer optionally identified the second Python helper
  for CI compilation and questioned safe validation errors inside `write_card`.
- Resolution: Removed the stale active-specification sentence and button-press step from the active
  physical procedure. Updated ADR 0013 and active wiring documentation for complete button
  removal. Added both Python helpers to CI compilation. Preserved only the already-approved safe
  artifact and provisioning messages through both writer validation boundaries; arbitrary
  exceptions remain sanitized. Historical decisions above remain unchanged and are superseded by
  this additive record.
- Closure verdict: Accepted. Claude verified the complete remediated diff and found no required
  issue or release-blocking defect introduced by the changes. Accepted commits are
  `3fa1571708c5e5027d848c15b54b7c08da5b75e6`,
  `5c70dac02052bcd67085c7d94128c51fdf53cd30` and
  `b1bc43ede509f1fae43956e2b7423d9af62fa332`.
- Revised physical evidence gap: Complete the real `e87ctl verify` runs, laptop DHCP and
  authorization checks, console disconnect/no-replay recovery, distinct machine-ID evidence,
  Ethernet-disconnected operation and invalid-bundle disposable-card result. Panel-button
  invariance is no longer applicable because the button is absent from the product.

### Provisioning image-selection performance correction

- Decision: Do not hash every local image before displaying the interactive image list. Parse each
  bounded strict manifest and check that its role-specific paired payload resolves to a regular
  file of the declared size. Fully validate only the selected image's SHA-256 before application
  building, bundle creation, target recheck or disk access. Explicit `--image` selection keeps the
  same full validation.
- Review: The configured Claude Code Opus call exited at its session quota without returning a
  review. A fresh in-session fallback reviewer found one required issue: a size-only metadata check
  could list a directory or special file. The implementation owner added the regular-file check
  while preserving symlinks to regular files. A different fresh fallback closure reviewer accepted
  the correction with no remaining or introduced required finding.
- Verification: The focused artifact and macOS provisioning suites passed (`65 passed`); the full
  `e87ctl` suite passed (`141 passed`). Ruff, strict mypy over 142 source files, direct symlink
  behavior and `git diff --check` passed. Tests prove listing opens no image payload and full
  validation opens only the selected payload before any later build or disk operation.
- Accepted commit: `1034e87222a1ac6d54835fbda34e9e0fa87c9621`.

## Orchestrator pre-workstream-9 record

- Final head and verification: Code corrections end at
  `f67e02e226491b7211c61ffd97bc73ce0c3a2792`. The physical-verifier correction passed `995`
  Python tests under independent Claude closure, plus Ruff and mypy. The orchestrator separately
  passed `96` focused tests, Ruff, mypy over 142 source files, provisioning-consumer compilation,
  application-builder shell syntax and `git diff --check`. Earlier whole-feature verification passed: `987` Python tests,
  mypy over 142 source files, Ruff, import contracts, generated protocol checks, provisioning
  consumer and application-builder helper compilation, per-file shell syntax and
  `git diff --check`. The unchanged frontend had already passed API checks, lint, typecheck, `208`
  tests and both production builds at whole-feature closure. PlatformIO native tests passed (`3`
  tests) and the RP2040 production firmware built after complete button removal.
- External validation pending: The macOS writer gate remains `Passed`. The provisioned-pair gate is
  `Troubleshooting` after real `e87ctl verify` exposed three measured defects despite the successful
  `eda0d12` deployed-device result. Build fresh artifacts, create a new installation, reprovision
  both cards and run the corrected verifier at least twice before completing the outstanding
  physical checks. Mechanical display spacing remains separate hardware work.
- Specification drift: No unrecorded implementation drift. Aidan classified mechanical
  DSI/display spacing as separate hardware integration work rather than a software gate blocker.
- Completion report delivered after the reopened review below.

Workstream 9 was approved after this review because the physical gate exposed avoidable operator
friction. After accepting it, run the documented whole-feature review against the new head. Keep
that review focused on CLI compatibility, reuse of the accepted verifier, secret-free evidence and
documentation agreement. The provisioned-pair gate remains `Troubleshooting` until the new guided
command and all outstanding physical evidence pass.

Workstream 9 implementation and its Claude review are complete at `8205dbb`, followed by the
format-only `f8b8e02` sweep. Real hardware produced four passing guided-verifier results, two per
role, with stable exact releases and complete SSH and mutual-TLS checks. The shared external gate
still lacks the exact image-build provenance and the rest of the workstream 7 and 8 evidence, so
workstream 9 remains at closure rather than final acceptance and the reopened whole-feature review
has not started.

## Reopened whole-feature review

- Reviewer: Claude Code Opus at medium effort through the configured read-only review command.
- Reviewed range: `7d7c2387c0d6b1135eeec842b08cc8ee9a827ef3` through gate-acceptance commit
  `b4ac430` on `feature/device-lifecycle-tooling`.
- Verification: Claude passed `1009` Python tests, mypy over 143 files, Ruff and both import
  contracts. The orchestrator independently passed the same Python suite, generated protocol and
  frontend API checks, all `208` frontend tests, both frontend production builds, relevant shell
  syntax, provisioning-consumer compilation and `git diff --check`.
- Acceptance audit: The CLI and workstation-only package boundary, destructive-disk safety,
  secret lifecycle, signed identity, first-boot atomicity, network isolation, TLS and application
  authorization, complete removal of the superseded Ethernet and panel-button paths, guided
  verification and Git artifact exclusions satisfy their approved contracts. Recorded macOS,
  image-build and Raspberry Pi results remain external evidence rather than review-host claims.
- Verdict: Changes required. The reviewer found two localized required issues and no architectural
  or security-boundary failure.

### Required findings

1. Workstream 6: `failure_identity` reads `manifest.json` from an invalid provisioning ZIP without
   first enforcing `MAX_MANIFEST`. A hostile declared uncompressed size could exhaust Pi memory in
   the failure-reporting path before it writes the bounded `invalid_bundle` status. Accept. Bound
   the failure-path read using the consumer's existing limit and add one focused oversized-entry
   test.
2. Workstream 3: private helper `_validate_file` in `e87ctl/src/e87ctl/artifacts.py` has no caller.
   Accept. Delete the dead helper as part of the required final simplification pass.

### Optional observations

The reviewer noted duplicated verifier literals, repeated provisioning-bundle validation,
short-read `dd` cleanup, a narrow temporary-key file-mode window, duplicate guided-result
derivation, one private helper import and no ignore rule for a recovery package deliberately
written inside the checkout. None changes an accepted criterion or presents a demonstrated release
defect, so none is promoted during closure.

### Questions and disposition

- The final report must state that the four application and provisioning digest values were
  observed to match but were not retained. Accepted; the gate and decision log already record that
  explicit limitation.
- The remaining physical observations are Aidan's attestation rather than captured command output.
  Accepted by Aidan when he instructed the orchestrator to close the workflow.

### Remediation and focused closure

- Workstream 6 bounded `failure_identity` before opening or decompressing the ZIP manifest. A
  focused test proves an entry larger than `MAX_MANIFEST` is never opened in the failure-reporting
  path. The owner passed all `21` provisioning-consumer tests, consumer compilation and
  `git diff --check`.
- Workstream 3 deleted the unused `_validate_file` helper. No import or caller was left behind. The
  owner passed all `34` provisioning-artifact tests, Ruff, mypy and `git diff --check`.
- A fresh Claude Code Opus closure call at medium effort accepted both fixes with no remaining
  required finding or release-blocking defect introduced by remediation. It passed the full
  `e87ctl` suite (`161` tests), all `21` provisioning-consumer tests, strict mypy, Ruff, consumer
  compilation and `git diff --check`.

### Final verification and verdict

- The orchestrator passed `1010` Python tests, mypy over 143 files, Ruff, both import contracts,
  generated protocol and frontend API checks, all `208` frontend tests, both frontend production
  builds, relevant shell syntax, provisioning-consumer compilation, the tracked secret/artifact
  filename audit and `git diff --check`.
- Both external gates are `Passed`, all nine workstreams are accepted and no required review
  finding remains. The workflow is complete.
- Known evidence limitation: the four application and provisioning digest values matched during
  physical testing but their literal values were not retained. Aidan accepted this limitation.
- Deferred hardware work: design and validate the console display spacer that mitigates measured
  2.4 GHz DSI/display proximity interference. This does not block the completed software and image
  workflow.
