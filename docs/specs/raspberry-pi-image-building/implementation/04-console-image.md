# Workstream 4: Console image

Status: not started.

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

- Base commit: `TBD`
- Outcome: `TBD`
- Files changed: `TBD`
- Role mapping from current setup: `TBD`
- Verification: `TBD`
- Hardware checks deferred to workstream 5: `TBD`
- Known limitations: `TBD`
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
