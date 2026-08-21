# Workstream 4: Console image

Status: accepted.

## Task packet

### Outcome

The console build produces a Pi 4 host image with the stable console CAN, display, kiosk, Ethernet
and service setup currently performed after cloning the repository.

### Scope

- Translate stable behavior from `scripts/setup_console.sh` into `images/console/`.
- Configure only the first HAT+ controller at `spi1.1` and preserve the car-profile listen-only
  default.
- Install the existing console units, environment example, udev rules and kiosk launcher from
  `deploy/` without forking their contents.
- Install the headless Lite image display stack required for Cage and Chromium.
- Prepare the fixed console Ethernet link while leaving installation inputs absent.
- Keep application and kiosk startup safe when no application bundle exists.
- Add focused structural checks and documented boot expectations.

### Non-goals

Do not embed the console application, operator account or device identity. Do not configure the
second CAN controller, coordinator services, desktop display managers or Pi 5 support.

### Initial ownership

- `images/console/**`
- `hosts/tests/test_pi_image_build.py`, transferred from workstream 3
- This workstream record

Existing `deploy/` changes require the same integration exception and deployment checks as
workstream 3.

### Required seams

Consume the accepted builder and common contracts. Preserve `kcan` at `spi1.1`, the disabled second
channel, `10.43.0.2/30`, local application binding and the existing kiosk health-check behavior.

### Acceptance criteria

- The image contains only console role assets and configures one receive-side CAN controller.
- Chromium and Cage are installed during the image build, never on first boot.
- The kiosk cannot race or bypass the local application health check.
- Structural tests agree with existing deployment and reliability checks.
- The manifest identifies the image as console-only and Pi 4 compatible.

### Targeted verification

```bash
uv run pytest \
  hosts/tests/test_pi_image_build.py \
  hosts/tests/test_host_deployment.py \
  hosts/tests/test_reliability.py
uv run ruff check \
  hosts/tests/test_pi_image_build.py \
  hosts/tests/test_host_deployment.py \
  hosts/tests/test_reliability.py
```

## Implementation handoff

- Base commit: `50681f6058409e061814588cbbef5bb9ba95002e`.
- Outcome: Added the console role definition, its fixed Pi 4 CAN and Ethernet setup, the Lite
  display stack, canonical console deployment assets and provisioning gates on top of the
  accepted common image.
- Files changed: `images/console/image.yaml`, `images/console/network-manager.cmds`,
  `images/console/customize.sh`, `images/console/e87canbus-console-provisioning.conf`,
  `images/console/e87canbus-console-kiosk-provisioning.conf`,
  `images/layer/e87-console.yaml`, `hosts/tests/test_pi_image_build.py` and this record. The
  orchestrator approved the narrow `images/layer/e87-console.yaml` integration exception because
  pinned `rpi-image-gen` discovers project layers below `SRCROOT/layer`. Its hook resolves the
  canonical assets as `$SRCROOT/../deploy`; no deployment file was copied into source or edited.
- Role mapping from current setup: The image installs only the `spi1.1` MCP2515 overlay and its
  `kcan` udev name, removes coordinator CAN and UART settings, and enables the canonical console
  CAN unit with the existing 100 kbit/s car-profile listen-only default. It installs Cage,
  Chromium, Chromium's sandbox, systemd PAM seat integration and Plymouth during the image build.
  It applies the quiet kiosk boot parameters and installs the canonical console application unit,
  Cage unit, launcher, environment example and both udev rules. The fixed `10.43.0.2/30` Ethernet
  profile autoconnects without a gateway or DNS and retains the ingress blackhole. The image
  enables only the CAN bootstrap. Application and kiosk units remain disabled and each checks the
  protected unprovisioned marker; the application also requires its executable, while the kiosk
  requires the built console frontend and still uses the canonical launcher's local health check.
- Verification: `sh -n images/console/customize.sh`; `uv run pytest
  hosts/tests/test_pi_image_build.py hosts/tests/test_host_deployment.py
  hosts/tests/test_reliability.py` (`57 passed`); `uv run ruff check` for the same files; and `git
  diff --check` passed. Pinned `rpi-image-gen` commit
  `262d4df5a9f9d4133370465399a7958a7c22cdc7` passed metadata lint for the console layer and
  resolved the complete console pipeline after the common layer. Focused probes ran the
  NetworkManager command through `nmcli --offline`, exercised the customization hook against a
  synthetic root, compared installed runtime assets with their canonical sources, and checked the
  assembled units with `systemd-analyze verify`. All five image packages exist in the pinned
  Debian arm64 snapshot.
- Hardware checks deferred to workstream 5: Pi 4 overlay discovery, the absent second CAN channel,
  100 kbit/s listen-only state, fixed Ethernet policy, touchscreen input, Cage and Chromium, local
  health gating, service state and application gating.
