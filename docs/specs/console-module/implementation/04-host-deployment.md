# Workstream 4: Deploy the coordinator and console as separate hosts

Status: accepted.

## Task packet

### Outcome

Two direct Pi 4 setup scripts install only their host's CAN, application, frontend and service
requirements. The coordinator is headless and exposes its loopback app through constrained hotspot
and console-link proxies. The console starts one listen-only K-CAN reader and its local kiosk over
the fixed, non-routing Ethernet link.

### Scope

- Replace `scripts/setup_pi.sh` with `scripts/setup_coordinator.sh` and
  `scripts/setup_console.sh`, starting from the existing script and trimming each role.
- Extract only substantial identical shell operations into a small helper; retain readable linear
  setup phases in both entry points.
- Coordinator setup preserves the three validated CAN mappings, controller/API, persistence,
  hotspot, UART coordinator panel and `car`/`bench`/`simulator` runtime profile semantics. It builds
  and installs only the coordinator frontend and removes kiosk/display installation.
- Console setup validates Pi 4 and the first 2-CH CAN HAT+ controller, maps it to logical `kcan`,
  configures 100 kbit/s kernel listen-only mode, builds/installs only the console frontend and
  installs the accepted console service and kiosk. It neither installs nor enables the second CAN
  controller.
- Add or adjust udev, systemd, environment and kiosk files for explicit host ownership, startup
  ordering, clean shutdown, loopback binding and correct frontend paths.
- Configure `10.43.0.1/30` on coordinator Ethernet and `10.43.0.2/30` on console Ethernet with no
  gateway, DNS, default route or forwarding.
- Add a coordinator console-link port-80 proxy bound only to `10.43.0.1` while preserving the
  hotspot-only `10.42.0.1` proxy and loopback application binding.
- Permit the fixed production console browser origin for coordinator HTTP and Socket.IO without
  broadening other origins or interfaces.
- Update deployment/configuration tests and CI shell checks for both roles.
- Delete obsolete combined-role setup, coordinator kiosk units/configuration and old frontend path
  assumptions instead of retaining aliases.

### Non-goals

- Supporting arbitrary host-role combinations, non-Pi hardware or configurable network topologies.
- Adding authentication, TLS, routing, DHCP or internet sharing.
- Changing coordinator controller profiles or CAN transmit grants.
- Enabling console CAN transmission or its unused HAT+ channel.
- Selecting or qualifying automotive power protection.
- Running commands against a live vehicle, production database or installed Pi during this
  workstream.
- Updating runbooks and narrative documentation; workstream 5 owns them.

### Initial ownership

- `scripts/setup_pi.sh` replaced by `scripts/setup_coordinator.sh`, `scripts/setup_console.sh` and
  at most one narrowly scoped shared helper
- Setup-adjacent scripts whose invocation paths change
- `deploy/systemd/**`, `deploy/kiosk/**`, `deploy/udev/**`, `deploy/bin/**` and deployment examples
- Host CLI/CORS configuration only where required to consume the accepted deployment seam
- Frontend workspace build configuration only for fixed production origins and accepted dist paths
- `.github/workflows/ci.yml` and focused host deployment/configuration tests

Do not edit vehicle-control domain behaviour, console live-contract shape or unrelated UI.

### Required seams

- Production ports, addresses, origins, CAN mapping and script names match [plan.md](plan.md).
- Coordinator application remains `127.0.0.1:8000`; no direct `0.0.0.0` binding is allowed.
- Console application remains `127.0.0.1:8000`; kiosk opens its local root, never the coordinator
  as its document origin.
- The coordinator console-link and hotspot proxies cannot expose through another interface or
  create forwarding between their subnets.
- Console `kcan` resolves to the HAT+ first controller (`spi1.1` with the accepted board jumper
  allocation); the second controller (`spi1.2`) has no enabled CAN bootstrap service.
- The console CAN service receives only the listen-only interface and contains no setup option that
  enables transmission.
- Both setup scripts fail before application startup when model, overlay, interface or SPI mapping
  validation fails.
- Rerunning a setup script converges on its own role and removes obsolete combined-role units it
  previously installed.

### Acceptance criteria

