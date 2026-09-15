# Workstream 9: Guided pair verification

Status: implemented, awaiting independent review.

## Task packet

### Outcome

`uv run e87ctl verify` guides an operator through complete pair verification without requiring them
to assemble four role-specific commands while disconnected from the internet. It collects local
inputs before the network switch, verifies both devices twice, and saves one secret-free evidence
report that can be inspected after the MacBook reconnects to its normal network.

### Scope

- Add an interactive form of `e87ctl verify` when no role is supplied.
- Prompt for the caller-owned recovery-package path. Do not search for or remember recovery
  packages.
- Prompt for the coordinator and console Ed25519 SHA-256 host-key fingerprints before asking the
  operator to connect to the installation network.
- Show one short network-switch instruction and wait for explicit confirmation before making
  device connections.
- Run the existing coordinator and console verification paths twice each. Keep their validation,
  trust and failure rules unchanged.
- Write one bounded, secret-free report containing both passes, role results and elapsed times to
  an operator-selected path. Make partial or failed results available without reporting success.
- Keep the existing explicit `verify coordinator|console` commands for automation, offline status
  checks and focused troubleshooting.
- Update the active specification and operator documentation for the guided command.

### Non-goals

- No hidden installation inventory, default recovery-package directory or remembered credentials.
- No automatic Wi-Fi or route changes.
- No internet proxy, forwarding or weakening of the coordinator's no-gateway network.
- No trust on first use. The operator still obtains each fingerprint from its physical Pi and the
  verifier still requires an exact match.
- No new device discovery protocol, daemon, GUI or remote service.
- No change to the existing per-role verification checks or the hardware display-spacing work.

### Initial ownership

- `e87ctl/src/e87ctl/cli.py`
- A small guided-flow module under `e87ctl/src/e87ctl/` only if keeping the CLI dispatcher readable
  requires it
- Existing verification result models, or one focused combined-report model beside them
- `e87ctl/tests/test_verify.py`
- `e87ctl/tests/test_installation.py` only if its shared CLI secrecy coverage needs extending
- `docs/specs/device-provisioning.md`
- Active operator documentation that shows the verification command
- This workstream record

Do not change provisioning, recovery-package contents, on-device services, network profiles or
image composition.

### Required seams

- Reuse `verify_device` as the only device-verification implementation. The guided flow coordinates
  calls and must not duplicate checks.
- Load the recovery package through the existing strict loader.
- Reuse the existing `VerificationResult` data for each role and pass. Keep any combined report
  schema narrow and versioned.
- Keep normal human output on the terminal. The saved report must contain no recovery-package
  secrets, private keys, passwords or certificate private material.
- Explicit role commands retain their current arguments and output for compatibility.

### Acceptance criteria

- Running `uv run e87ctl verify` interactively collects the recovery path, both trusted
  fingerprints and report path before asking the operator to switch networks.
- After confirmation, one command verifies coordinator and console twice and records all four
  results plus elapsed times.
- A second pass that detects release mutation fails the overall command and remains visible in the
  saved report.
- Invalid local input fails before the network-switch prompt. A device failure produces a nonzero
  exit and a bounded report containing the completed evidence.
- The command never writes or logs recovery secrets.
- Existing explicit online and offline commands behave exactly as before.
- Help text makes the guided and explicit forms obvious without requiring the implementation
  runbook.

### Targeted verification

```bash
uv run pytest e87ctl/tests/test_verify.py e87ctl/tests/test_installation.py -q
uv run ruff check e87ctl
uv run mypy
git diff --check
```

Add focused tests for prompt ordering, two passes, failure reporting, secret-free output and
unchanged explicit-command dispatch. Prefer injected input and clocks over subprocess-heavy test
machinery.

## Implementation handoff

- Base commit: `437e4c6`
- Outcome: `uv run e87ctl verify` with no role runs the guided pair check. It collects the
  recovery-package path, both trusted fingerprints and the report path, asks for one network-switch
  confirmation, verifies the coordinator and console twice each and saves one secret-free report.
  The explicit `verify coordinator|console` commands keep their arguments, output and exit codes.
- Files changed: `e87ctl/src/e87ctl/guided.py` (new), `e87ctl/src/e87ctl/cli.py`,
  `e87ctl/tests/test_verify.py`, `docs/specs/device-provisioning.md`, `deploy/README.md`,
  `images/README.md`, this record.
- Decisions:
  - The guided flow lives in its own module. Keeping it in `cli.py` would have doubled that
    dispatcher's size with prompt sequencing that has nothing to do with argument parsing.
  - `run_passes` only sequences `verify_device`; it duplicates no check. Prompts, clock and
    verifier are injected, so the tests need no subprocess or network machinery.
  - The report is a new narrow `PairVerificationReport` v1 holding four
    `PairVerificationPass` entries, each wrapping an unmodified `VerificationResult` with its role,
    pass number and elapsed seconds. A validator forbids claiming `passed` without four passing
    passes. It contains no recovery-package material.
  - A `VerifyCommandError` from a device call stops the remaining passes and is recorded as
    `incomplete_reason`, so a bad package or unreachable network does not cost the operator three
    more full timeouts. Ordinary `failed` results never stop the run, so a mutated release is still
    visible in both passes.
  - The report path is rejected up front if it exists or its directory is missing, keeping
    overwrite and path mistakes on the internet-connected side of the network switch.
  - `verify` with no role rejects `--installation`, `--status`, `--host-key-fingerprint` and
    `--json` rather than silently ignoring them. An explicit role still requires `--installation`;
    argparse can no longer enforce it now that the role is optional.
- Verification: `uv run pytest e87ctl/tests -q` (161 passed), `uv run ruff check e87ctl`,
  `uv run mypy` (143 files, clean), `git diff --check`. Fourteen new tests cover prompt ordering,
  each invalid local input failing before the network prompt, the four-pass sequence and elapsed
  times, a failing second pass staying visible, partial evidence after an abort, the report
  contract, and a secret-free written report from the real CLI path. Also smoke-tested end to end
  against a throwaway installation with no devices present: four recorded failing passes, a written
  report and exit 1.
- Known limitations or external checks: Internet access still needs a second interface while the
  MacBook is attached only to the isolated coordinator network. The guided flow removes the need
  for live agent help during that interval and leaves a report for later review.
- Specification drift: Aidan approved adding the guided form while retaining the explicit
  commands and security boundaries.

## Independent review

- Reviewer: `TBD`
- Verdict: `TBD`
- Required findings: `TBD`
- Optional observations: `TBD`
- Questions for orchestrator: `TBD`

## Resolution

- Finding dispositions: `TBD`
- Simplification/deletion pass: `TBD`
- Final verification: `TBD`

## Closure review

- Verdict: `TBD`
- Remaining required findings: `TBD`
- Accepted commit: `TBD`

## External validation

- Gate and placement: Complete provisioned pair after this workstream's closure.
- Status: `Troubleshooting`
- Candidate and instructions: `f67e02e226491b7211c61ffd97bc73ce0c3a2792` is the current software
  correction. Nominate a new exact candidate after this workstream is accepted, then build a fresh
  installation and cards and use the guided command.
- Required evidence: All existing workstream 7 and 8 gate evidence, plus the saved report showing
  two passing checks for each role.
- Attempts and lasting decisions: Preserve the successful `eda0d12` device result and its measured
  verifier defects. The display-spacing mitigation remains hardware work.
- Resume condition: Both passes for both roles succeed, the complete physical evidence is recorded
  and the provisioned-pair gate returns to `Passed`.
