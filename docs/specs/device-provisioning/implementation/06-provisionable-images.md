# Workstream 6: Build provisionable coordinator and console images

Status: accepted.

## Task packet

### Outcome

Both reusable images contain the same strict, idempotent first-boot consumer and their role-specific
Wi-Fi/TLS service composition. They contain no cloned host identity and remain fail-closed until a
valid bundle is fully installed.

### Scope

- Extend the image contract and manifest with provisioning version and storage limits.
- Remove reusable hostname, machine ID and SSH host keys; generate/install unique identity locally.
- Implement the root-owned durable first-boot phases, exact ZIP validation, bounded staging,
  ready-release activation, non-secret status and secret cleanup.
- Create `e87-admin`, `e87-kiosk` and service accounts with the specified login and sudo boundaries.
- Configure coordinator NetworkManager access point, DHCP-only dnsmasq, firewall, nginx HTTPS/mTLS
  and SSH exception.
- Configure console NetworkManager client, Chromium trust/client certificate and automatic
  certificate selection.
- Gate all role services on successful provisioning and remove the bundle/marker in the specified
  order.
- Add assembled-root or sandboxed behavioral tests for success, rejection and interrupted resume.

### Non-goals

- A second bundle schema, in-place repair, rollback, rotation or general-purpose installer.
- Internet sharing, DNS, gateway advertisement, IP forwarding, wireless CAN or cockpit behavior.
- A competing application authorization map in nginx.

### Initial ownership

- `images/` definitions, layers, role hooks, image checker and focused image tests
- Provisioning consumer, systemd, nginx, dnsmasq, NetworkManager, SSH, kiosk and service assets
  under `deploy/`
- Minimum host runtime configuration needed to use `/opt/e87canbus/current` and provisioned files,
  as an explicit integration exception coordinated with workstream 5

### Required seams

- Independently validate workstream 3's baked image contract and provisioning bundle.
- Install the authenticated-transport inputs defined by workstream 5 without broadening its
  authorization table.
- Preserve the accepted Docker builder and command from workstream 1.
- Produce both root and boot status documents consumed by workstream 7.
- Preserve the exact `bootfs` boot-partition label consumed by workstream 4's safe writer.

### Acceptance criteria

- Invalid, incompatible, corrupt, duplicate, unknown, traversal or oversized input changes no
  installed state and leaves role services disabled.
- Durable phases resume safely after interruption; `unprovisioned` clears only after complete
  validation, installation, cleanup and status.
- No secret value reaches status, journal or overly broad file permissions.
- First boot performs no package install, dependency resolution or application/frontend build.
- Each Pi receives its assigned hostname/device identity and locally unique machine ID/SSH keys.
- Coordinator and console implement the exact IP, DHCP, WPA2-Personal/RSN/CCMP/required-PMF,
  no-forwarding, TLS and service policy from the Wi-Fi contract.
- Chromium can select only the installed console identity for the coordinator origin without
  frontend access to its private key.
- Both images build structurally through the existing wrapper; real hardware behavior remains
  explicitly owned by workstream 7.

### Targeted verification

```bash
uv run pytest e87ctl/tests/test_image_build.py hosts/tests/test_host_deployment.py -q
uv run ruff check e87ctl hosts
uv run mypy
bash -n e87ctl/scripts/build-pi-image deploy/bin/* deploy/kiosk/*.sh
bash -n images/*/customize.sh images/e87canbus-image-check
```

Run `systemd-analyze verify` in a suitable Linux/container fixture for all changed units. Validate
NetworkManager, nginx and dnsmasq configurations with their native parsers in the image test
environment where available. Do not claim Pi radio compatibility from these checks.

## Implementation handoff

- Base commit: `07b4f2d8cf59c0ad4aa852494aba793b01181540`
- Outcome: Both role images now contain one strict first-boot consumer, remove the builder's host
  identity and install only a fully validated, ready application release. The coordinator composes
  the private WPA3 network, DHCP-only dnsmasq, no-forwarding firewall and nginx mTLS boundary. The
  console composes its static Wi-Fi client and an isolated Chromium client identity.