- Static tests demonstrate the exact coordinator and console service/install sets, targeted
  frontend build commands and removal of the old setup entry point.
- Unit/configuration tests verify loopback binding, fixed origin policy, exact proxy addresses,
  no-forwarding network configuration and listen-only console CAN command.
- Coordinator setup neither installs nor enables a kiosk; console setup neither installs the
  controller, persistence, hotspot, panel, PT-CAN or F-CAN services.
- Console service starts only after its K-CAN bootstrap and serves the locally built console app.
- Existing coordinator hotspot hardening, service-user boundaries and three-CAN validation remain
  protected.
- Shell scripts parse cleanly and no obsolete combined-role unit or compatibility wrapper remains.
- Hardware-dependent commands and power checks are clearly recorded as pending rather than claimed
  from static tests.

### Targeted verification

```bash
bash -n scripts/*.sh deploy/bin/* deploy/kiosk/*.sh
uv run pytest -q hosts/tests/test_deployment_profiles.py hosts/tests/test_cli_main.py hosts/tests/test_config.py hosts/tests/test_hotspot.py hosts/tests/test_networkmanager_hotspot.py hosts/tests/test_architecture.py
uv run ruff check hosts scripts
cd frontend
pnpm --filter ./apps/coordinator build
pnpm --filter ./apps/console build
```

Run every focused setup/systemd/network test introduced by this workstream. Record as pending on
real hardware: both blank-Pi runs, HAT+ SPI mapping, physical listen-only observation, Ethernet
isolation, kiosk/touch startup, combined Pi/screen current demand and vehicle power behaviour.

## Implementation handoff

- Base commit: `927b4a3fe6313e7401bab21797f1c1335cec5cd7`
- Outcome: Replaced the combined Pi installer with direct coordinator and console installers. The
  coordinator retains its three validated CAN interfaces, controller profiles, persistence,
  panel and hardened hotspot while running headless behind interface-bound hotspot and console-link
  proxies. The console installs one kernel-listen-only `kcan`, its local service/frontend and its
  own kiosk on the fixed non-routing Ethernet link.
- Files changed: Added `scripts/setup_coordinator.sh`, `scripts/setup_console.sh` and one small
  shared host-setup helper; updated the adjacent capture hint and CI shell parsing. Split CAN udev
  naming by host; added console service/CAN/environment/kiosk files and explicit coordinator proxy
  pairs; updated the controller environment/unit for the coordinator artifact and fixed console
  origin. Removed `scripts/setup_pi.sh` and the obsolete generic kiosk, CAN-naming and proxy files.
  Updated focused deployment assertions in `hosts/tests/test_reliability.py` and added
  `hosts/tests/test_host_deployment.py` for the complete static role boundary.
- Decisions: Kept controller `car`/`bench`/`simulator` as coordinator runtime profiles rather than
  introducing host-role configuration. Shared only checkout, package, account, boot-line and fixed
  Ethernet mechanics. Used NetworkManager manual `/30` connections with empty gateway/DNS,
  `never-default` and ingress-policy blackholes; the existing hotspot ingress blackhole and the new
  Ethernet rule prevent forwarding between interfaces. The console HAT+ exposes only `spi1.1` as
  `kcan`; its `spi1.2` overlay, udev name and service are absent. The console build fixes the
  coordinator origin at `http://10.43.0.1`, while its kiosk remains rooted at
  `http://127.0.0.1:8000/` and that exact document origin is the coordinator CORS/Socket.IO grant.
- Verification: `bash -n scripts/*.sh deploy/bin/* deploy/kiosk/*.sh` passed. The packet tests plus
  the new deployment and inherited reliability tests passed, 121 total, using
  `PYTHONPATH=hosts/src .venv/bin/pytest` because `uv` is unavailable in this shell. Ruff passed for
  `hosts` and `scripts`; both filtered production frontend builds passed, and output inspection
  confirmed only the console build embeds `http://10.43.0.1`. `systemd-analyze verify` accepted the
  units and reported only the expected absent target-host executables (`cage` and `/opt/e87canbus`
  entry points) in this development environment. `git diff --check` passed.
