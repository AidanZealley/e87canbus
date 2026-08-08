# Workstream 5: Pi provisioning and deployment documentation

Status: accepted.

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

- Base commit: `4250a8443fb1b8f0b2e21dc536150a88db178f3c`
- Outcome: Extended the existing Pi reconciliation for the physical `car` and `bench` profiles
  with `/dev/serial0`, fixed hotspot provisioning, service-account access, and the complete firmware,
  harness, wiring, and bench handoff. The simulator path does not read credentials or change UART,
  NetworkManager, or panel permissions. The workstream 3 owner correction routes all four production
  NetworkManager/station operations through the accepted fixed helper contract.
- Files changed: `coordinator/src/e87canbus/adapters/networkmanager_hotspot.py`,
  `coordinator/tests/test_networkmanager_hotspot.py`, `scripts/setup_pi.sh`,
  `deploy/bin/e87canbus-hotspot`,
  `deploy/sudoers/e87canbus-hotspot`, `deploy/systemd/e87canbus-controller.service`,
  `coordinator/tests/test_reliability.py`, `deploy/README.md`, `docs/setup.md`, `docs/wiring.md`, and
  the implementation plan and this record.
- Provisioned connection and permission approach: Setup adds NetworkManager and `iw`, enables UART,
  removes the serial console with the existing backup/reboot pattern, and adds `e87canbus` to
  `dialout`. It creates or reconciles only `e87canbus-hotspot`, binds it to built-in `wlan0`, disables
  autoconnect and IPv6, and leaves it down. NetworkManager shared addressing supplies the client DHCP
  service; a priority-100 `wlan0` input rule and blackhole default in table 500 prevent forwarding
  client traffic through Ethernet. Installed NetworkManager evidence showed that the initially
  attempted user ACL requires a logged-in session, while username-wide Polkit network-control would
  reach unrelated profiles. The approved replacement installs one root-owned helper plus exact
  sudoers entries for only `activate`, `deactivate`, `state`, and `stations`. The helper accepts
  exactly one action and hard-codes `/usr/bin/nmcli`, `/usr/sbin/iw`, `e87canbus-hotspot`, and `wlan0`;
  there is no arbitrary argument, environment, connection editing, unrelated networking operation,
  daemon, or general sudo command. The controller unit's `NoNewPrivileges` setting is necessarily
  disabled because Linux otherwise blocks the sudo setuid transition; the exact sudoers allowlist
  remains the privilege boundary and the unit retains its other hardening.
- Secret-handling verification: First provisioning prompts twice with `read -s`; an explicitly
  supplied password file is the only unattended/replacement path, and an ordinary rerun tests for
  an existing stored PSK without printing it. Input accepts NetworkManager's 8-63 character form or
  64 hexadecimal form. The PSK is fed to the NetworkManager editor over stdin with stdout discarded
  and its command-history cache disabled; it is not placed in argv, exported environment, service
  environment, logs, or repository files. The shell value is cleared immediately after saving.
- Verification: Initial focused NetworkManager/profile tests passed (15 tests). Final remediation
  verification is recorded in `Resolution` below. Setup itself was not run on the development
  machine.
- Target-Pi checks still required: Confirm the target NetworkManager version accepts and installs
  the route type/routing rule; validate the installed helper ownership/mode and four-entry sudo
  listing; run each action from the nologin service unit; confirm the hotspot remains down across
  boot, association receives an address, Ethernet forwarding is blocked, activation cancellation
  and disable disconnect work, and the original password survives a no-password rerun. All assembled
  panel checks remain pending: firmware upload/bootloader recovery with the Pi harness disconnected,
  fused/diode-protected power, UART and heartbeat, pixels/brightness, debounce, timeout recovery,
  graceful off, and the complete button-to-hotspot-to-display path.
- Specification drift: `None`.

## Independent review

- Reviewer: `Codex /root/ws5_review`
- Verdict: `Changes required`
- Required findings:
  - The proposed NetworkManager authorization cannot both operate from the deployed service and
    preserve unrelated connections. Setup gives the hotspot `connection.permissions
    user:e87canbus`, but NetworkManager's installed `nm-settings-nmcli(5)` documentation states
    that a connection with a non-empty permissions list can be active only while one of those users
    is logged into an active session. The accepted system unit instead runs the system account with
    `/usr/sbin/nologin`, so its `nmcli connection up` cannot activate this profile merely because
    Polkit returned `YES`. Removing that ACL would expose the other half of the defect: the rule
    grants `org.freedesktop.NetworkManager.network-control` to every process owned by `e87canbus`,
    while NetworkManager documents that profiles with an empty permissions list are accessible to
    all users. The service could then control unrelated ordinary system connections, and the Polkit
    rule contains no connection identity check. This violates both the required practical runtime
    permission and the fixed-connection-only authority boundary. Record the direct-approach failure
    evidence and orchestration approval required by the task packet, then replace this with the
    smallest mechanism whose effective privileged operations validate the fixed connection and
    exact activation/deactivation commands; return any runtime command correction to the accepted
    workstream 3 owner.
