# Workstream 8: Retire the panel hotspot control

Status: accepted.

## Why this exists

The provisioned Wi-Fi network and the panel hotspot button control the same NetworkManager
connection. The access point now starts automatically and carries the console's only transport, so
the old maintenance-hotspot button can disconnect the console while the coordinator is running.
The hotspot display states also outrank `READY`, which prevents the healthy steady-state display
while the console remains associated.

Workstream 6 raised this conflict and deferred it. Aidan chose full removal in a separate Claude
thread on 2026-09-12 and confirmed that decision in the orchestration thread. The panel becomes a
status indicator with no network authority.

## Task packet

### Outcome

The coordinator panel shows `STARTING`, `READY`, `FAULT` and `OFF` only. It cannot start or stop
the provisioned Wi-Fi network. The obsolete hotspot helper, privileged host path, simulator and UI
operations, and firmware button event are absent.

### Scope

- Delete the host hotspot model and NetworkManager adapter with their focused tests.
- Reduce panel behavior to coordinator status and remove the hotspot dependency and button path
  from physical and simulated runners.
- Remove simulator API models and routes for hotspot state, connection, failure and panel presses.
  Regenerate the OpenAPI document and coordinator client rather than editing generated files.
- Remove hotspot controls and copy from the coordinator panel and simulator UI.
- Remove hotspot display states from coordinator-panel firmware. Keep the physical button wired
  and debounced, but stop emitting its UART event.
- Delete the root hotspot helper and sudo rule. Remove their image installation checks and restore
  `NoNewPrivileges=true` for the coordinator service.
- Update active panel, image and wiring documentation. Extend ADR 0013 to supersede the panel
  control in ADR 0010 while preserving accepted ADR history.
- Update the Wi-Fi specification so no panel action starts or stops the provisioned network.

### Non-goals

- Repurposing the physical button or reserving its UART command.
- Adding a console-link indicator or rebuilding one from wireless station polling.
- Changing access-point, DHCP, firewall, nginx or authorization behavior.
- Renaming hotspot-related comments that describe the provisioned access point rather than the
  removed control path.

### Initial ownership

- `hosts/src/e87canbus/{hotspot,panel}.py`, the NetworkManager hotspot adapter, panel runners and
  focused host tests
- Simulator panel API, `protocol/openapi.json` and generated coordinator-client output
- Coordinator panel and simulator frontend components and tests
- `devices/coordinator-panel/`
- Hotspot helper, sudo rule, coordinator service and coordinator image customization
- `docs/wiring.md`, `images/README.md`, `docs/specs/wifi-device-network.md` and ADR 0013

### Required seams

- Preserve the panel's heartbeat, fault, timeout and graceful-off behavior.
- Leave no host reader for a firmware event that is no longer emitted.
- Remove the controller service's last privileged network operation and its service-account sudo
  rule.
- Collapse the second panel thread if it exists only to isolate slow NetworkManager operations.
- Keep workstream 7 verification behavior and external-gate instructions synchronized with the
  final panel and image behavior.

### Acceptance criteria

- No coordinator code path can deactivate `e87canbus-coordinator-wifi`.
- `READY` is the steady-state panel display on a healthy provisioned coordinator.
- The image contains no hotspot helper or service-account sudo rule.
- Firmware emits no button event and the host has no handler for one.
- Simulator API, generated client and coordinator UI expose no hotspot operation or state.
- A service laptop can associate and reach HTTPS without physical panel action.
- ADR 0013 records retirement of ADR 0010's panel control without rewriting accepted history.
- Active documentation contains no instruction to press the panel button for Wi-Fi.

### Targeted verification

```bash
uv run pytest hosts/tests -q
uv run pytest e87ctl/tests/test_image_build.py e87ctl/tests/test_verify.py -q
uv run ruff check hosts e87ctl
uv run mypy
python3 -m py_compile deploy/bin/e87canbus-provision
for script in images/coordinator/customize.sh images/e87canbus-image-check \
  deploy/bin/e87canbus-firewall; do
  bash -n "$script"
done
```