- Files changed: Added the consumer, firewall helper, shared SSH/network/nginx/systemd assets,
  assembled-root behavioral tests and the common image hook. Updated both image layers and role
  hooks, application units and environment paths, the image manifest builder, hotspot helper,
  hardware checker, image runbook and focused deployment/image tests. Removed both baked Ethernet
  NetworkManager profiles; workstream 7 still owns deletion of the superseded fallback setup and
  deploy assets outside these image definitions.
- State-machine phases and installed contract: The durable phases are `staged`, `boot_removed`,
  `installed`, `verified`, `status_written` and `cleaned`; clearing `unprovisioned` is the final
  filesystem mutation. The consumer validates the baked role/interface contract, exact ZIP and TAR
  members, closed JSON documents, bounded sizes, digests, application role/runtime, device
  configuration, Wi-Fi policy and credential encodings before staging. It fsyncs root-owned
  staging, removes the boot ZIP, installs accounts, host identity, credentials and the digest-named
  release, atomically selects `/opt/e87canbus/current`, validates installed files and native
  configuration, writes the strict non-secret root and `bootfs` status, removes staging and starts
  the already-enabled role target. Release extraction fsyncs every file and directory before its
  atomic rename; activation and resume verify the staged archive digest and every installed file
  record before trusting an existing digest directory. Re-entry repeats only incomplete phases.
  Operational failure retains staging and the marker and writes both statuses using the validated
  staged identity; invalid input records a bounded terminal failure without installing state.
- Verification: The required focused command plus the expanded behavioral file passed (`61 passed`).
  The complete `e87ctl` suite passed (`104 passed`). Ruff passed for `e87ctl`, `hosts` and the
  installed Python consumer; mypy passed over 143 source files. All specified shell files and the
  new firewall helper parsed with `bash -n`; `git diff --check` passed. The complete host suite
  passed (`860 passed`), including the focused reliability and consumer files (`17 passed`).
  `dnsmasq --test` accepted the installed configuration. `systemd-analyze verify` parsed every
  changed unit in a synthetic root and
  reported only fixture-missing base targets and executables. This environment has no Docker,
  nginx binary or NetworkManager daemon, and unprivileged nftables validation reached netlink but
  could not evaluate rules, so those native/container checks remain unclaimed.
- Hardware behavior still owned by workstream 7: No image build, macOS write, Pi boot, WPA3/PMF
  radio check, real nftables load, nginx mTLS exchange, Chromium certificate import/selection or
  two-device service check ran here. The combined macOS writer gate and provisioned-pair gate own
  that evidence.
- Specification drift: None. The image candidates preserve the exact `bootfs` label expected by
  workstream 4, the bundle schema from workstream 3 and the loopback console CORS origin and trusted
  nginx headers from workstream 5. A pre-validation failure with no readable manifest cannot supply
  truthful non-null identifiers under the accepted status schema; its existing sentinel failure
  identity remains confined to that case. Post-staging failures use only the validated identity.

## Independent review

- Reviewer: Claude Code Opus at medium effort, using the configured read-only review command.
- Verdict: Required changes.
- Required findings:
  - The provisioning unit runs before NetworkManager but `verify_installed` calls `nmcli connection
    load`, so a valid first boot can fail forever before NetworkManager starts.
  - Failures after the bundle is removed from `bootfs` write no failure status. The card then has no
    offline evidence explaining why it remains unprovisioned.
  - The image contract declares fixed 2 GiB boot and 4 GiB root limits while the image definition
    uses percentage growth. The writer and consumer therefore cannot know that the declared limits
    describe the partitions they validate.
  - `ProtectSystem=strict` does not provide the writable paths dnsmasq and nginx need. The nginx
    unit also lacks restart behavior, so an early bind failure can leave HTTPS down.
  - The firewall starts too late to guarantee that the access point is filtered before it becomes
    reachable, and reload deletes the table before loading its replacement.
  - The coordinator hook writes the image contract without creating its parent directory.
  - Nginx does not replace `X-Forwarded-Proto` or `X-Forwarded-Host`, even though the application
    trusts those values for the Socket.IO same-origin decision.
  - The installed-release resume guard accepts any existing digest directory, and installed
    verification checks only a few paths rather than the application manifest's complete file
    records. An interrupted extraction can therefore be mistaken for a complete release.
