# Workstream 3: provision and reflash the pad

Status: not started.

## Task packet

### Outcome

`uv run e87ctl provision button-pad --firmware <manifest> --port <serial>` verifies the artifact
and attached board, then performs one confirmed full provisioning operation. A separate
`uv run e87ctl firmware flash button-pad --firmware <manifest> --port <serial>` performs an
ordinary reflash that preserves identity and configuration.

### Scope

- Add the button-pad certificate role to `e87ctl`'s small target and role table. Read the
  installation recovery package through the existing validated path.
- Generate a fresh device UUID, P-256 key and client certificate with the Slice 02 canonical
  `button-pad` role and URI SAN. Create the versioned `e87id` NVS image containing Wi-Fi
  credentials, installation CA, key, certificate and initial TLS clock floor. Do not duplicate
  role or ID outside the certificate. Verify coordinator parser acceptance in an integration test.
- Confirm the serial port, chip and 8 MB flash, revalidate manifest and images, and display the
  microSD removal warning before invoking `esptool`. Show the operation and require explicit
  operator confirmation. Full provisioning writes all images and replaces `e87id` while clearing
  `e87cfg`; ordinary reflash writes neither partition.
- Read the installation recovery package through `--installation` or the existing
  `E87CTL_INSTALLATION` setting. The public provisioning command keeps the specified short form
  when that setting is configured.
- Remove the obsolete AVR button-pad source/upload path and source-only dependencies made useless
  by the replacement if any remain; record the search evidence. Update operator documentation;
  retain coordinator-panel behavior.
- Own H2 bench validation now that the manifest and flash tooling exist. Provide a small, documented
  test fixture that writes valid and invalid `e87cfg` NVS values; keep it outside production
  firmware. Remove microSD before any flash. Check CAN termination with a resistance measurement
  before attaching to a terminated bus, and use an active acknowledging CAN node alongside the
  injector and listen-only pad.

### Non-goals

Wi-Fi joining firmware, TLS firmware, remote update, inventory, certificate rotation, or a
second device target implementation.

### Initial ownership

`e87ctl/src/e87ctl/`, `e87ctl/tests/`, its dependency files, `devices/README.md`, relevant
provisioning docs, and any obsolete AVR material still present. Changes to Workstream 2 manifest
code require an explicit owner handoff recorded in this packet. Do not alter `hosts/` except a
test that verifies coordinator parser acceptance.

### Required seams

Use the accepted Workstream 2 manifest validator and Workstream 1 partition table. Certificate
parsing must match `hosts/src/e87canbus/api/auth.py`. Use the existing recovery package rather
than a new installation store. Preserve the full-provision versus reflash distinction.

### Acceptance criteria

- An artifact built once can be validated and flashed more than once.
- Manifest and attached-board mismatches fail before writing.
- Full provision creates a parser-accepted certificate, replaces identity and clears config.
- Ordinary reflash preserves both `e87id` and `e87cfg`; confirmation clearly names the mode.
- The microSD warning precedes the flash call; declined confirmation writes nothing.
- No obsolete button-pad AVR upload or source-only dependency remains; coordinator-panel still works.
- H2 physically proves offline boot, scene restore/rejection, press feedback, CAN reception and
  no CAN transmission using the reviewed firmware.

### Targeted verification

Run `uv run pytest -q e87ctl/tests` and the focused coordinator authentication integration test
added here, `uv run ruff check e87ctl hosts/tests`, and `uv run mypy`. Use a fake serial/esptool
boundary to prove no-write rejection and exact flash offsets. The lead records H3 physical read-back
evidence separately.

### External validation

- Gate and placement: H2 and H3 after closure, before acceptance.
- Status: Pending.
- Candidate and instructions: use one accepted manifest and the confirmed 8 MB board with microSD
  removed. For H2 use the bench fixture to write valid and invalid `e87cfg` values, power-cycle
  offline, press assigned and unassigned keys, and inject standard 100 kbit/s frames with an
  active acknowledging node. Check termination resistance before bus connection and observe pad
  transmit with a separate interface. For H3 reflash twice, compare identity and configuration
  partitions before and after, then full-provision and compare again; confirm the new certificate
  parses at the coordinator.
- Required evidence: H2 boot, scene, press, received-frame and no-transmit observations; H3
  detected chip and flash size, image offsets, partition read-back or hashes, fresh identity,
  empty config, and operator confirmation result.
- Attempts and lasting decisions: `TBD`
- Resume condition: H2 and H3 physical observations pass; otherwise use README gate retry rules.

## Implementation handoff

- Base commit: `TBD`
- Outcome: `TBD`
- Files changed: `TBD`
- Decisions: `TBD`
- Verification: `TBD`
- Known limitations or external checks: `TBD`
- Specification drift: `TBD`

## Independent review

- Reviewer: `TBD`
- Verdict: `TBD`
- Required findings: `TBD`
- Optional observations: `TBD`
- Questions: `TBD`

## Resolution

- Finding dispositions: `TBD`
- Simplification/deletion pass: `TBD`
- Final verification: `TBD`

## Closure review

- Verdict: `TBD`
- Remaining required findings: `TBD`
