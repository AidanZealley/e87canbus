# Workstream 4: Deploy the coordinator and console as separate hosts

Status: not started.

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

- Base commit: `TBD`
- Outcome: `TBD`
- Files changed: `TBD`
- Decisions: `TBD`
- Verification: `TBD`
- Hardware/external validation pending: `TBD`
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