- Optional observations:
  - Production provisioning still writes the two Vite development origins into `controller.env`.
  - The old plain provisioning-interface marker duplicates the image-contract version.
  - The consumer validates the NetworkManager profile policy but not its connection ID.
  - Root and boot receive the same status document rather than a smaller boot projection.
  - Failure paths synthesize identifiers that look valid when no trustworthy manifest identity is
    available.
  - Removing the reusable hostname also removes its `127.0.1.1` hosts entry without restoring an
    entry for the assigned hostname.
  - The synthetic-root ownership predicate is inconsistent between account creation and chown.
  - One test block is misindented, and the image checker exercises only the provisioned state.
- Questions for orchestrator:
  - The panel hotspot toggle can still stop the nominally always-on private network. Workstream 7
    owns removal of the superseded setup path, so this remains deferred to that packet.
  - The reviewer questioned iwd support for a WPA3-SAE access point. Debian Trixie ships iwd 3.8;
    upstream added SAE access-point support in 2.18. Keep the selected backend and require the
    documented Raspberry Pi WPA3/PMF hardware evidence before workstream 7.
  - Treat the declared storage values as limits that must come from the same image configuration
    as the built partition geometry, not unrelated policy ceilings.

## Resolution

- Finding dispositions: Accept all eight required findings above. Promote release extraction and
  complete digest verification from the review's optional observations because interruption-safe
  resume is an explicit acceptance criterion. Also restore the assigned hostname in `/etc/hosts`,
  remove development CORS origins from the provisioned production environment, validate the fixed
  NetworkManager connection ID and remove the duplicate plain interface marker. Reject the claimed
  lack of iwd AP-SAE support because it predates the pinned distribution version. Defer the panel
  toggle to workstream 7. Leave the status schema and boot projection unchanged unless remediation
  proves they block truthful failure reporting without a public-contract change.
- Remediation outcome: Removed the pre-NetworkManager `nmcli` dependency; gave dnsmasq and nginx
  explicit runtime/state paths and nginx restart behavior; ordered the atomic firewall transaction
  between provisioning and NetworkManager; created the missing image-contract directory; replaced
  forwarded origin headers with fixed trusted values; made 2 GiB/4 GiB partition geometry explicit
  and build-checked; and made release reuse contingent on complete manifest digest verification.
  Provisioning now restores the assigned hostname in `/etc/hosts`, validates the fixed role-specific
  NetworkManager ID, emits only the loopback console production CORS origin, and records failures
  after boot-bundle removal with the validated identity in both status locations.
- Simplification/deletion pass: Removed the duplicate plain provisioning-interface marker and its
  otherwise-empty overlay. Kept one consumer, one image contract, one role target and the existing
  public status schema; added no fallback network/security modes or alternate installer path.
- Final verification: Focused image, deployment and consumer tests pass (`61 passed`); complete
  `e87ctl` tests pass (`104 passed`); the complete host suite passes (`860 passed`).
  Ruff, mypy over 143 source files, all specified shell syntax checks, `git diff --check` and native
  dnsmasq parsing pass. `systemd-analyze verify` reports only host-missing installed executables.
  Docker/image assembly, nginx, NetworkManager, privileged nftables and physical Pi checks remain
  unavailable here and are not claimed.

## Closure review

- Reviewer: Codex, fresh focused closure reviewer.
- Reviewed state: Complete uncommitted workstream diff from
  `07b4f2d8cf59c0ad4aa852494aba793b01181540`.
- Accepted finding outcomes: All accepted findings are closed. Provisioning no longer invokes
  `nmcli` before NetworkManager. Failures after durable staging and boot-bundle removal write the
  validated device identity and phase to both status locations. The shared image definition,
  build wrapper and role hooks agree on fixed 2 GiB boot and 4 GiB root geometry. dnsmasq and nginx
  receive their required writable runtime or state directories, and nginx restarts after failure.
  The firewall is ordered after provisioning and before NetworkManager, and reload replaces its
  table in one nftables transaction. Both role hooks create the image-contract directory. Nginx
  replaces the trusted forwarded host and protocol headers. Existing releases and interrupted
  extraction directories must match the complete application manifest and every file digest
  before activation.
