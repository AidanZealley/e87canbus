# Workstream 3: Coordinator image

Status: closure review.

## Task packet

### Outcome

The coordinator build produces a Pi 4 host image with the stable coordinator boot, CAN, UART,
network, service and security setup currently performed after cloning the repository.

### Scope

- Translate stable physical coordinator behavior from `scripts/setup_coordinator.sh` into
  `images/coordinator/`.
- Configure the three CAN overlays, UART3, interface naming and required packages.
- Install the existing coordinator units, proxy units, hotspot helper and sudoers policy from
  `deploy/` without copying their contents into a second source.
- Prepare the fixed Ethernet and hotspot infrastructure while leaving passwords and other
  installation inputs absent.
- Keep application services unable to start incorrectly when no application bundle exists.
- Add focused structural checks and documented boot expectations.

### Non-goals

Do not embed the application, hotspot password, device identity or operator account. Do not add
console files, simulator behavior, Pi 5 support or a new network abstraction.

### Initial ownership

- `images/coordinator/**`
- `hosts/tests/test_pi_image_build.py`, transferred from workstream 2
- This workstream record

Existing `deploy/` changes are integration exceptions. The orchestrator must assign them to this
stream and require the existing deployment tests.

### Required seams

Consume the accepted builder and common image contracts. Preserve the current Pi 4 mappings for
`kcan`, `ptcan`, `fcan` and `/dev/ttyAMA3`. Provisioning owns the hotspot password and application
bundle. The image owns only stable NetworkManager and system service prerequisites.

### Acceptance criteria

- The image contains only coordinator role assets and the exact current CAN and UART boot settings.
- The hotspot helper keeps its four-action sudo boundary and no secret enters the image.
- Coordinator services fail closed or remain inactive when required hardware or application state
  is absent.
- Structural tests agree with existing deployment and reliability checks.
- The manifest identifies the image as coordinator-only and Pi 4 compatible.

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

- Base commit: `87d6efff35798e4e87ba77f7023d8e9f465ea6cb`.
- Outcome: Added the coordinator role definition, stable Pi 4 hardware and network setup, canonical
  deployment asset installation and a fail-closed application boundary on top of the accepted
  common image.
- Files changed: `images/coordinator/image.yaml`, `images/coordinator/network-manager.cmds`,
  `images/coordinator/customize.sh`,
  `images/coordinator/e87canbus-controller-provisioning.conf`,
  `images/layer/e87-coordinator.yaml`, `hosts/tests/test_pi_image_build.py` and this record. The
  orchestrator approved the narrow `images/layer/e87-coordinator.yaml` integration exception
  because pinned `rpi-image-gen` discovers project layers below `SRCROOT/layer`. Its hook resolves
  the canonical assets as `$SRCROOT/../deploy`; no deployment file is copied into source or edited.
- Role mapping from current setup: The image appends the Pi 4 UART3, SPI and three MCP2515 overlays,
  removes the serial console and optional I2C0 overlay, installs the `spi0.0` to `kcan`, `spi1.1` to
  `ptcan` and `spi1.2` to `fcan` udev mapping, and enables the three canonical CAN units at 100,
  500 and 500 kbit/s. It installs Avahi, `iw`, sudo, the controller and constrained proxy units,
  the four-action hotspot helper and policy, and the default coordinator environment. The fixed
  `10.43.0.1/30` Ethernet profile autoconnects with no gateway or DNS. The `10.42.0.1/24` hotspot
  profile stays down and has no WPA key until provisioning supplies one.
- Verification: `sh -n images/coordinator/customize.sh`; `uv run pytest
  hosts/tests/test_pi_image_build.py hosts/tests/test_host_deployment.py
  hosts/tests/test_reliability.py` (`50 passed`); `uv run ruff check` for the same files; and `git
  diff --check` passed. Pinned `rpi-image-gen` commit
  `262d4df5a9f9d4133370465399a7958a7c22cdc7` passed metadata lint for the coordinator layer and
  resolved the complete coordinator pipeline after the common layer. Focused probes ran both
  NetworkManager commands through `nmcli --offline` and exercised the customization hook against
  a synthetic root, including canonical asset paths, modes, boot edits and Avahi configuration.
