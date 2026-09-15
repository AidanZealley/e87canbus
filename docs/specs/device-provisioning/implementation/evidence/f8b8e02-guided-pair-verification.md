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

## Image provenance

Both images were built from clean commit
`f8b8e02617375dff694c69976849a6eabe9fc804` with `git_dirty=false` and pinned builder revision
`262d4df5a9f9d4133370465399a7958a7c22cdc7`.

- Coordinator manifest:
  `artifacts/images/coordinator/e87-coordinator_2026-09-15_2208Z_f8b8e02.json`
- Coordinator image: `e87-coordinator_2026-09-15_2208Z_f8b8e02.img`, 6,450,839,552 bytes,
  SHA-256 `b208139ea16c1834ebf5298314764ed01c30440cbf9456dac4a0bceb506c9570`
- Console manifest: `artifacts/images/console/e87-console_2026-09-15_2216Z_f8b8e02.json`
- Console image: `e87-console_2026-09-15_2216Z_f8b8e02.img`, 6,450,839,552 bytes,
  SHA-256 `f7ad933c3a831128f7e15536feff7b9c8cf52cdfacc6135c3ab1e58004b46bd4`

The application and provisioning digests cannot be derived from these image manifests. Aidan
confirmed that all four values were present and matched during physical testing, but the literal
values were lost when the diagnostic sessions containing them were closed.

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

## Laptop DHCP boundary

The MacBook joined the coordinator network through `en0` and received `10.42.0.105` from
`10.42.0.1`. This is inside the required `10.42.0.100-150` client pool. Its DHCP ACK contained the
subnet mask and broadcast address but no router or domain-name-server option, so the isolated
network supplied neither a default route nor DNS.

## Gate disposition

This evidence accepts the guided command's real-device behavior and closes the previously measured
SSH scan, release bytecode and certificate-profile defects. Exact clean image provenance is now
recorded. Aidan confirmed that he completed the remaining workstream 7 and 8 checks during the
same evening's physical testing: both image checkers passed; identities were unique; provisioning
material was removed; only the intended services were exposed; the coordinator remained healthy
during console loss; failed commands did not replay; the console recovered; the panel remained
status-only at `READY` and its inputs did not change the network; and the disposable invalid-bundle
card remained unprovisioned, started no role service and reported `invalid_bundle` without a
secret. He also confirmed that the application and provisioning digests were present and matched
when tested, although their literal values were not retained.

The shared provisioned-pair gate is `Passed`. The retained clean image manifests, four-pass guided
report, DHCP result, earlier detailed physical reports and Aidan's final attestation form the gate
record.