- Promoted finding outcomes: Provisioning restores the assigned `127.0.1.1` hostname entry,
  validates the fixed role-specific NetworkManager connection ID, writes only the production
  console origin, and removes the duplicate plain provisioning-interface marker and overlay.
- Verification: `uv run pytest e87ctl/tests/test_image_build.py
  hosts/tests/test_host_deployment.py hosts/tests/test_provisioning_consumer.py -q` passed (`61
  passed`). Ruff passed for `e87ctl`, `hosts` and the consumer; mypy passed over 143 source files;
  the specified shell syntax checks, native dnsmasq parsing and `git diff --check` passed.
  `systemd-analyze verify` parsed the remediated provisioning, firewall, dnsmasq, nginx and role
  units and reported only executables absent from this host fixture. No release-blocking defect was
  introduced by remediation.
- Verdict: Accepted.
- Remaining required findings: None.
- Accepted commit: `3bac67b68a265b10508effced7930ae6c82beef7`

## Gate attempt 4 reopening implementation handoff

- Base commit: `a3717ae`
- Outcome: Standardised workstream 6's on-device and hardware checks on the exact `BOOT` label
  emitted by pinned rpi-image-gen. The shared image definition remains the builder's unmodified
  source for that label.
- Claude review: Changes required. Genimage places `extraargs` before its own label argument, so
  the proposed `fs.vfat_mkfs_args: -n bootfs` was overridden by the final `-n BOOT`. Pinned
  upstream's by-slot boot udev rule also matches `ID_FS_LABEL=="BOOT"`, so changing only the
  filesystem label would break upstream boot-device discovery.
- Finding dispositions: Accepted both findings. The product specifications require one exact boot
  partition but do not name its filesystem label. The orchestrator therefore chose upstream's
  existing `BOOT` label as the internal contract. Workstream 4 owns the sequential writer change.
- Files changed: Updated the provisioning consumer, hardware checker, image runbook, focused image
  tests and this reopening handoff. Removed the ineffective image configuration override, builder
  preflight and test from the first implementation pass.
- Decisions: Require exact `BOOT` everywhere in workstream 6. No alias, post-build relabelling,
  role-specific setting or compatibility path was added.
- Verification: The pinned rpi-image-gen source fixes the `simple_dual` FAT label and its by-slot
  udev match to `BOOT`. The focused image, host-deployment and provisioning-consumer tests passed
  with 61 tests. Ruff passed for `e87ctl` and `hosts`; mypy passed over 143 source files; all
  required shell syntax checks and `git diff --check` passed.
- Simplification pass: Removed the losing duplicate label argument and its defensive machinery.
  The built image, on-device consumer and hardware checker now share one upstream label.
- Limitations and drift: This environment did not assemble a Docker image. Gate attempt 5 must
  build and write the combined correction on macOS. Changing the workflow seam from `bootfs` to
  upstream `BOOT` does not change approved product behavior or a security boundary.

### Gate attempt 4 focused closure

- Reviewer: Codex, fresh focused closure reviewer.
- Accepted finding outcomes: Both accepted Claude findings are closed. The ineffective
  `fs.vfat_mkfs_args` override and its defensive checks are absent. The image retains pinned
  rpi-image-gen's exact `BOOT` label, while the on-device provisioning consumer and hardware
  checkpoint require the same value.
- Coupling evidence: At pinned revision `262d4df5a9f9d4133370465399a7958a7c22cdc7`, the
  `simple_dual` genimage definition labels the FAT filesystem `BOOT` and the installed udev rule
  creates `/dev/disk/by-slot/boot` only for `ID_FS_LABEL=="BOOT"`. Keeping the upstream label
  therefore preserves boot-device discovery as well as the assembled image's observed layout.
- Verification: The focused image, host-deployment, provisioning-consumer and macOS writer suite
  passed with 89 tests. The complete `e87ctl` suite passed with 116 tests. Ruff passed for
  `e87ctl`, `hosts` and the installed consumer, mypy passed over 143 source files, the changed
  executable checks parsed with their native interpreters, and `git diff --check` passed.
