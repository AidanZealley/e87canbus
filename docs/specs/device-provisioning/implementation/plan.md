# Device lifecycle tooling implementation plan

Status: implementation in progress.

## Orchestration record

- Integration branch: `feature/device-lifecycle-tooling`
- Starting commit: `7d7c2387c0d6b1135eeec842b08cc8ee9a827ef3`
- Orchestrator: Codex primary agent (`/root`)
- Review command: `claude -p "<prompt>" --model opus --effort medium --permission-mode plan`
- Review command validation: Passed on 2026-09-10 with Claude Code 2.1.263; exit 0 and no effort warning.
- Specification approved at commit: `622a9d6d62e98b84d4f25152bb5ee525486f98b7`
- Started: `2026-09-10`

## Workstream order

| # | Workstream | Depends on | Status | Accepted commit |
|---:|---|---|---|---|
| 1 | [CLI boundary and image build](01-cli-and-image-build.md) | Approved specs | Accepted | `3a1f0a2a0b65ae96b31d7be13281619408cbc7eb` |
| 2 | [Installation authority](02-installation-authority.md) | 1 accepted | Accepted | `11fae1dc10680678987d1db6fbfed03b921e2b1e` |
| 3 | [Provisioning artifacts](03-provisioning-artifacts.md) | 2 accepted | Accepted | `fff702367bed156640f52085d6cc5c48ba196815`; correction `924514ea061bb69a825efe19ebfec742c698bdf6` |
| 4 | [Safe macOS card provisioning](04-macos-provisioning.md) | 3 accepted | Accepted | `3d01f300aee37d9cf0b3818143877083522c4374` |
| 5 | [Authenticated transport](05-authenticated-transport.md) | 3 accepted | Accepted | `d896b526f66765219db2718bef81efb888f3f72e` |
| 6 | [Provisionable host images](06-provisionable-images.md) | 4 and 5 accepted | Accepted | `3bac67b68a265b10508effced7930ae6c82beef7` |
| 7 | [Verification and cutover](07-verification-and-cutover.md) | 6 accepted and macOS writer gate passed | Not started | — |

Use only `Not started`, `Implementing`, `Review`, `Remediation`, `Closure review` or `Accepted`.
Only one workstream may be active.

## Why these boundaries

Workstream 1 creates the workstation package and moves the already-proven image builder without
mixing in security decisions. Workstream 2 isolates the installation authority and secret-bearing
recovery package. Workstream 3 freezes both bundle contracts and the reproducible application
payload before any destructive writer or first-boot consumer depends on them.

Workstream 4 owns the macOS destructive boundary and complete offline `provision` operation.
Workstream 5 separately secures the existing HTTP and Socket.IO application surface. These two
streams are sequential because both consume the frozen artifact contract and the shared worktree
must remain reviewable, even though neither semantically depends on the other's implementation.

Workstream 6 composes the stable inputs into the images: first-boot state machine, unique host
identity, Wi-Fi, nginx, Chromium and role-service gates. Workstream 7 adds online verification and
puts the removal of the superseded Ethernet/setup path into the candidate that must pass on real
hardware.

## Cross-workstream contracts

- Public commands are exactly `e87ctl image build`, `installation create`, `provision` and
  `verify`, with the role forms in the approved specification.
- `e87ctl` is a top-level workstation-only package exposed by the root uv environment. It is not
  included in Pi application bundles.
- Recovery, image, application, provisioning and status documents use one strict v1 schema each.
  Unknown fields and incompatible roles or versions fail closed.
- Installation identity is derived from the P-256 CA public key. Device identity is the complete
  signed URI SAN defined by the specification.
- The application bundle is ready-to-run `linux-aarch64`; first boot performs no package or
  dependency installation and no frontend build.
- `e87canbus-provisioning-v1.zip` uses the exact entry names, bounded reads, digests and free-space
  reserves in the specification.
- `/opt/e87canbus/current` selects the installed release. `/etc/e87canbus` owns configuration and
  secrets. `/var/lib/e87canbus` owns mutable state.
- The coordinator is `10.42.0.1`, console is `10.42.0.2`, and DHCP is limited to
  `10.42.0.100-150` without DNS, gateway or forwarding.
