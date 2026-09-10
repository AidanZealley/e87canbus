# Workstream 2: Create the installation authority and recovery package

Status: accepted.

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

- Base commit: `b5c03e16b9e20995d5a4d2a82074973614bf0c44`
- Outcome: Added `e87ctl installation create --output <path>` with secret-free human and JSON
  summaries. It creates one strict v1 recovery document, its public CA sidecar and typed reload
  access to the installation authority and SSH management key.
- Files changed: Added `e87ctl/src/e87ctl/{identity,installation,recovery}.py` and
  `e87ctl/tests/test_installation.py`; extended `e87ctl/src/e87ctl/cli.py`; and added the direct
  `argon2-cffi`, `cryptography` and `pydantic` dependencies to `e87ctl/pyproject.toml` and the root
  `uv.lock`.
- Decisions: The closed, flat v1 JSON schema uses the eleven named fields exercised by the focused
  tests. The CA uses ECDSA P-256 with SHA-256, a fixed subject, critical CA basic constraints and
  only key-cert-sign usage. Its calendar validity is creation minus 24 hours through creation plus
  20 years. The SSID uses the first 12 installation-ID characters. Independent 32-character
  passwords use a consumer-safe 57-character alphabet. Load validation reparses credentials and
  checks canonical encodings, CA self-signature, key pairs, identity derivation, certificate
  profile and validity, fixed values and the absence of duplicate or unknown fields. Parsed
  private keys are returned on demand rather than cached.
- Verification: `uv sync --locked`; `uv run pytest e87ctl/tests -q` (`59 passed`); `uv run ruff
  check e87ctl`; `uv run mypy` (`135 source files`); `uv run e87ctl installation create --help`;
  and `git diff --check` passed.
- Security assumptions and secret-output audit: Recovery writes reserve both paths without
  replacement, set the recovery document to `0600` and the public certificate to `0644`, and
  remove partial outputs after failure. `SecretStr` protects model representations, normal output
  contains only the public installation ID and paths, the CLI replaces internal exceptions with a
  fixed error, and focused tests check generated secrets against stdout, stderr, captured logs and
  model representations. The recovery document remains intentionally plaintext and caller-owned.
- Known limitations or external checks: This workstream has no external gate. It does not create
  device certificates or provisioning artifacts; workstream 3 consumes the typed authority and
  password-hashing function.
- Specification drift: None.

## Independent review

- Reviewer: Codex (`/root/ws2_review_retry`), fresh independent reviewer. The first assigned
  reviewer stopped before inspecting the work because its account had reached a usage limit; this
  is the first completed review.
- Verdict: Accepted. The uncommitted workstream matches the approved installation-authority and
  recovery-package requirements, preserves the accepted CLI boundary and adds no competing
  credential store, cryptographic profile or lifecycle machinery.
- Required findings: None. The CA and installation ID use P-256, ECDSA with SHA-256 and the complete
  domain-separated DER SubjectPublicKeyInfo digest. The loader checks the key pairs, self-signature,
  fixed CA extensions, exact validity, identity, credentials, version and closed JSON fields before
  exposing fresh typed private-key values. Recovery creation reserves both final paths without
  replacement, applies `0600` and `0644` after creation and removes files it created when a normal
  write fails. Normal human and JSON output contains only the public installation ID and paths;
  loader and CLI error boundaries replace internal exceptions with fixed messages.
- Optional observations: The implementation handoff calls the password alphabet 58 characters,
  but `_PASSWORD_ALPHABET` contains 57 distinct characters. The generated 32-character passwords
  still use secure randomness, have ample entropy and fit their consumers, so this record-only
  discrepancy does not block acceptance.
- Questions for orchestrator: None.
- Verification: `uv sync --locked`; `uv run pytest e87ctl/tests -q` (`59 passed`); `uv run pytest
  -q` (`904 passed`); `uv run ruff check e87ctl`; `uv run mypy` (`135 source files`); `uv run
  e87ctl installation create --help`; and `git diff --check` passed. A real create under umask
  `000` produced recovery and sidecar modes `0600` and `0644`; OpenSSL inspection confirmed the
  v3 P-256 CA profile, extensions and dates; and a repeated create exited nonzero without changing
  either file.

## Resolution

- Finding dispositions: No required findings or questions. Accepted the optional record-only
  observation and corrected the handoff's password-alphabet count from 58 to 57. The
  implementation was already correct, so no code remediation was needed.
- Simplification/deletion pass: Preserved the direct argparse command, closed recovery model,
  on-demand key parsing and one shared CA-validity rule. The review found no unused compatibility
  path, duplicated state or speculative machinery to remove, and the documentation correction
  added none.
- Final verification: No implementation changed after the independent review passed the targeted
  commands, full Python suite (`904 passed`), real create and no-overwrite checks, mode checks and
  OpenSSL inspection recorded above. `git diff --check` passed after the documentation correction.

## Closure review

- Verdict: Accepted. The handoff now records the actual 57-character password alphabet. The
  resolution accurately states that the independent review found no required issue and that this
  documentation-only correction needed no implementation remediation. It introduces no
  release-blocking defect, and `git diff --check` passes.
- Remaining required findings: None.
- Accepted commit: `11fae1dc10680678987d1db6fbfed03b921e2b1e`
