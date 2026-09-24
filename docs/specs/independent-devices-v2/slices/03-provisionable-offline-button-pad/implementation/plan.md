# Provisionable offline button pad implementation plan

Status: draft; implementation has not started.

## Orchestration record

- Integration branch: `TBD` (create from the approved Slice 02 HEAD)
- Starting commit: `TBD`
- Specification approved at commit: `TBD` (the workflow request approves the Slice 03 draft as the implementation source)
- Review command: `claude -p "<review brief>" --model claude-opus-5-5 --effort medium --permission-mode plan`
- Started: `TBD`

## Workstream order

| # | Workstream | Depends on | Status |
|---:|---|---|---|
| 1 | [Local firmware and CAN reception](01-local-firmware.md) | Accepted Slice 02 | Not started |
| 2 | [Build and verify firmware artifacts](02-firmware-artifacts.md) | 1 | Not started |
| 3 | [Provision and reflash the pad](03-provision-and-reflash.md) | 2 | Not started |
| Final | [Whole-feature review](final-review.md) | 1-3 | Not started |

The lead updates its row at each transition: `Not started`, `Implementing`, `Review`,
`Remediation`, `Closure review`, `Blocked`, or `Accepted`. Only one workstream is active.

## Why these boundaries

The firmware project owns its partition table, scene validation, local input and rendering, and
listen-only CAN behavior. Its hardware facts and bench behavior need physical evidence. The build
tool then consumes that project and owns the secret-free artifact contract. Provisioning consumes
the verified artifact and owns chip checks, credentials, identity image creation, and flash safety.
These outcomes can each be accepted without temporary compatibility code for a later workstream.

## Cross-workstream contracts

- The checked-in 8 MB partition table follows the [board reference](../../../../../weact-can485-esp32.md#internal-flash-layout); `e87id` and `e87cfg` are distinct NVS partitions.
- The firmware consumes the exact Slice 02 scene and configuration envelope. It validates a whole
  stored value before replacing the active scene, and keeps a compiled safe scene if none is valid.
- The build manifest lists every flash image with offset, byte length and SHA-256. Its identity
  partition offset and maximum size match the firmware partition table. A normal reflash omits
  `e87id` and `e87cfg`.
- Full provisioning creates one fresh P-256 device certificate from the installation recovery
  package. Its role is `button-pad` and its URI SAN uses the coordinator's accepted Slice 02
  parser. The identity image also holds Wi-Fi credentials, CA and issue-time clock floor; it does
  not hold an application scene.
- CAN is receive-only at 100 kbit/s on GPIO26/27. No received payload changes LEDs in this slice.
- Workstream 1 adds a pinned PlatformIO dependency to `e87ctl` and the required lockfiles.
  `uv run pio` is the build and native-test entry point for all later workstreams.

## Ownership handoffs

Workstream 1 owns `devices/button-pad/` and its README, including firmware, tests and partitions,
plus `e87ctl/pyproject.toml` and lockfiles for PlatformIO. Workstream 2 owns firmware build code,
manifest model and tests in `e87ctl/`, and may update firmware build configuration only to make its
PlatformIO invocation work. Workstream 3 owns provisioning code, CLI, tests and operator docs in
`e87ctl/`; it may fix manifest validation through the Workstream 2 owner with an explicit recorded
handoff. It confirms no obsolete AVR upload material remains and preserves coordinator-panel.

## Whole-feature acceptance

- The accepted Slice 02 coordinator contract remains intact; no project-device CAN protocol returns.
- A verified artifact can be built once and flashed repeatedly. Invalid manifest fields, digests,
  offsets, sizes, overlaps, chip or flash size stop before writing.
- Full provisioning creates a coordinator-accepted button-pad certificate, replaces identity and
  clears configuration. Ordinary reflash preserves both partitions.
- The physical pad starts locally without Wi-Fi, restores only complete valid scenes, flashes only
  assigned presses, receives injected standard CAN frames without LED effects, and transmits none.
- The button-pad README records measured board revision, NeoTrellis pin and button mapping,
  brightness limit, and bench wiring. No guessed measurement is accepted as evidence.
- Obsolete AVR upload material and source-only dependencies made useless by this replacement are
  gone. The coordinator-panel build and upload path remain.

## External validation gates

| Gate | Owner and placement | Status | Candidate and required evidence | Resume condition |
|---|---|---|---|---|
| H1 hardware facts | 1, before pin-dependent implementation | Pending | Assembled PCB revision, measured NeoTrellis I2C pins and logical-to-physical map, safe brightness measurement and bench wiring | User supplies measurements or an agent with the assembled hardware records them |
| H2 local bench behavior | 3, after closure and before acceptance | Pending | Firmware build flashed to the board; offline boot, valid/invalid scene power-cycle, assigned/unassigned feedback, 100 kbit/s standard-frame reception, no CAN transmission | Recorded bench observations pass; failures enter the gate troubleshooting loop |
| H3 flash behavior | 3, after closure and before acceptance | Pending | Manifest and images on the confirmed 8 MB board; repeated ordinary flash preserving `e87id`/`e87cfg`, full provision replacing identity and clearing config, read-back or equivalent evidence | Recorded flash observations pass; failures enter the gate troubleshooting loop |

The owner records candidate, instructions, evidence, and lasting decisions in its packet. A gate
needing the user's hardware or judgment yields an escalation and `Blocked` return. The fresh lead
resumes after the orchestrator records the user's answer. Diagnostic retries stay inside the gate;
reopen review only for a change to approved behavior, architecture, ownership, security, persistent
data, public contracts, or another accepted workstream.

## Escalations

Empty until a lead blocks. Each entry records the decision needed, options, recommendation,
evidence, what it unblocks, and the user's answer. The resuming lead moves lasting decisions to
its handoff and, when later workstreams depend on them, the log below, then removes the entry.

## Decision and drift log

| Date | Decision or drift | Reason | Approved by | Affected workstreams |
|---|---|---|---|---|
| 2026-09-24 | Use the Slice 03 draft as the implementation source | Aidan requested its workflow on the accepted Slice 02 branch | Aidan | All |
| 2026-09-24 | Specify `e87ctl firmware flash button-pad` for ordinary reflash | A verified, confirmed reflash must omit both persistent partitions; the product spec requires reflash behavior but does not name its operator command | Aidan | 3 |