- Verdict: Accepted for the combined gate candidate. Remediation introduced no release-blocking
  defect.
- Remaining required findings: None.
- Accepted correction commit: `2e29008c5d271fff3cc21fe9e3544f6ecead90b9`.

## Provisioned-pair gate attempt 3 reopening handoff

- Base commit: `d3b29b3fbb033d6adf47ed4aa42879f0868575f8`.
- Outcome: Corrected two installed-state validation defects and replaced iwd with NetworkManager's
  default wpa_supplicant backend after the target rejected SAE access-point mode through iwd.
- Files changed: Updated the provisioning bundle generator and consumer, shared image definition,
  common image layer, focused image and consumer tests, workstream 8 gate record and plan.
- Decisions: Debian Trixie's `wpasupplicant` is now the one explicit Wi-Fi backend package.
  NetworkManager remains the sole network owner. The provisioning profile still requires
  `key-mgmt=sae` and `pmf=3`; it advertises no gateway or DNS and permits no fallback mode.
- Corrections: The generated profile omits invalid empty gateway and DNS properties, and strict
  consumer validation rejects either property while requiring the no-default-route and ignore-DNS
  settings. Coordinator native validation creates nginx's runtime directory before `nginx -t`.
- Verification: The focused image, artifact, online-verification, deployment and provisioning
  consumer tests passed with 106 tests. Ruff passed for `e87ctl`, `hosts` and the consumer; mypy
  passed over 142 source files; consumer compilation, common image-hook parsing and
  `git diff --check` passed. Docker image assembly and native NetworkManager validation remain at
  the physical gate.
- Simplification pass: Removed both iwd layer selections. Added no backend switch, hostapd path,
  duplicate network owner or weaker security profile.
- External evidence: Docker image assembly and Raspberry Pi radio behavior remain unclaimed. The
  next exact candidate must pass the complete provisioned-pair gate, including SAE and required
  management-frame protection.
- Focused review: Claude Code Opus at medium effort accepted the cumulative correction with no
  required findings. It reproduced `973` tests, Ruff, mypy over `142` source files, provisioning
  consumer compilation and `git diff --check`. It confirmed one NetworkManager owner, no weaker
  security mode, strict absence of gateway and DNS properties, and the correct nginx validation
  precondition. Docker assembly and physical SAE/PMF behavior remain at the gate.
- Accepted correction commit: `9924947eacd209fc00b9eaa7fb0df5098c63892b`.

### Provisioned-pair gate attempt 4 troubleshooting correction

- Physical evidence: Candidate `9924947eacd209fc00b9eaa7fb0df5098c63892b` reached installed
  verification, where provisioning-time `nginx -t` tried to bind `10.42.0.1` before
  NetworkManager assigned it. This disproves the focused review's conclusion that creating the
  runtime directory made nginx validation safe before networking.
- Correction: Removed nginx validation from provisioning. The existing
  `e87canbus-nginx.service` owns `nginx -t` through `ExecStartPre`; systemd runs it with
  `RuntimeDirectory=e87canbus-nginx` after `NetworkManager-wait-online.service`. Provisioning
  continues to validate the interface-independent dnsmasq and nftables configurations.
- Focused coverage: The consumer test requires provisioning native validation to run only dnsmasq
  and nftables. The image test requires the nginx service's runtime directory, network ordering and
  exact `ExecStartPre` check.
- Verification: The focused image, artifact, online-verification, deployment and provisioning
  consumer tests passed with 106 tests. Ruff passed for `e87ctl`, `hosts` and the consumer; mypy
  passed over 142 source files; consumer compilation and `git diff --check` passed.
- Simplification pass: Removed the runtime-directory constant, provisioning-time nginx call and
  obsolete workaround test. Added no retry, alternate address or second validation path.
- Resume condition: Publish one corrected candidate, then repeat the complete physical gate from
  clean cards.
- Accepted correction commit: `b944952b8672b601d11cb0f83feaf4c4ef4d4da4`.

## Provisioned-pair gate attempt 5 reopening handoff