- Hardware/external validation pending: Both blank-Pi installer runs; Pi 4 boot-overlay and HAT+
  `spi1.1` mapping validation; physical kernel listen-only observation and confirmation that the
  unused channel stays inactive; direct-Ethernet addressing, isolation and both constrained
  proxies; kiosk/touch startup; combined Pi/screen peak-current capacity; and vehicle power,
  grounding, transceiver, termination and wiring checks.
- Specification drift: None.

## Independent review

- Reviewer: Codex (`/root/ws4_reviewer`)
- Verdict: Changes required. The role-specific installers, exact installed service sets, frontend
  artifacts, loopback application binds, interface-bound proxies, fixed non-routing `/30` link,
  coordinator hotspot boundary, console `spi1.1` naming and kernel listen-only command, absent
  `spi1.2` overlay/name/service, unit ordering and service-user boundaries otherwise satisfy the
  packet. Independent checks passed 121 focused deployment/configuration/reliability tests, Ruff,
  shell parsing, both role-filtered production builds, `systemd-analyze verify` (apart from the
  expected target-host executables absent in this checkout), and `git diff --check`. Output
  inspection found `http://10.43.0.1` only in the configured console build. No live service,
  network, CAN or hardware command was run.
- Required findings: The controller unit's fixed console-origin argument removes the two existing
  approved development origins instead of adding the console origin to them. The unit always
  supplies `--cors-origin ${E87CANBUS_CONSOLE_ORIGIN}`, and `create_app` treats any explicit origin
  sequence as a complete replacement for `DEFAULT_CORS_ORIGINS`. Consequently deployed `bench`
  and `simulator` profiles no longer accept their existing `http://localhost:5173` or
  `http://127.0.0.1:5173` HTTP/Socket.IO clients, contrary to the frozen requirement to permit the
  fixed console origin *in addition to* approved development origins and to preserve controller
  profile semantics. A direct preflight check against an explicitly configured simulator app
  accepted `http://127.0.0.1:8000` but returned `400` with no allow-origin header for both approved
  development origins. Preserve exactly those two existing development origins plus the exact
  production console document origin, without a wildcard or another interface exposure, and add a
  focused configuration/behaviour test that protects both the allowed set and rejection of an
  unrelated origin.
- Optional observations: None.
- Questions for orchestrator: None.

## Resolution

- Finding dispositions: Accepted and resolved the origin regression. The deployed controller now
  repeats `--cors-origin` for exactly `http://localhost:5173`,
  `http://127.0.0.1:5173` and the fixed console document origin
  `http://127.0.0.1:8000`, preserving the approved development clients while adding production
  console access for both HTTP and Socket.IO.
- Simplification/deletion pass: Kept the correction in the existing controller environment and
  unit rather than adding runtime defaults, origin parsing, a wildcard or another policy layer.
  One focused test reads that deployed environment as the single source for the exact set and
  exercises the existing HTTP and Socket.IO origin policies.
- Final verification: Shell parsing, Ruff and `git diff --check` passed. The complete focused
  deployment/configuration set passed all 125 tests through the accepted local environment
  equivalent. For each of the three deployed origins, real HTTP preflight and Engine.IO polling
  handshake requests succeeded; an unrelated origin returned `400` with no HTTP allow-origin
  header and its Engine.IO handshake also returned `400`. `systemd-analyze verify` accepted the
  changed unit and reported only the previously recorded target-host executables absent locally.

## Closure review

- Verdict: Pass. The deployed controller now repeats the existing CLI option for exactly the two
  approved development origins and the fixed console document origin. The focused tests derive the
  deployed values from the environment file, separately pin the exact three-value set and argument
  count, and prove successful HTTP preflights and Engine.IO polling handshakes for every allowed
  origin while rejecting an unrelated origin through both transports. The fix changes only the
  existing environment/unit seam and its focused tests: it adds no wildcard, new interface bind,
  runtime origin parser or policy abstraction. Independent closure checks passed all 54 focused
  host-deployment and simulator-API tests, Ruff, shell parsing, `systemd-analyze verify` (with only
  the expected absent target-host executable warning) and `git diff --check`. No live state was
  touched.
- Remaining required findings: None.
- Accepted commit: `8008b568fea474baf31db2a4f9bac59d7aefced5`
