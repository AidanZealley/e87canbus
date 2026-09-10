# Workstream 2: Create the installation authority and recovery package

Status: not started.

## Task packet

### Outcome

`e87ctl installation create --output <path>` creates the one caller-owned v1 recovery package and
public CA sidecar with the exact identities and credentials required by later provisioning.

### Scope

- Implement the P-256 installation CA, installation-ID derivation and strict recovery schema.
- Generate the specified Wi-Fi, operator and Ed25519 SSH credentials using secure randomness.
- Write exact PEM/OpenSSH encodings, v1 validity windows, permissions and no-overwrite behavior.
- Validate recovery packages on load and expose typed values to later CLI modules.
- Produce secret-free human and JSON summaries; test log and exception boundaries.
- Add only the direct cryptography, schema and password-hashing dependencies required.

### Non-goals

- Device leaf certificates, provisioning bundles, disk writes or a hidden credential store.
- Recovery-package encryption, revocation, rotation, inventory or alternate encodings.
- A configurable cipher, curve, password policy or certificate profile system.

### Initial ownership

- Installation, identity, secret-output and recovery modules under `e87ctl/src/e87ctl/`
- Their focused tests under `e87ctl/tests/`
- `e87ctl/pyproject.toml`, root `uv.lock` and CLI registration as integration exceptions

### Required seams

- The complete installation ID is derived from the domain-separated DER SubjectPublicKeyInfo hash.
- Recovery values are read explicitly per operation and never cached in hidden state.
- Private material is available to later device-certificate creation without stringifying it in
  commands, logs or structured output.
- The public sidecar can be recreated from the recovery document.

### Acceptance criteria

- Generated CA constraints, usages, validity and installation ID match the specification.
- The JSON has only the fixed v1 fields and encodings, mode `0600`, and refuses replacement.
- Operator username is fixed to `operator`; all other secrets use secure randomness.
- The CA sidecar contains only the public certificate.
- Malformed, unsupported and internally inconsistent recovery files fail safely.
- Tests prove no generated secret reaches normal output or captured logs.

### Targeted verification

```bash
uv run pytest e87ctl/tests -q
uv run ruff check e87ctl
uv run mypy
uv run e87ctl installation create --help
```

## Implementation handoff

- Base commit: `TBD`
- Outcome: `TBD`
- Files changed: `TBD`
- Decisions: `TBD`
- Verification: `TBD`
- Security assumptions and secret-output audit: `TBD`
- Known limitations or external checks: `TBD`
- Specification drift: `TBD`

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