- Nginx owns TLS client-certificate verification; FastAPI owns the explicit request-class
  authorization table. Chromium owns console client-certificate selection.
- `provision` proves only card preparation. `verify` proves online first-boot and application
  behavior. Both use versioned, secret-free structured output.
- Compromise recovery replaces the installation and reprovisions both Pis. Do not add rotation,
  revocation or hidden inventory.

## Ownership handoffs

- Workstream 1 owns package layout, CLI dispatch, root dependency wiring and the image command.
  Later streams extend subcommands without reintroducing a generic command framework.
- Workstream 2 owns identity and recovery-package types. Later streams consume them and return
  contract changes to that owner.
- Workstream 3 owns artifact schemas, builders and validators. Workstreams 4 and 6 consume the same
  validation code rather than duplicate it.
- Workstream 4 owns validated macOS disk values and the low-level writer. No later call site may
  pass an arbitrary device path around that boundary.
- Workstream 5 owns the executable authorization map and authenticated application identity.
  Workstreams 6 and 7 configure and verify it without duplicating permissions in nginx.
- Workstream 6 owns the on-device state machine, image contract and network/service composition.
  Workstream 7 may add diagnostics but must return behavior fixes to its owner.
- Focused test-file ownership may transfer sequentially. Generated API and live-contract artifacts
  must be regenerated in the workstream that changes their source.

## Whole-feature acceptance

- Every workstream is accepted from a clean sequential head.
- Both external gates are `Passed` against recorded candidate commits.
- Every acceptance criterion in the three product documents has an implementation owner and
  evidence or an explicit approved drift entry.
- Recovery packages, private keys, passwords, generated images and bundles are absent from Git and
  test output.
- Focused and repository-wide checks pass, including generated-contract checks.
- A fresh whole-feature reviewer finds no unresolved required issue.

## External validation gates

| Gate | Owner | Placement | Status | Candidate | Resume condition |
|---|---:|---|---|---|---|
| macOS writer | 4 | After workstream 6, before workstream 7 | Testing | `3bac67b68a265b10508effced7930ae6c82beef7` | macOS writer evidence recorded on the combined candidate |
| Provisioned pair | 7 | After closure | Pending | TBD | MacBook and two-Pi evidence recorded |

Gate status is one of `Pending`, `Testing`, `Troubleshooting` or `Passed`; it is separate from the
workstream status.

## Decision and drift log

| Date | Decision or drift | Reason | Approved by | Affected workstreams |
|---|---|---|---|---|
| 2026-09-10 | One workflow; Wi-Fi supports and images depend. | Shared contracts. | Aidan | 1-7 |
| 2026-09-10 | Use the one sufficient security path. | Avoid marginal machinery. | Aidan | 2-7 |
| 2026-09-10 | Reopen workstream 3 for the missing `car` or `bench` deployment-profile contract. | Workstream 4 found that the accepted strict device configuration could not carry an approved provisioning input. | Orchestrator | 3-4 |
| 2026-09-10 | Run independent reviews with Claude Code Opus at medium effort. | Aidan requested an explicit external reviewer after workstream 3; the validated command is read-only. | Aidan | 4-7 and whole-feature review |
| 2026-09-10 | The workstream 4 writer gate has no current producer for its strict compatible image. | The accepted builder emits the prototype manifest; workstream 6 owns the provisionable successor but depends on workstream 4 acceptance. The gate remains pending without weakening validation. | Orchestrator | 4 and 6 |
| 2026-09-10 | Move the macOS writer gate after workstream 6 and require it before workstream 7. | This keeps image validation truthful, accepts the independently reviewed writer without hardware overclaim and tests the combined writer/image candidate. | Aidan | 4, 6 and 7 |
| 2026-09-11 | Keep the Trixie iwd backend and require physical WPA3-SAE/PMF evidence. | Debian Trixie provides iwd 3.8, after upstream added SAE access-point support in 2.18. The reviewer claim that iwd cannot provide AP-SAE does not apply to the pinned distribution, while Pi radio compatibility still needs the existing hardware gate. | Orchestrator | 6-7 |