- Optional observations: `None`.
- Questions for orchestrator:
  - Which Raspberry Pi model is the approved coordinator? The deployment guide currently permits
    any Pi with a 40-pin header, but Raspberry Pi's current UART documentation says that on Pi 5
    `/dev/serial0` is UART10 on the dedicated debug header, not BCM14/15 on pins 8/10. The setup's
    `enable_uart=1`, runtime's fixed `/dev/serial0`, and documented BCM14/15 harness therefore do not
    describe one transport on Pi 5. If Pi 5 is out of scope, pin the supported pre-Pi-5 model in the
    deployment documentation; if it is in scope, the orchestrator must resolve the cross-workstream
    UART path/configuration contract before this workstream can be accepted.

## Resolution

- Finding dispositions: Accepted the authorization defect. Installed NetworkManager documentation
  shows a connection `user:` ACL requires an active login session, which the nologin service account
  does not have; removing it would make username-wide Polkit authority too broad. This satisfies the
  specification's evidence gate for a fixed argument-validating helper, approved here with exact
  operation-only sudo permission. Resolved the UART question by pinning Raspberry Pi 4, matching the
  approved `/dev/serial0` on BCM14/15 contract and existing repository hardware direction; Pi 5
  model-specific UART support remains outside this fixed implementation.
- Simplification/deletion pass: Removed the ineffective connection ACL and broad Polkit rule rather
  than layering the helper over them. The replacement has one executable, one required argument,
  four closed actions, four exact sudoers command entries, and fixed absolute underlying commands.
  Setup validates and installs those two files directly; no wrapper hierarchy, configurable command,
  profile name, interface, wildcard permission, daemon, or runtime editing path remains. Deployment
  guidance now names Raspberry Pi 4 Model B wherever fresh hardware or the panel harness is selected,
  and setup fails fast on another model before physical-profile changes. `NoNewPrivileges=false` is
  the one necessary unit change: keeping it true would make the approved helper impossible to call,
  and broader ambient capabilities or a privileged service would expose more authority and machinery.
- Final verification: Focused NetworkManager, deployment-profile, physical composition,
  systemd/setup, and helper tests (24 passed); coordinator Ruff (passed); coordinator mypy (123
  source files passed); both import contracts kept; Bash syntax checks on setup, upload, and helper
  scripts (passed); `visudo -cf` on the repository sudoers file (parsed OK); helper calls with no
  arguments, an unknown action, and extra arguments each exited 2 without reaching an underlying
  command; the complete non-secret hotspot settings parsed with local NetworkManager 1.46.0 in
  offline mode; `git diff --check` (passed). `shellcheck` was unavailable. The production adapter
  now invokes the helper through `/usr/bin/sudo -n`, using
  `/usr/local/libexec/e87canbus-hotspot ACTION`, where `ACTION` is `activate`, `deactivate`, `state`,
  or `stations`; stdout and exit behavior pass through unchanged.

## Closure review

- Verdict: `Accepted`
- Remaining required findings: `None`. The ineffective active-session ACL and username-wide
  Polkit grant are gone. The replacement root-owned helper rejects every invocation except one
  exact action and hard-codes the fixed connection, interface, and absolute `nmcli`/`iw` commands;
  sudoers parses successfully and grants the service account only the four corresponding literal
  helper invocations. The production adapter uses only `/usr/bin/sudo -n` plus that fixed helper and
  action vocabulary, while the systemd unit permits the required setuid transition without removing
  its remaining filesystem/process hardening. Setup validates and installs the helper and sudoers
  files idempotently, retains the existing secret-preservation/editor path, and leaves the simulator
  outside physical provisioning and runtime composition. Physical setup now fails before mutation
  unless `/proc/device-tree/model` identifies a Raspberry Pi 4 Model B, and deployment, setup, and
  wiring documentation consistently bind `/dev/serial0` to the approved BCM14/15 Pi 4 harness rather
  than implying Pi 5 support. Focused helper rejection, sudoers, Bash, NetworkManager/profile,
  deployment, reliability, Ruff, mypy, and diff checks pass (24 focused tests); target-Pi and
  assembled-hardware checks remain explicitly pending.
- Accepted commit: `90df837d4177f76c34ca552c23f4cd020af13e48`