- Base commit: `0df1babbb4db591c7282a98d91f596de7f1c5116`.
- Physical evidence: Candidate `b944952b8672b601d11cb0f83feaf4c4ef4d4da4` provisioned
  successfully and passed every physical checker item except the WPA3 access point. Its SAE,
  required-PMF and address settings were correct, but the profile stayed inactive. Explicit
  activation reached wpa_supplicant, which reported `Could not generate WPA IE`,
  `WPA initialization failed` and `Failed to initialize AP interface`. Power was healthy at
  `get_throttled=0x0`. Together with attempt 3's iwd failure, both available NetworkManager
  backends have failed SAE access-point operation on the target Pi 4 stack.
- Decision: Aidan approved the specification's single evidence-backed fallback. Use
  WPA2-Personal with RSN only, CCMP only and required PMF through the existing NetworkManager and
  wpa_supplicant ownership. We briefly considered disabling PMF, but the evidence isolates SAE and
  does not justify that extra downgrade.
- Security effect: The fallback loses SAE forward secrecy and resistance to offline password
  guessing. The existing generated 32-character random installation PSK makes guessing
  impractical. Required PMF, TLS, mutual TLS, SSH, firewall filtering and disabled forwarding
  remain unchanged.
- Files changed: Provisioning profile generation and strict consumption, online verification,
  physical image checker, focused tests, active Wi-Fi, provisioning, deploy and image documentation,
  workstream 7's physical procedure, ADR 0014 and the active workflow records.
- Verification: The complete Python suite passed with 979 tests. Ruff passed for `e87ctl`, `hosts`,
  the consumer and the watched-contract script; mypy passed over 142 source files. Both import
  contracts and the generated custom-protocol check passed, as did consumer compilation,
  image-checker shell parsing and `git diff --check`. A final 112-test focused run passed after
  tightening the exact Wi-Fi security-property set.
- Simplification pass: Replaced the active SAE assertions with one exact WPA2-RSN/CCMP contract.
  Added no selectable mode, compatibility alias, TKIP path, second backend or hostapd service.
- External evidence: The corrected exact candidate must repeat the complete provisioned-pair gate
  and prove active profiles with `key-mgmt=wpa-psk`, `proto=rsn`, CCMP-only pairwise and group
  ciphers, and `pmf=3` on both Pis.
- Focused review: Claude Code Opus at medium effort required two changes. The consumer test's broad
  `"sae"` absence assertion could match a random generated SSID or PSK, and the active workstream
  acceptance criterion still named WPA3/PMF. Both findings were accepted. The test now rejects the
  exact `key-mgmt=sae` property, and the criterion names the approved
  WPA2-Personal/RSN/CCMP/required-PMF contract. Reflow suggestions, the pre-existing ConfigParser
  default-section case and alternate security wording remain optional and were not promoted.
- Remediation verification: The 76 focused provisioning-consumer, online-verification and image
  tests passed. Ruff and `git diff --check` passed. The simplification check found no alias,
  fallback mode or extra validation path introduced by remediation.
- Closure review: Claude Code Opus at medium effort accepted both corrections with no remaining
  required findings. It reran the same 76 focused tests, Ruff, image-checker shell parsing and
  `git diff --check`, and confirmed the five-property Wi-Fi contract remains consistent from
  generation through physical verification. Hardware compatibility remains at the gate.
- Accepted correction commit: `3631bfcdf655f5af73162b3903fcccc9d197e166`.

### Provisioned-pair gate console troubleshooting correction

- Physical evidence: Candidate `3631bfcdf655f5af73162b3903fcccc9d197e166` provisioned the
  console successfully after manually bypassing its missing `/usr/bin/chvt`. The console joined
  the coordinator and passed the WPA2-RSN check. Every remaining console check passed except the
  checker's unconditional listen-only assertion. The selected `bench` profile correctly configures
  `kcan` with listen-only disabled so it can acknowledge frames on the isolated bench bus.
- Correction: The console image installs Debian's `kbd` package, which provides the kiosk unit's
  existing `/usr/bin/chvt` command. The physical checker reads the strict provisioned
  `/etc/e87canbus/device.json` and requires listen-only for `car` or disabled listen-only for
  `bench`.