```bash
cd frontend
pnpm api:generate
pnpm api:check
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

Run the native coordinator-panel PlatformIO tests. Confirm generated diffs contain only the
removed hotspot operations. Docker image assembly, NetworkManager and physical Pi checks remain
external and must not be claimed on the implementation host.

## External validation

- Gate and placement: complete provisioned pair, after closure and before acceptance.
- Status: `Troubleshooting`
- Candidate and evidence: corrective software commit
  `f67e02e226491b7211c61ffd97bc73ce0c3a2792`; fresh images have not yet been built. Candidate
  `eda0d12cfb56a23ed71bd1a3e33eb40be229b75b` passed its deployed device path, but the subsequent
  workstation verification exposed three CLI, release-construction and certificate-generation
  defects. See [the physical report](evidence/eda0d12-physical-gate-report.md) and
  [the verifier follow-up](evidence/eda0d12-e87ctl-verification-diagnostics.md).
- Required evidence: All evidence listed in workstream 7 plus a healthy steady-state `READY`
  display and confirmation that panel presses do not change the provisioned network.
- Attempts and lasting decisions: Attempt 1 reached `completed_phase=boot_removed`, then failed with
  `provisioning_interrupted`. Debian Trixie's `systemd-machine-id-setup --commit` cannot handle the
  deliberately absent `/etc/machine-id`; plain `systemd-machine-id-setup` creates the required
  unique ID. The active macOS instructions also used nonexistent plist key `Whole` instead of the
  measured `WholeDisk`. Candidate `90d4142c24189c42655dd3ec91abab0bda487e8d` contains both
  focused corrections. Attempt 2 on that candidate passed machine-ID creation and host identity,
  then reached `completed_phase=installed` before failing with `provisioning_interrupted`.
  `verify_installed()` included matching systemd relationship and drop-in directories in its
  `systemd-analyze verify` arguments, which the tool rejected. The physical checker also mistook
  vacancy of UID 1000 for removal of the upstream `pi` account, even though provisioning correctly
  creates `e87-admin` as the first regular user. The correction verifies only matching unit files
  and checks that the named upstream account is absent. Candidate
  `3fccfd009a2beffd7a4cd1addfe7373126a9b78f` contains both focused corrections. Aidan retained the
  attempt evidence outside the repository under
  `~/.e87canbus/gates/90d4142c24189c42655dd3ec91abab0bda487e8d/`. Attempt 3 on
  `3fccfd009a2beffd7a4cd1addfe7373126a9b78f` passed host identity and reached installed-state
  verification. It exposed an nginx validation precondition, an invalid empty `gateway=` property
  in the generated NetworkManager profile, and a target incompatibility between NetworkManager's
  iwd backend and an SAE access point. The focused correction creates nginx's runtime directory
  before native configuration validation and omits both gateway and DNS properties while requiring
  the no-default-route and ignore-DNS settings. Aidan approved replacing iwd with NetworkManager's
  default wpa_supplicant backend after the physical result invalidated the earlier iwd assumption.
  The image now removes both iwd layer selections and installs Debian Trixie's `wpasupplicant`
  explicitly. The bundle retains its SAE-only and required-PMF settings, and the physical gate must
  still prove both. Claude Opus at medium effort accepted the cumulative correction with no
  required findings. Candidate `9924947eacd209fc00b9eaa7fb0df5098c63892b` contains the reviewed
  correction. Attempt 4 on that candidate proved `nginx -t` binds the configured `10.42.0.1`
  address during provisioning, before NetworkManager assigns it. This physical result disproves
  the focused review's conclusion that creating nginx's runtime directory was a complete
  precondition fix. Provisioning now leaves nginx validation to the existing service
  `ExecStartPre`, which runs with its runtime directory after `NetworkManager-wait-online`; it keeps
  the interface-independent dnsmasq and nftables checks. Candidate
  `b944952b8672b601d11cb0f83feaf4c4ef4d4da4` contains this focused correction. Attempt 5 on that
  candidate provisioned successfully and passed every physical checker item except the WPA3 access
  point. The correct SAE, required-PMF and address settings remained inactive. Explicit activation
  reached wpa_supplicant but failed with `Could not generate WPA IE`, `WPA initialization failed`
  and `Failed to initialize AP interface`; `get_throttled=0x0` ruled out a power fault. Both iwd and
  wpa_supplicant have now failed SAE access-point operation on the target Pi 4 stack. Aidan approved
  the one documented fallback: WPA2-Personal with RSN only, CCMP only and required PMF. The existing
  32-character random installation PSK makes offline guessing impractical. TLS, mutual TLS, SSH,
  firewall filtering and disabled forwarding remain unchanged. Claude Opus at medium effort
  accepted the focused correction and closure with no remaining required findings. Candidate
  `3631bfcdf655f5af73162b3903fcccc9d197e166` contains the reviewed fallback. Console diagnostics
  on that candidate proved the fallback in operation: provisioning completed after manually
  bypassing the missing `/usr/bin/chvt`, the console joined the coordinator, its WPA2-RSN check
  passed and every remaining console check passed except the checker's unconditional listen-only
  assertion. The selected `bench` profile correctly disables listen-only. Candidate
  `8ed08b2152f4aaf93a64c4388604f853020f1e7a` installs the console-only `kbd` package that provides
  `chvt` and makes the physical CAN check enforce the provisioned `car` or `bench` mode. That
  candidate provisioned the console and started Cage, but Chromium `152.0.7977.82-1~deb13u1`
  repeatedly exited from `SIGTRAP` with status 133. The display stayed black apart from an
  intermittent cursor and Chromium wrote minidumps without useful stderr. Diagnostics ruled out
  automatic Ozone selection, the Chromium sandbox, GPU acceleration, D-Bus session setup, the
  persistent profile and missing Mesa DRI drivers. The card was modified during diagnosis and
  cannot supply final evidence. GDB confirmed that the installed Raspberry Pi Chromium build did
  not match Debian's debug symbols, but register values at the deliberate trap decoded to fragments
  of `select_certificate_for_urls`. The generated Linux policy used dictionary entries where
  Chromium requires stringified JSON dictionaries. Candidate
  `ca6a8267201b3ef82fcf47030d2cefdb0761ac74` corrects only that serialization; its origin and
  installation-CA issuer restrictions remain unchanged. Radio diagnostics on the later rolling
  build then isolated a local Pi 4 brcmfmac status-16 association regression: both Pis worked with
  unrelated peers, but the console could not reach authentication with the coordinator under any
  tested PMF, band, power-saving or userspace-owner variation. Candidate
  `2827f7eaa2a69f5c1daf26910c4fe813a974b8e3` applies the evidence-backed correction by resolving
  only `firmware-brcm80211` from Debian for both roles. It leaves the Raspberry Pi kernel,
  NetworkManager ownership and the WPA2-RSN/CCMP/required-PMF profile unchanged. The clean-card
  report proved that the Debian package loaded but did not restore association, so commit
  `908f835be7fd16b68c684782dedbf816de91e882` next isolated Raspberry Pi's maintained Bookworm 6.12
  kernel line. Before that image was built, the authoritative DSI A/B/A test on candidate
  `2827f7e` superseded both software diagnoses. The unchanged production profile repeatedly joined
  on Trixie 6.18 with the console ribbon disconnected. Attaching and enabling the display collapsed
  only the 2.4 GHz scan census and usually removed the coordinator from view; disconnecting it
  restored reception. The 5 GHz join test was split and supports no production choice. The forward
  cleanup candidate removes both diagnostic package overrides without rewriting their history.
  A later physical-separation test then associated the console immediately and kept it connected at
  `10.42.0.2`, strongly confirming display proximity as the status-16 cause. That test separately
  exposed a coordinator image defect: `e87canbus-nginx.service` crash-looped because nginx retained
  default temporary paths under read-only `/var/lib/nginx`, while Debian's stock `nginx.service`
  exposed unauthenticated port 80. The checker falsely accepted the custom unit's
  `activating (auto-restart)` state. Candidate
  `417d4b47ba7746b8da5472bc364b230a29d0e5eb` moves every nginx temporary path beneath its systemd
  runtime directory, selects `www-data`, masks the stock unit and requires the intended HTTPS
  listener while rejecting port 80. The configured Claude review call exhausted its session quota
  without returning a review; the documented fresh in-session fallback accepted the correction
  with no findings.
- Result: Fresh coordinator and console cards provisioned successfully. Both complete streamed
  image checkers passed; the console associated immediately while physically separated from the
  display, Chromium mutual TLS loaded settings through the authenticated API, port 443 remained
  stable and port 80 was absent. Aidan accepted this as passing the software and image workflow.
  Designing and validating the mechanical spacer remains separate hardware integration work.

## Implementation handoff

- Base commit: `87441b224e69b1a91a845148dbb2cdc590121daf`
- Outcome: Retired the complete coordinator-panel hotspot authority. The physical and simulated
  panels now expose only coordinator `STARTING`, `READY`, `FAULT` and `OFF` status. NetworkManager
  autoconnect remains the sole owner of the provisioned access point.
- Files changed: Deleted the host hotspot service, NetworkManager adapter, root helper, sudo rule
  and their focused tests. Reduced the panel domain, UART adapter, physical and simulated runners,
  simulator API and tests. Regenerated `protocol/openapi.json` and the coordinator HTTP client.
  Removed coordinator and simulator UI controls and hotspot presentation. Reduced coordinator-panel
  firmware and tests to four display states without emitting button events. Updated coordinator
  image package/install wiring and checks, the controller unit, active panel/image/wiring
  documentation, the Wi-Fi specification, ADR 0013 and the combined physical-gate procedure.
- Decisions: Removed the operation and state contracts rather than retaining aliases. The physical
  runner now uses one thread for its one-second UART heartbeat because it no longer waits on
  NetworkManager. UART I/O failure still stops heartbeats so firmware reaches `FAULT`; orderly
  shutdown still sends `OFF`. Firmware continues to read and debounce the wired button but does
  nothing with a press. `CoordinatorStatus` is the one host, simulator API and frontend status type;
  there is no duplicate display field or alias. ADR 0013 now explicitly supersedes ADR 0009's
  hotspot mechanism and button handling while preserving its panel-isolation decision. ADRs 0009
  and 0010 remain unchanged as accepted history.
- Simplification pass: Removed the second panel thread, button queue, host UART reader, hotspot
  state machine, simulated hotspot backend, four simulator mutations, six-state display logic,
  duplicate panel-display type and API field, now-unused `iw` package and privileged service path.
  No button command, alternate network control or replacement indicator remains.
- Verification: `uv run pytest e87ctl/tests/test_image_build.py e87ctl/tests/test_verify.py
  hosts/tests -q` passed (`893 passed`). Ruff passed for `hosts` and `e87ctl`; mypy passed over 142
  source files. Shell syntax passed for the coordinator image hook, image checker and firewall
  helper; the provisioning consumer compiled; the coordinator-panel logic header passed a C++17
  syntax check; and `git diff --check` passed. `pnpm api:generate` regenerated the source-derived
  contracts. Frontend API checks, lint, typecheck, all tests and both production builds passed (`6`
  coordinator-client files with `18` tests, `24` console files with `101` tests and `21` coordinator
  files with `89` tests). PlatformIO is not installed on this host, so the native coordinator-panel
  test command was unavailable and is not claimed. Docker image assembly, NetworkManager and
  physical Pi behavior remain at the documented external gate.
- Specification drift: Aidan approved making the panel status-only. The Wi-Fi specification and
  ADR 0013 now record that behavior. Naming both ADR 0009 and ADR 0010 in ADR 0013 corrects the
  source-history reference within that approved removal; it does not broaden the behavior change.

## Independent review

- Reviewer: Claude Code Opus at medium effort through the configured read-only review command.
- Verdict: Changes required.
- Required findings:
  1. The workstream 7 and 8 verification commands passed several paths to one `bash -n` invocation.
     Bash parses only the first path as a script and treats the rest as arguments, so the records
     overclaimed syntax coverage.
  2. `PanelDisplay` duplicated `CoordinatorStatus`, and the simulator API returned both identical
     values. This left two names and fields for one status-only concept after the hotspot states
     disappeared.
- Optional observations: Reflow the two documentation artifacts; return the effective simulated
  status instead of storing a temporary field initialized only by refresh; replace new
  path-deletion assertions with tests of the durable privilege boundary; remove the unobservable
  wiring debounce bench instruction; make ADR 0013 precise about which part of ADR 0009 it
  supersedes; and protect the single-thread UART write-failure behavior with one focused test.
- Questions for orchestrator: Whether retaining the wired pull-up button and debouncer leaves an
  unnecessary concept, and whether historical raspberry-pi-image-building records should also be
  rewritten to remove their accepted hotspot descriptions.

## Resolution

- Finding dispositions: Accepted both required findings. The shell commands now loop over existing
  paths and invoke `bash -n` once per file. `CoordinatorStatus` now flows directly through the panel
  domain, UART adapter, physical runner, simulator model, generated API and frontend. Promoted all
  optional cleanup because each removes misleading text, duplicate state or an implementation-only
  assertion. Keep the wired pull-up and debouncer because Aidan explicitly approved that packet
  boundary; firmware emits no event and the host has no reader. Keep accepted image-building
  records immutable; current specifications, active documentation and this workflow record the
  replacement behavior.
- Simplification/deletion pass: Deleted `PanelDisplay`, `derive_display`, their ceremonial focused
  test and the simulator's duplicate `display` field. Simulated refresh returns the effective
  status to the response builder instead of storing transient state. Image and deployment tests now
  protect `NoNewPrivileges` and the absence of an effective service-account sudo grant rather than
  named deleted paths. The new UART write-failure test proves that an I/O fault stops heartbeats and
  does not send graceful `OFF`.
- Final verification: The full targeted verification passed after remediation: `835` host tests
  and `58` focused `e87ctl` tests (`893` total), Ruff, mypy over `142` source files, provisioning
  script compilation, corrected per-file shell parsing and `git diff --check`. OpenAPI and client
  regeneration were clean; frontend API checks, lint, typecheck, `208` tests and both production
  builds passed. A direct C++17 syntax check of `panel_logic.h` passed. PlatformIO remains
  unavailable on this host, so its native test and the documented physical checks are not claimed.

## Closure review

- Reviewer: Claude Code Opus at medium effort through the configured read-only review command.
- Verdict: Accepted.
- Remaining required findings: None. The reviewer verified both required corrections and every
  promoted cleanup, including the durable privilege checks and UART failure behavior. PlatformIO,
  image assembly, NetworkManager and physical Pi behavior remain assigned to external validation.
- Accepted commit: `f4c775f36f05292615308828ac7151aa5d64bdb1`
