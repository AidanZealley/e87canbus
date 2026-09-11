# Workstream 6: Build provisionable coordinator and console images

Status: closure review.

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
- Coordinator and console implement the exact IP, DHCP, WPA3/PMF, no-forwarding, TLS and service
  policy from the Wi-Fi contract.
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
- Accepted commit: `TBD`