- Focused coverage: The image test requires `kbd` in the console-only package layer and pins both
  deployment-profile branches in the physical checker. The runbook now describes the same
  profile-dependent CAN check.
- Simplification pass: Kept the existing kiosk unit and provisioning-controlled CAN setting. Added
  no alternate VT switch, inferred profile or fallback CAN mode.
- External evidence: The next exact candidate must repeat the console first boot without the
  manual `chvt` bypass and pass the profile-aware physical checker.

### Provisioned-pair gate Chromium policy correction

- Physical evidence: Candidate `8ed08b2152f4aaf93a64c4388604f853020f1e7a` provisioned the
  console and started Cage, but Raspberry Pi Chromium
  `152.0.7977.82-1~deb13u1+rpt2` exited with status 133 from `SIGTRAP`. The diagnostic card was
  modified and cannot supply final gate evidence. Its report is retained at
  `evidence/8ed08b2-chromium-gdb-report.txt`.
- Diagnosis: The installed Raspberry Pi build has build ID
  `18af09b2cf097d17f79e2717b6ec2d0b7528d4a5`, while Debian's non-Raspberry-Pi debug package has
  build ID `0297ec5e840b87b8936579770f04581456ad51b8`, so GDB could not produce named frames. The
  register values at the deliberate `brk` instruction nevertheless decode to fragments of
  `select_certificate_for_urls`. Chromium's policy schema requires
  `AutoSelectCertificateForUrls` to be a list of stringified JSON dictionaries. The consumer wrote
  a list of dictionaries, sending the Raspberry Pi build into that policy parser failure.
- Correction: Serialize the one origin and issuer filter as compact JSON inside the policy's outer
  list. The selection remains restricted to `https://10.42.0.1` and certificates issued by the
  installation CA.
- Focused coverage: The sandboxed console-consumer test now checks that the outer policy contains
  one string and parses that string to verify the exact origin and issuer filter. The focused
  consumer and image suites passed (`59 passed`). Ruff passed on the changed consumer and tests;
  Python compilation, the workstream's shell syntax checks and `git diff --check` also passed.
- Simplification pass: Kept the existing Chromium package, kiosk command, certificate store and
  managed-policy file. No browser flag, alternate browser, package pin, debug package or recovery
  path enters the image.
- External evidence: Build the next exact candidate and repeat console provisioning from a clean
  card. The kiosk must remain running, render the coordinator UI and complete the client-certificate
  connection without diagnostic modifications.

### Provisioned-pair gate Pi-to-Pi radio diagnosis

- Physical evidence: The console associates with ordinary access points, and a Mac completes the
  WPA handshake with the coordinator. The Pi console cannot associate with the Pi coordinator
  under ordinary WPA2 with PMF required, optional or disabled. Disabling power saving, bypassing
  NetworkManager, changing frequency band and rebooting both radios do not change the result. Each
  attempt reaches an accepted nl80211 connect request, then returns `NL80211_CMD_CONNECT status=16`
  after about 0.4 seconds. The coordinator receives no authentication or handshake. Candidate
  `3631bfcdf655f5af73162b3903fcccc9d197e166` previously joined the same coordinator and passed its
  WPA2-RSN check, while a later rolling build regressed. This isolates the failure to the Pi 4
  brcmfmac AP/STA combination rather than the approved network profile or userspace owner.
- Package provenance: Pinned `rpi-image-gen` revision
  `262d4df5a9f9d4133370465399a7958a7c22cdc7` composes `rpi4` through `rpi-generic64`. Its
  `rpi-linux-v8` layer requests `linux-image-rpi-v8`, while `rpi-device-base` requests
  `firmware-brcm80211`. The `rpi-debian-trixie` layer resolves both from Raspberry Pi's live Trixie
  repository. The dated Debian snapshot in `images/builder/debian.sources` supplies only the
  builder container, so neither target package version is frozen or recorded in the image
  manifest. On 2026-09-14 the live repository advertises kernel meta-package
  `1:6.18.39-1+rpt1` and firmware package `1:20260519-1~bpo13+1+rpt1`; that does not prove which
  versions the failed candidate contains.
