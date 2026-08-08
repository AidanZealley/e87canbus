# Workstream 5: Pi provisioning and deployment documentation

Status: not started.

## Task packet

### Outcome

Extend fresh-Pi setup for the accepted physical runtime and document the complete deployment and
bench handoff. Setup must safely provision UART, the fixed hotspot, credentials, dependencies, and
service permissions without moving configuration responsibility into runtime code.

### Scope

- Extend `scripts/setup_pi.sh` for physical `car` and `bench` profiles only.
- Enable `/dev/serial0`, remove the serial console from it, and mark reboot required when boot files
  change.
- Grant the existing `e87canbus` account UART access.
- Install the minimal packages selected by the accepted production runtime.
- Create or reconcile `e87canbus-hotspot` without altering unrelated NetworkManager connections.
- Prompt twice and silently for the first WPA password; support `--hotspot-password-file` for
  unattended provisioning; preserve an existing password when none is supplied.
- Install the smallest practical permission rule that lets the unprivileged service operate the
  fixed connection.
- Ensure the hotspot does not autoconnect, starts disabled, and does not route internet from
  Ethernet.
- Update setup/wiring documentation with provisioning, firmware upload, harness, diode/fuse, and
  the remaining physical checks.

Start with a direct Polkit/system-permission approach. Add a fixed argument-validating privileged
helper only if target evidence shows the direct approach cannot work, and record that evidence and
orchestration approval before adding it.

### Non-goals

- A network administration CLI, runtime connection creation, or general sudo command access.
- Passwords in arguments, logs, repository files, or coordinator environment files.
- Maximum-client enforcement, client identity, internet sharing, or unrelated Wi-Fi changes.
- Claims that physical UART, LEDs, hotspot association, or cancellation were validated without the
  hardware evidence.
- Enclosure CAD, light-pipe design, ignition shutdown, or Pi hold-up power.

### Initial ownership

- `scripts/setup_pi.sh`.
- Required files beneath `deploy/` for the narrow permission/configuration mechanism.
- `docs/setup.md`, `docs/wiring.md`, and device/deployment documentation directly affected.
- Focused static/script tests if the repository has an appropriate existing pattern.
- This workstream record.

Substantive changes to the Python runtime or firmware return to their workstream owners. Small
configuration corrections may be made only after recording the handoff.

### Required seams

- Setup provisions exactly the names, commands, packages, serial path, and permission assumptions
  recorded by workstream 3.
- Firmware instructions use the accepted upload script and require the Pi harness to be unplugged.
- Simulator setup remains free of physical UART/hotspot changes and password prompts.

### Acceptance criteria

- Usage and validation clearly distinguish first setup, rerun, password-file automation, and
  simulator profile behaviour.
- Secret values are never passed on the command line or printed.
- Rerunning setup preserves the existing password unless replacement is explicitly requested.
- Boot-file changes use the script's existing reconciliation/backup/reboot conventions.
- The service account remains unprivileged and receives no general command authority.
- The fixed connection is disabled and non-autoconnecting after setup.
- Unrelated NetworkManager connections are untouched.
- Documentation matches the final runtime, firmware, wiring, and unresolved bench checks.

### Targeted verification

Run the repository's shell checks if present, plus non-destructive syntax/static validation:

```bash
bash -n scripts/setup_pi.sh scripts/coordinator_panel_upload.sh
```

Do not run `setup_pi.sh` against the development machine. Record which behaviours require a target
Pi and verify only through reviewed commands/tests until that hardware is available.

## Implementation handoff

- Base commit: `TBD`
- Outcome: `TBD`
- Files changed: `TBD`
- Provisioned connection and permission approach: `TBD`
- Secret-handling verification: `TBD`
- Verification: `TBD`
- Target-Pi checks still required: `TBD`
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