- Known limitations: Provisioning still owns the application bundle, operator account and device
  identity, then removes the protected marker after validation. The canonical Cage unit keeps its
  `KIOSK_USER_PLACEHOLDER` and remains disabled until provisioning installs that operator input.
  The reusable image contains no desktop manager and cannot demonstrate the kiosk before those
  inputs exist.
- Specification drift: None.

## Independent review

- Reviewer: Codex (`gpt-5.6-sol`, fresh workstream reviewer).
- Verdict: Accepted. No required defects found.
- Required findings: None. The image configures one MCP2515 controller at `spi1.1`, gives only
  that device the `kcan` name and enables only the canonical 100 kbit/s console CAN unit. Its
  environment keeps the car-profile `listen-only=on` default. The hook removes the coordinator
  `spi0.0`, `spi1.2`, I2C0 and UART settings without installing coordinator assets. The rendered
  NetworkManager profile fixes `eth0` at `10.43.0.2/30`, has no gateway or DNS, cannot become a
  default route and sends ingress forwarding through table 501's blackhole.

  The Lite display package set is complete under the pinned base's
  `APT::Install-Recommends=false` policy. `cage` pulls the Wayland, Xwayland, EGL, Mesa and Pi
  `v3d`/`vc4` DRI chain. The base locale layer pulls `kbd`, which supplies the kiosk unit's
  `/usr/bin/chvt`. The layer explicitly adds `chromium-sandbox`, since Chromium only recommends
  it, and `libpam-systemd`, which provides the logind seat and PAM session used by Cage. Plymouth,
  Chromium, Cage and their runtime dependencies are installed during image construction.

  The customization hook installs byte-identical canonical units, environment, udev rules and
  launcher with modes `0644`, `0640`, `0644` and `0755` respectively. Only the CAN bootstrap is
  enabled. Both application units remain disabled and require the protected provisioning marker
  to be removed. The application also requires its executable; the kiosk requires the built
  frontend, requires the application unit and reaches Chromium only through the canonical
  launcher's local liveness loop. The unresolved `KIOSK_USER_PLACEHOLDER` is a valid but absent
  systemd user. It cannot start Cage and is safe while the unit is disabled. Later provisioning
  must replace it and install the operator before removing the marker and enabling the unit.
- Optional observations: None. The console role remains isolated from coordinator services,
  credentials, application contents, build tools and desktop display managers. The pinned layer
  plan resolves `e87-common` before `e87-console`, and the role config retains the accepted Pi 4,
  Raspberry Pi OS Lite Trixie and manifest contracts.
- Questions for orchestrator: None.
- Evidence: `sh -n images/console/customize.sh`; `uv run pytest
  hosts/tests/test_pi_image_build.py hosts/tests/test_host_deployment.py
  hosts/tests/test_reliability.py` (`57 passed`); Ruff on those files; `git diff --check`; pinned
  `ig metadata --lint images/layer/e87-console.yaml`; pinned full console pipeline resolution;
  independent `nmcli --offline` rendering; a synthetic-root hook run with canonical asset
  comparisons and mode checks; `systemd-analyze verify` of the assembled units; pinned Debian
  snapshot package metadata and dependency-chain inspection.

## Resolution

- Finding dispositions: No required, optional or question findings were raised, so no remediation
  was needed.
- Simplification/deletion pass: Kept one role layer, one direct customization hook and one offline
  NetworkManager command. Runtime assets remain canonical in `deploy/`; the role adds only the two
  provisioning conditions that cannot live in the legacy deployment path. No operator account,
  desktop manager, role abstraction or first-boot executable was added.
- Final verification: `sh -n images/console/customize.sh`; `uv run pytest
  hosts/tests/test_pi_image_build.py hosts/tests/test_host_deployment.py
  hosts/tests/test_reliability.py` (`57 passed`); `uv run ruff check` for the same files; pinned
  console layer metadata lint; YAML parsing; and `git diff --check` passed.

## Closure review

- Verdict: Accepted. The independently reviewed diff had no required findings, no remediation was
  needed and the frozen candidate contains no release-blocking defect.
- Remaining required findings: None. The role remains console-only, preserves the accepted
  common and builder contracts, gates the unprovisioned application and kiosk, and leaves physical
  CAN, Ethernet, display and kiosk behavior to the workstream 5 hardware checkpoint.
- Closure verification: `sh -n images/console/customize.sh`; `uv run pytest
  hosts/tests/test_pi_image_build.py hosts/tests/test_host_deployment.py
  hosts/tests/test_reliability.py` (`57 passed`); Ruff on those files; and `git diff --check`
  passed.
- Accepted commit: `677c3ae` (`Add console Raspberry Pi image`).