- Diagnosis: Raspberry Pi's firmware tracker issue
  [#58](https://github.com/RPi-Distro/firmware-nonfree/issues/58) reports the same low-level Pi 4
  BCM4345/6 local status-16 association signature after installing
  `1:20260519-1~bpo13+1+rpt1`, although its peer setup is not identical. Debian Trixie's
  `20250410-2` package restores association in that report with no other change. Raspberry Pi's
  retained `firmware-brcm80211` packages from `20240709`, `20241210`, `20250410` and `20260519`
  contain the same Pi 4 BCM43455 standard blob, SHA-256
  `d608f866582519c0a28d86db43040f4f1b98dd1d153e72e9752586546b4a36c3`, version `7.45.265`.
  Pinning an older Raspberry Pi package or selecting its `7.45.241` minimal alternative would test
  a different and less relevant change. Debian's package instead supplies firmware `7.45.234`,
  SHA-256 `d408faa9d0d5b1a2f9912dcea53ab0be48217288e398406d117f0edafe7c3edd`, which matches the
  evidence-backed fix.
- Correction: Before package resolution, the common image layer writes one APT preference for
  `firmware-brcm80211` from release origin `Debian` at priority 1001. Both roles therefore select
  Debian Trixie's package instead of Raspberry Pi's epoch-prefixed package. The preference remains
  in the image, so later package operations keep following Debian's supported Trixie firmware
  updates rather than freezing one version. The kernel remains on Raspberry Pi's normal supported
  track because the matching report fixes the same failure without changing it.
- Security and architecture: This keeps NetworkManager with wpa_supplicant as the sole network
  owner and leaves the WPA2-RSN/CCMP/required-PMF profile unchanged. Debian's Trixie package is a
  distribution-supported firmware source. Its BCM43455 binary contains SAE and DPP support but
  lacks the Raspberry Pi standard variant's external-SAE support. The approved WPA2 network uses
  neither SAE mode nor DPP. The physical retest must still prove required PMF. No hostapd service or
  alternate network path is added.
- Focused coverage: The image test requires the preference to target only
  `firmware-brcm80211`, select origin `Debian` with downgrade-capable priority 1001 and avoid an
  exact-version freeze. Mmdebstrap's setup-hook phase guarantees that the preference exists before
  package resolution; YAML mapping order does not. The focused consumer and image suites passed
  (`59 passed`). Ruff, YAML parsing, extracted setup-hook shell syntax, image script shell syntax
  and `git diff --check` passed.
- Simplification pass: Added one three-field APT preference. There is no package download hook,
  copied firmware blob, kernel pin, firmware alternative, second repository or runtime repair.
- Removal condition: Return `firmware-brcm80211` to normal Raspberry Pi repository resolution only
  after a Raspberry Pi package passes the complete physical gate without the local status-16
  regression.
- External evidence: Build both roles from the next exact candidate and record `uname -r`,
  `dpkg-query -W firmware-brcm80211` and the boot-time brcmfmac firmware version. Repeat the full
  clean-card gate. The console must associate with the coordinator under the unchanged required-PMF
  profile and complete every remaining network, TLS and kiosk check.
- Focused review: Claude Code Opus at medium effort found two required issues. The test treated YAML
  text order as execution order, and the first diagnosis overstated issue #58 as identical physical
  behavior. Both were accepted. The DPP wording, active image-runbook note and removal condition
  were accepted from optional observations. Extra provenance work, A/B image experiments and
  physical-checker expansion were rejected because the clean full gate supplies the required
  evidence.
- Resolution: Removed the text-order assertion and grounded setup timing in mmdebstrap semantics.
  The record now distinguishes the shared status-16 signature from peer behavior, includes the
  earlier successful rolling candidate and accurately describes Debian firmware capabilities.
- Final verification: The focused consumer and image suites passed (`59 passed`), including `41`
  image tests. Ruff, YAML parsing, extracted setup-hook shell syntax, every image script's shell
  syntax and `git diff --check` passed. Fresh Claude closure reproduced the focused checks and
  found no remaining required issue. Physical firmware selection and association remain at the
  clean-card gate.
- Accepted correction commit: `2827f7eaa2a69f5c1daf26910c4fe813a974b8e3`.
