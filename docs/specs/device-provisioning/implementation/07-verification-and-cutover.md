# Workstream 7: Verify the complete pair and cut over to provisioning

Status: closure review.

## Task packet

### Outcome

`e87ctl verify coordinator|console` reports the complete installed and online state, a newly built
and provisioned physical pair passes acceptance, and repository documentation exposes provisioning
as the sole coordinator-console setup path.

### Scope

- Implement versioned human and `--json` verification results with `passed`, `failed` and
  `unavailable` checks.
- Read the boot status offline and use trusted HTTPS plus key-only SSH for online checks as
  specified.
- Verify identity, bundle consumption, release, role services, Wi-Fi, mTLS, HTTP/Socket.IO
  authorization and operator-only rejection.
- Create exact checkpoint instructions and record MacBook, image, card and two-Pi evidence.
- Exercise one deliberately invalid bundle and confirm safe boot-partition failure reporting.
- Remove the superseded Ethernet runtime proxies and manual setup path from the hardware candidate.
- Update setup, deployment and image documentation, and add ADRs that supersede the named network
  decisions without rewriting accepted history.
- Run the final deletion and simplification pass across the assembled feature.

### Non-goals

- Routine deploy, rollback, repair, telemetry, rotation or additional device roles.
- Treating an offline/unavailable target as verified.
- Keeping compatibility aliases or Ethernet fallback after the accepted cutover.

### Initial ownership

- Verification and diagnostic modules plus tests under `e87ctl/`
- `docs/setup.md`, `deploy/README.md`, `images/README.md`, root `README.md` where relevant
- New superseding ADRs under `docs/decisions/`
- Obsolete Ethernet proxies and manual setup assets in the external-gate candidate
- Small cross-layer corrections only through the orchestrator and original owning workstream

### Required seams

- Compare complete installation and device identities, not display prefixes.
- Reuse the public CA and management key in the recovery package without logging secrets.
- Treat preparation and online verification as separate result contracts.
- Preserve coordinator operation during console/Wi-Fi loss and prove no queued command replay.

### Acceptance criteria

- `verify` exits nonzero when a required check fails or is unavailable and never overclaims success.
- Human and JSON output cover the same versioned checks without secrets.
- A fresh physical pair passes every device-lifecycle and Wi-Fi acceptance criterion.
- The invalid-bundle card remains unprovisioned and exposes a useful bounded safe error on boot.
- The built image and application manifests, digests and candidate commit are recorded.
- Old coordinator-console Ethernet transport, proxies and setup instructions are absent after the
  replacement path passes.
- Documentation teaches the complete bare-card-to-connected-pair flow and compromise replacement.
- Repository-wide verification and final secret/artifact audits pass.

### Targeted verification

```bash
uv run pytest -q
uv run mypy
uv run ruff check e87ctl hosts scripts/watch_frontend_contracts.py
uv run lint-imports
uv run python scripts/generate_custom_protocol.py --check
cd frontend && pnpm api:check && pnpm lint && pnpm typecheck && pnpm test && pnpm build
bash -n e87ctl/scripts/build-pi-image deploy/bin/e87canbus-firewall \
  deploy/bin/e87canbus-hotspot deploy/kiosk/*.sh
python3 -m py_compile deploy/bin/e87canbus-provision
bash -n images/*/customize.sh images/e87canbus-image-check
git diff --check
```

Adjust the shell glob only when an intentionally removed path no longer exists. Record rather than
hide any check unavailable on the implementation host.

## External validation

- Gate and placement: complete provisioned pair, after automated closure and before acceptance.
- Status: `Pending`
- Candidate: set after automated closure. Test the exact clean accepted candidate, not a later
  bookkeeping commit.
- Required evidence: candidate hash and clean/dirty build context; both image and application
  manifests/digests; MacBook builds; two safe SD writes/readbacks; coordinator and console first
  boot; unique hostname/machine ID/SSH keys; ZIP and staged-secret removal; marker transition;
  service health; exact IP/DHCP/no-forwarding behavior; WPA3-SAE and PMF; certificate trust and
  automatic console mTLS; HTTP and Socket.IO allowlists; laptop Wi-Fi-only denial; operator access;
  console rejection on operator status; Ethernet-disconnected operation; console disconnect/no
  replay/recovery; locally trusted SSH host-key fingerprints; authenticated SSH-only service
  exception; verification wall-clock times; and invalid-bundle boot and local-host state.
- Attempts and lasting decisions: `TBD`
- Resume condition: all required evidence passes on one recorded candidate. A WPA3/PMF failure may
  resume only after the single evidence-backed fallback allowed by the specification is approved
  and recorded as drift.

