# `f8b8e02` guided pair verification

Date: 2026-09-15

The guided `uv run e87ctl verify` command produced a valid
`PairVerificationReport` with `result=passed`, four completed passes and no incomplete reason.

## Installation and devices

- Installation: `vkowexhk2cqpvfl24amyy33mcjeybvbetjd63imjkjxr6gpgorka`
- Coordinator: `e87-coordinator-4421b15a4aec`, device
  `4421b15a-4aec-4889-896f-01e471a6e46d`
- Console: `e87-console-6cb75605d5e9`, device
  `6cb75605-d5e9-4f9a-9ce2-087bfd41905e`

## Results

| Pass | Role | Time | Checks | Result |
|---:|---|---:|---:|---|
| 1 | Coordinator | 3.952 seconds | 14 of 14 passed | Passed |
| 1 | Console | 9.981 seconds | 17 of 17 passed | Passed |
| 2 | Coordinator | 3.821 seconds | 14 of 14 passed | Passed |
| 2 | Console | 8.634 seconds | 17 of 17 passed | Passed |

Both repeated `application_release` checks passed, which proves the corrected verifier did not
mutate either release tree between passes. Authenticated SSH, bundle consumption, provisioning,
device and host identity, role services, SSH policy and Wi-Fi passed on both devices. Coordinator
HTTPS identity, liveness, readiness, unauthenticated denial and operator access passed. Console
HTTP mTLS, Socket.IO mTLS and operator rejection passed twice.

The attached report validated against the implementation's strict `PairVerificationReport` model.
Its schema contains only installation and device identities, hostnames, check outcomes, details and
timings. It contains no recovery-package secrets.

## Gate disposition

This evidence accepts the guided command's real-device behavior and closes the previously measured
SSH scan, release bytecode and certificate-profile defects. It does not name the exact image build
commit, manifests or artifact digests and does not include every remaining workstream 7 and 8
physical check. The shared provisioned-pair gate therefore remains `Troubleshooting` until that
evidence is supplied or an explicit limitation is approved.
