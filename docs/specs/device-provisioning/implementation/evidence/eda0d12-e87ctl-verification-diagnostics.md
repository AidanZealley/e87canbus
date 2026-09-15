# `eda0d12` e87ctl verification diagnostics

Date: 2026-09-15

## Physical result

Fresh coordinator and console images built from
`eda0d12cfb56a23ed71bd1a3e33eb40be229b75b` booted and provisioned successfully. With the console
Pi and display physically separated, the console associated immediately, remained at
`10.42.0.2`, and loaded settings through the coordinator's authenticated API. Both streamed
on-device image checkers passed completely. This confirms the software image and deployed
application path; display proximity remains a separate hardware/RF concern.

## Workstation verification result

The MacBook routed to `10.42.0.1` and `10.42.0.2` through the devices' Ethernet connections.
Direct authenticated SSH using the recovery key and recorded Ed25519 fingerprints succeeded to
both fixed addresses. Coordinator HTTPS identity, liveness, readiness, unauthenticated rejection
and operator access also passed. The unmodified `e87ctl verify` command could not complete its SSH
and console mutual-TLS evidence because of three defects:

1. macOS `ssh-keyscan` emitted a banner comment on stdout before its valid key record. The parser
   counted the comment as a second record and rejected the scan before attempting SSH.
2. Exactly 48 `cryptography/__pycache__/*.pyc` files differed from the application manifest. They
   were 15 bytes larger after the ready-to-run environment was relocated, consistent with an
   embedded source-path change. No application files were missing or added and no symlinks were
   present in the release.
3. The console NSS client certificate exported and parsed, but Python's first strict TLS handshake
   failed with `Missing Authority Key Identifier`. The broader console check group consequently
   reported its three mutual-TLS results as false.

The PKCS#12 BER fallback warning was observed but was not the immediate TLS failure.

## Device evidence

- Coordinator: `e87-coordinator-61f3fe49402f`, device
  `61f3fe49-402f-4b6a-88c9-aa4c60d73999`, SSH fingerprint
  `SHA256:HxFkqNtyrWaXcux7+gb1CZqdfN2fYPYQZLSYvYYGcOU`.
- Console: `e87-console-a6610795808e`, device
  `a6610795-808e-4781-a4d6-e8969fe5d4c4`, SSH fingerprint
  `SHA256:RKkcuIJs+geJwNrsvSCKoTTH4Hwp/M38P320Nc8Yhzk`.

## Accepted correction

Commit `f67e02e226491b7211c61ffd97bc73ce0c3a2792`:

- ignores only blank and comment lines from `ssh-keyscan` before retaining the exact one-record,
  Ed25519 and fingerprint checks;
- excludes Python bytecode from the application producer and rejects it at both archive and
  first-boot consumer boundaries, prevents deployed services and the privileged verifier from
  writing it, and keeps exact release hashing;
- adds a public-key-derived subject key identifier to the installation CA and subject/authority
  key identifiers to device certificates, with exact validators and a strict bounded mutual-TLS
  test against the production IP SAN.

Claude Code Opus at medium effort accepted the focused closure with no release-blocking finding.
Its run passed 995 Python tests, Ruff and mypy. The orchestrator separately passed 96 focused
tests, Ruff, mypy, provisioning-consumer compilation, application-builder shell syntax and
`git diff --check`.

## Retest requirement

The provisioned-pair gate returns to `Troubleshooting`. Build through the corrected application
builder, create a fresh installation and recovery package, build fresh role bundles and images,
and reprovision both cards. Earlier recovery packages lack the corrected certificate profile and
earlier application artifacts contain bytecode, so neither can validate this correction.

On the fresh candidate, run `e87ctl verify` at least twice and confirm that host-key pinning,
`application_release` and console mutual TLS all pass. The complete outstanding gate evidence must
also be recorded before the gate returns to `Passed`.