- Hardware checks deferred to workstream 5: Pi 4 overlay discovery, `/dev/ttyAMA3`, exact CAN SPI
  parent mappings and bitrates, fixed Ethernet state, hotspot provisioning and isolation, Avahi,
  helper policy, service state and application gating.
- Known limitations: The later provisioning work still owns the application bundle, hotspot
  password, operator account, host identity and the transition that removes the protected
  `unprovisioned` marker. Application and proxy units remain disabled in the reusable image.
- Specification drift: None.

## Independent review

- Reviewer: Codex (`gpt-5.6-sol`, fresh workstream reviewer)
- Verdict: Changes required.
- Required findings:
  1. The image does not preserve the current fail-closed UART check. The legacy coordinator setup
     refuses to install or start the controller unless `/dev/ttyAMA3` exists, but the new systemd
     drop-in checks only the provisioning marker and application executable. In a physical profile,
     a missing UART makes the panel worker fault and stop while the controller process continues.
     Gate controller startup on the fixed panel UART, or add an equivalent systemd device
     dependency, and protect that behavior with a focused structural check. Keep the existing CAN
     device requirements and provisioning gates intact.
- Optional observations: None. The role remains coordinator-only. It installs the canonical
  deployment assets with the intended modes, keeps the helper's exact four-command sudo grant and
  leaves the controller and proxy sockets disabled until provisioning. The two generated
  NetworkManager keyfiles preserve the fixed isolation rules, contain no WPA key and leave the
  hotspot inactive; the password can be inserted later without rebuilding the profile.
- Questions for orchestrator: None.
- Evidence: `sh -n images/coordinator/customize.sh`; `uv run pytest
  hosts/tests/test_pi_image_build.py hosts/tests/test_host_deployment.py
  hosts/tests/test_reliability.py` (`50 passed`); `uv run ruff check` for the same files; `git diff
  --check`; pinned `ig metadata --lint images/layer/e87-coordinator.yaml`; inspection of the pinned
  layer plan and NetworkManager hook; independent `nmcli --offline` rendering of both profiles;
  comparison with `scripts/setup_coordinator.sh`, the canonical deployment assets and the physical
  panel startup path.

## Resolution

- Finding dispositions: Accepted the required UART finding. The existing controller drop-in now
  requires and starts after `dev-ttyAMA3.device`, so systemd cannot start the controller when the
  fixed panel UART is absent. The provisioning marker and application executable conditions remain
  unchanged. A focused structural assertion fixes both the dependency and its ordering.
- Simplification/deletion pass: Added two declarations to the existing drop-in. No probe service,
  startup script, retry path or new hardware abstraction was needed.
- Final verification: `sh -n images/coordinator/customize.sh`; `uv run pytest
  hosts/tests/test_pi_image_build.py hosts/tests/test_host_deployment.py
  hosts/tests/test_reliability.py` (`50 passed`); `uv run ruff check` for the same files; `git diff
  --check`; and a focused `systemd-analyze verify` of the controller drop-in passed.

## Closure review

- Verdict: Accepted. The UART correction resolves the required finding without introducing a
  release-blocking defect.
- Remaining required findings: None. `dev-ttyAMA3.device` is the correct systemd device-unit name
  for `/dev/ttyAMA3`. `Requires` and `After` make a missing panel UART block controller activation,
  while the existing unprovisioned-marker and executable conditions still block an incomplete
  application. The canonical controller unit and all three CAN units retain their existing
  ordering and required-device relationships. The image still leaves the controller and proxy
  sockets disabled for later provisioning.
- Closure verification: Focused `systemd-analyze verify` of the assembled controller drop-in and
  three CAN units accepted the dependency graph; its only warning was the deliberately absent
  application executable in the review checkout. `systemd-escape --path --suffix=device
  /dev/ttyAMA3` returned `dev-ttyAMA3.device`. `uv run pytest
  hosts/tests/test_pi_image_build.py hosts/tests/test_host_deployment.py
  hosts/tests/test_reliability.py` passed (`50 passed`); Ruff, shell syntax and `git diff --check`
  passed.
- Accepted commit: `TBD`
