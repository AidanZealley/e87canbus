# Workstream 3: Coordinator image

Status: not started.

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