### Candidate procedure

Use an M-series MacBook with Docker Desktop, the two target Pi 4s, two blank cards and a separate
disposable card. Keep Ethernet disconnected for the whole successful-pair test. Set
`E87_RECOVERY` to a protected path outside the checkout.

1. Check out the exact candidate supplied by the orchestrator and record the clean build context:

   ```bash
   git rev-parse HEAD
   git status --short
   sw_vers
   uname -m
   uv sync --locked
   ```

2. Set `E87_RECOVERY` to a path that does not exist, create one recovery package, then build both
   images. Record the complete image manifest paths and their SHA-256 digests from the command
   output.

   ```bash
   uv run e87ctl installation create --output "$E87_RECOVERY"
   uv run e87ctl image build coordinator
   uv run e87ctl image build console
   ```

3. Provision the successful cards interactively. Use the same `car` or `bench` profile for both.
   Record each image, application and provisioning digest plus the assigned hostname and complete
   device ID. The two zero exits are the writer/readback evidence.

   ```bash
   uv run e87ctl provision coordinator --installation "$E87_RECOVERY"
   uv run e87ctl provision console --installation "$E87_RECOVERY"
   ```

4. Before first boot, add the temporary checker and local debug-shell input described in
   [the image runbook](../../../../images/README.md#physical-checkpoint). Boot the coordinator, then
   the console. Run the checker for each role and retain its output. On each local debug shell, run
   `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub -E sha256`. Record each complete `SHA256:`
   fingerprint and which physical role supplied it. Remove both temporary inputs from both
   successful cards before calling the gate passed.

5. Join the installation Wi-Fi from the MacBook. Run both verification commands in human and JSON
   forms and retain all four secret-free results:

   ```bash
   E87_COORDINATOR_SSH_FINGERPRINT='SHA256:<recorded-coordinator-fingerprint>'
   E87_CONSOLE_SSH_FINGERPRINT='SHA256:<recorded-console-fingerprint>'
   time uv run e87ctl verify coordinator --installation "$E87_RECOVERY" \
     --host-key-fingerprint "$E87_COORDINATOR_SSH_FINGERPRINT"
   time uv run e87ctl verify coordinator --installation "$E87_RECOVERY" \
     --host-key-fingerprint "$E87_COORDINATOR_SSH_FINGERPRINT" --json
   time uv run e87ctl verify console --installation "$E87_RECOVERY" \
     --host-key-fingerprint "$E87_CONSOLE_SSH_FINGERPRINT"
   time uv run e87ctl verify console --installation "$E87_RECOVERY" \
     --host-key-fingerprint "$E87_CONSOLE_SSH_FINGERPRINT" --json
   ```

   Record each elapsed wall-clock time without introducing a performance threshold. Every check
   must say `passed`. The commands scan the fixed role address, require the scanned Ed25519 host
   key to match the locally recorded fingerprint, pin it in a temporary `known_hosts`, then use
   strict host-key checking. They cover the strict root status, complete installation
   and device identities, consumed ZIP and staged-secret cleanup, release manifest and installed
   file digests, hostname and generated host identity, active role services, WPA3/PMF profiles,
   disabled forwarding, loaded firewall and dnsmasq policy, key-only SSH, trusted coordinator TLS,
   authenticated coordinator readiness, unauthenticated denial, operator status access, console
   HTTP and Socket.IO mTLS, and console rejection by the operator-only status endpoint.

6. Import the public CA sidecar on the service laptop and open `https://10.42.0.1`. Record that
   Chromium on the console loads the coordinator-backed UI without a certificate chooser or login
   prompt. From the laptop, record a `200` for liveness, a `401` for readiness without credentials,
   and a successful prompted operator request:

   ```bash
   curl --cacert "${E87_RECOVERY%.json}-ca.pem" -o /dev/null -w '%{http_code}\n' \
     https://10.42.0.1/health/live
   curl --cacert "${E87_RECOVERY%.json}-ca.pem" -o /dev/null -w '%{http_code}\n' \
     https://10.42.0.1/health/ready
   curl --cacert "${E87_RECOVERY%.json}-ca.pem" --user operator \
     https://10.42.0.1/api/system/provisioning
   ```

   Supply the operator password only at curl's prompt. Exercise the shipped console UI's current
   reads and one reversible write on the isolated bench. The existing generated-contract tests
   remain the exhaustive allowlist evidence.

7. Record that the MacBook receives an address in `10.42.0.100-150` and receives neither a router
   nor DNS option from this network. Use `networksetup -listallhardwareports` to find the Wi-Fi
   device, then record `ipconfig getpacket <device>`. On the two local debug shells, record these
   non-secret checks:

   ```bash
   nmcli -g GENERAL.STATE,802-11-wireless-security.key-mgmt,802-11-wireless-security.pmf,ipv4.addresses,ipv4.gateway,ipv4.dns connection show e87canbus-coordinator-wifi
   nmcli -g GENERAL.STATE,802-11-wireless-security.key-mgmt,802-11-wireless-security.pmf,ipv4.addresses,ipv4.gateway,ipv4.dns connection show e87canbus-console-wifi
   sysctl net.ipv4.ip_forward net.ipv6.conf.all.forwarding
   sudo nft list table inet e87canbus
   sudo dnsmasq --test --conf-file=/etc/e87canbus/dnsmasq.conf
   sudo ss -H -lntup
   ```

   Run the role-specific `nmcli` command on its matching Pi. The successful active profiles,
   `key-mgmt=sae`, `pmf=3` and actual association provide the WPA3-SAE and required-PMF evidence.
   Confirm no hotspot-reachable listener exists outside DHCP, HTTPS and SSH.

8. Prove the failure boundary. Power off or disconnect the console, confirm the coordinator stays
   ready, and attempt one reversible console command while disconnected. Confirm it fails at once,
   does not change coordinator state after reconnection, and a fresh complete snapshot restores
   the console display. Keep Ethernet disconnected throughout.

9. Compare the two successful results and checker output. Run the following on each local debug
   shell and record the output:

   ```bash
   hostname
   cat /etc/machine-id
   ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
   test ! -e /boot/firmware/e87canbus-provisioning-v1.zip
   test ! -e /var/lib/e87canbus-provisioning/staging
   test ! -e /var/lib/e87canbus-provisioning/unprovisioned
   ```

   Hostnames, complete device IDs, machine IDs and SSH host-key fingerprints must differ. Both
   statuses must contain the expected complete installation ID and their recorded application and
   provisioning digests.

10. Provision the disposable card for either role and add the test-only local debug shell through
    the guarded image-runbook procedure. Before boot, set `E87_INVALID_DISK` to its confirmed
    whole-disk identifier, then corrupt only its provisioning ZIP with this fail-fast chain:

    ```bash
    (
      set -euo pipefail
      E87_INVALID_DISK_ID=${E87_INVALID_DISK#/dev/}
      [[ "$E87_INVALID_DISK_ID" =~ ^disk[0-9]+$ ]]
      E87_INVALID_PARTITION="/dev/${E87_INVALID_DISK_ID}s1"
      diskutil info -plist "/dev/$E87_INVALID_DISK_ID" |
        plutil -extract Whole raw - | grep -qx true
      diskutil info -plist "$E87_INVALID_PARTITION" |
        plutil -extract ParentWholeDisk raw - | grep -qx "$E87_INVALID_DISK_ID"
      diskutil info -plist "$E87_INVALID_PARTITION" |
        plutil -extract VolumeName raw - | grep -qx BOOT
      trap 'diskutil unmountDisk "/dev/$E87_INVALID_DISK_ID" >/dev/null 2>&1 || true' EXIT
      diskutil mount "$E87_INVALID_PARTITION"
      diskutil info -plist "$E87_INVALID_PARTITION" |
        plutil -extract MountPoint raw - | grep -qx /Volumes/BOOT
      printf 'invalid provisioning fixture\n' > /Volumes/BOOT/e87canbus-provisioning-v1.zip
      sync
      diskutil unmountDisk "/dev/$E87_INVALID_DISK_ID"
      trap - EXIT
    )
    ```

    Set `E87_INVALID_ROLE` to the card's role and boot it once. On its local debug shell, record this
    proof that the failed consumer kept the root marker and never started the role target or main
    role service:

    ```bash
    test -e /var/lib/e87canbus-provisioning/unprovisioned
    test "$(systemctl show -p ActiveEnterTimestampMonotonic --value e87canbus-role.target)" = 0
    case "$E87_INVALID_ROLE" in
      coordinator) E87_INVALID_SERVICE=e87canbus-controller.service ;;
      console) E87_INVALID_SERVICE=e87canbus-console.service ;;
      *) exit 2 ;;
    esac
    test "$(systemctl show -p ActiveEnterTimestampMonotonic --value "$E87_INVALID_SERVICE")" = 0
    ```

    Remove the temporary debug-shell input, power the Pi down and return the card to the MacBook.
    Mount only `BOOT` and record the bounded status with:

    ```bash
    uv run e87ctl verify coordinator --installation "$E87_RECOVERY" \
      --status /Volumes/BOOT/e87canbus-status-v1.json --json
    ```

    Use `console` if that is the disposable card's role. The result must be nonzero, report the
    safe `invalid_bundle` error, keep online verification unavailable and contain no secret. The
    disposable Pi must retain `unprovisioned` and start no role service. Reprovision the card before
    any later use.

## Implementation handoff

- Base commit: `d5d0ff3ffc30d84cb43d1748f38ed526c6e40657`
- Outcome: Added `e87ctl verify coordinator|console` as the strict boundary between offline
  first-boot diagnosis and online device acceptance. The online command checks the installed host
  over key-only SSH and the coordinator over trusted HTTPS, including console mTLS. The cutover
  removes the checkout-based Pi installers and both plain-HTTP proxy pairs, and repository guidance
  now teaches provisioning as the only blank-card path.
- Files changed: Added `e87ctl/src/e87ctl/verify.py`, its focused test module and ADR 0013. Extended
  the CLI. Replaced the deployment and setup guidance, updated the root, image, wiring, Waveshare,
  capture-helper and project-context references, and indexed the superseding ADR. Removed
  `scripts/setup_{coordinator,console,host_common}.sh` and the coordinator's Ethernet and legacy
  hotspot HTTP proxy socket/service pairs. Updated deployment tests that had specified the deleted
  setup path.
- Decisions: `--status` reads one strict bounded boot status and always leaves online verification
  unavailable. Without it, verification uses the recovery package's management key from a
  mode-`0600` temporary file. Online verification scans the selected fixed role address, requires
  the Ed25519 host key to match an explicit locally trusted SHA-256 fingerprint, pins that key in a
  temporary `known_hosts`, and runs one strict bounded SSH invocation. Remote stdout goes to a
  temporary file and is read with a fixed cap. Remote evidence must contain the exact role-specific
  boolean check set. Complete installation and device IDs bind root status, installed device
  configuration, the coordinator server certificate and the console certificate exported
  temporarily from its NSS database. Installation-CA HTTPS proves authenticated readiness as well
  as liveness and authorization policy. The release check validates the closed installed manifest
  and every recorded file digest. No private key, operator password or Wi-Fi password enters
  process arguments, output or the remote verifier. The result is one strict versioned model
  shared by human and JSON output; any failed or unavailable required check makes the command and
  result fail. The established panel hotspot control remains: NetworkManager autoconnect meets
  automatic startup, deliberate Wi-Fi removal is an approved failure mode, and removing the
  control would change accepted runtime and simulator behavior outside this workstream.
- Simplification pass: Reused the existing recovery-package and boot-status contracts, one remote
  verifier invocation and one result model. Removed the obsolete installers, HTTP proxies and
  their implementation-coupled tests. Added no compatibility alias, Ethernet fallback, persistent
  inventory or speculative extension point.
- Verification: `uv run pytest -q` passed (`985 passed`). `uv run mypy` passed over 144 source
  files. Ruff, import contracts and the generated custom protocol check passed. Frontend API,
  lint, typecheck, tests and production builds passed (`18` coordinator-client, `101` console and
  `89` coordinator tests). Shell syntax passed for the image builder, shell deployment helpers,
  kiosk and image hooks; the Python provisioning consumer compiled; and `git diff --check` passed.
  The focused verify suite passed `17` tests.
- Candidate and external instructions: The exact candidate commit is assigned after closure. Run
  the complete `Candidate procedure` above on that clean commit and attach its manifests, digests,
  command results and physical observations to this record. No Docker, macOS, radio, Pi boot,
  Chromium or physical two-device check ran on this implementation host.
- Specification drift: None. ADR 0013 records the approved Wi-Fi and provisioning decisions while
  preserving the superseded ADRs as history. The cockpit remains deferred with no replacement
  transport selected here.

## Independent review

- Reviewer: Claude Code Opus at medium effort through the configured read-only review command.
- Verdict: Changes required.
- Required findings:
  1. The invalid-bundle procedure proved only BOOT status. It did not inspect the running card's
     root marker or prove that the role target and service never started.
  2. The image runbook's manual BOOT edit used separate commands. A failed disk-label check did not
     stop a later pasted command from mutating `/Volumes/BOOT` on another card.
  3. `docs/reliability.md`, `docs/waveshare-three-channel-stack.md` and `docs/wiring.md` retained
     manual-setup or Ethernet claims, and the reliability document linked to a deleted heading.
  4. SSH accepted a newly observed server key, so possession of the management private key did not
     authenticate the device reached at the fixed address.
  5. SSH captured remote stdout without a size bound.
- Optional observations: Require a trusted authenticated `200` from coordinator readiness; record
  physical verification wall-clock time without setting a threshold; reuse the console check-name
  constant; give malformed SSH evidence an accurate diagnostic; and remove source-string or
  deletion-regression tests that do not protect runtime behavior.
- Questions for orchestrator: Whether WS7 may correct the cross-layer documents and tests; whether
  obsolete assets belong in the gate candidate despite the ownership wording; and how to replace
  the stale mixed shell/Python verification glob.

## Resolution

- Finding dispositions: Accepted all five required findings. The invalid-bundle gate now checks
  the root marker and zero role-target/service activation timestamps from its local debug shell.
  Both manual BOOT edits are guarded fail-fast subshells that validate the whole disk, parent
  partition, label and actual mount point before writing. The named stale documents, broken link
  and remaining `rsync`/`git pull` deployment claim are corrected. Online verify now requires the
  locally recorded Ed25519 SHA-256 host-key fingerprint, checks a bounded scan against it, pins the
  result temporarily and enables strict host-key checking. Remote stdout uses a temporary file and
  a capped read. The orchestrator also promoted authenticated coordinator readiness to required
  and accepted the small cross-layer
  documentation and test corrections. Scope controls candidate contents, so the ownership wording
  now matches the obsolete-asset removal already required for validation. The shell command names
  shell executables explicitly and compiles the Python consumer separately.
- Simplification/deletion pass: Reused `REMOTE_CONSOLE_CHECKS`, kept host authentication ephemeral,
  and added no inventory, provisioning field, trust-on-first-use state or crypto protocol. Removed
  the new deletion-regression and source-string assertions. Malformed remote evidence now reports
  authenticated SSH failure or invalid evidence instead of claiming only network unavailability.
- Final verification: The focused verification, all `985` Python tests, mypy over `144` source
  files, Ruff, import contracts and the generated custom-protocol check passed. Frontend API
  contracts, lint, typecheck, all `208` tests and both production builds passed. The image builder,
  deployment helpers, kiosk scripts and image hooks passed shell syntax checks; the Python
  provisioning consumer compiled; and `git diff --check` passed. The focused verify suite passed
  all `17` tests, including missing and mismatched fingerprint rejection and bounded remote output.

## Closure review

- Reviewer: Fresh in-session reviewer (`/root/ws7_closure`).
- Finding outcomes: All accepted findings are closed. The invalid-bundle procedure now records the
  retained root marker and zero activation timestamps for the role target and main role service
  before it relies on the bounded BOOT status. Both manual BOOT edits run in fail-fast subshells
  and validate the whole disk, parent partition, exact `BOOT` label and selected partition's mount
  point before writing. The active reliability, wiring and Waveshare guidance no longer teaches
  the deleted setup or Ethernet path, and the broken reliability link is corrected.
- Security and diagnostic evidence: Online verification requires an explicit Ed25519 SHA-256
  fingerprint from the local physical check. It accepts exactly one matching `ssh-keyscan` result,
  pins that key in a mode-`0600` temporary `known_hosts` file and invokes SSH with strict host-key
  checking. The remote result goes to a temporary file, is read with a 256 KiB cap and fails closed
  on excess or malformed evidence. Coordinator readiness now requires a trusted, operator-
  authenticated `200`; all failed and unavailable checks still force a failed result and nonzero
  exit. The card-failure guidance distinguishes an ordinary card retained under operator control
  from loss of control or suspected compromise, which still replaces the installation and both
  devices.
- Review dispositions and scope: The orchestrator resolved all three review questions in the
  recorded remediation: WS7 owns the small active-document and test corrections, obsolete setup
  assets belong in the gate candidate, and the verification command checks shell and Python
  executables with their proper tools. The diff does not change coordinator-panel firmware,
  runtime hotspot-button handling, frontend panel behavior or its protocol. The panel-button
  conflict remains outside this workstream.
- Verification: `uv run pytest -q e87ctl/tests/test_verify.py` passed (`17 passed`). `uv run ruff
  check e87ctl`, `uv run mypy` (`144 source files`), the corrected shell syntax command,
  `python3 -m py_compile deploy/bin/e87canbus-provision` and `git diff --check` passed. A focused
  source and documentation audit found no unresolved accepted finding or release-blocking defect
  introduced by remediation.
- Verdict: Accepted. No required finding remains. The provisioned-pair hardware gate is still
  pending and determines workstream acceptance.
- Accepted commit: `TBD`
