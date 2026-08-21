# Workstream 5: Role-image hardware acceptance

Status: closure review.

## Task packet

### Outcome

The repository has a concise image build and inspection runbook, and recorded evidence shows that
both role images build on the M1 Pro, flash through Raspberry Pi Imager and boot on Raspberry Pi 4.

### Scope

- Add `images/README.md` with prerequisites, both build commands, output and manifest inspection,
  Raspberry Pi Imager steps, temporary access setup and exact per-role boot checks.
- State what a successful host-image boot proves and what later provisioning must still supply.
- Run the non-hardware integration checks before handoff.
- Give Aidan one checkpoint commit and collect results for both roles.
- Route each failure to the workstream that owns it. Record the correction and focused closure.
- Update stale image-building and deployment documentation within the approved feature boundary.

### Non-goals

Do not add an automated SD writer, provisioning CLI, application bundle, secrets, vehicle testing or
new image behavior merely to make the runbook easier.

### Initial ownership

- `images/README.md`
- Image-building references in `docs/setup.md` and `deploy/README.md`
- `hosts/tests/test_pi_image_build.py`, transferred from workstream 4
- This workstream record

Implementation defects return to workstreams 1 through 4. The orchestrator assigns exact file
ownership before any correction begins.

### Required seams

The runbook uses only the two public build commands and Raspberry Pi Imager. Temporary access must
not alter the reusable image or commit credentials. Generated artifacts stay outside Git.

### Acceptance criteria

- The runbook can be followed from a clean checkout on the M1 Pro.
- It names expected artifact and manifest locations without assuming a hard-coded build identifier.
- It has exact checks for OS, architecture, Pi model, role configuration and expected service state.
- Aidan records command outcomes, digests, flash results and Pi boot checks for both images.
- Failures are resolved and closed by their original owners.
- The final worktree contains no image, cache, credential or unrelated change.

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

On the M1 Pro:

```bash
./scripts/build-pi-image coordinator
./scripts/build-pi-image console
```

On each Pi before role-specific checks:

```bash
uname -m
grep VERSION_CODENAME /etc/os-release
tr -d '\0' < /proc/device-tree/model
systemctl --failed --no-pager
```

## Implementation handoff

- Base commit: `c07f28cc387e832f84cddd63467fc0568165464a`.
- Outcome: Added the clean-M1 build, artifact inspection, Imager and physical Pi 4 checkpoint
  runbook for both accepted role images. It uses a local systemd debug shell for temporary test
  access, then requires its removal before the card is reused.
- Files changed: `images/README.md`, image references in `docs/setup.md` and `deploy/README.md`,
  `hosts/tests/test_pi_image_build.py` and this record.
- Verification: `uv run pytest hosts/tests/test_pi_image_build.py
  hosts/tests/test_host_deployment.py hosts/tests/test_reliability.py` (`59 passed`); `uv run ruff
  check` for the same files; and `git diff --check` passed.
- Coordinator artifact, digest, flash and boot result: Pending Aidan's hardware checkpoint.
- Console artifact, digest, flash and boot result: Pending Aidan's hardware checkpoint.
- Corrections routed to prior owners: None before the checkpoint.
- Known limitations: The unprovisioned image has no application bundle or operator account. The
  console checkpoint can prove that the display stack, DRM and touchscreen input exist and that
  application units stay gated. It cannot launch the kiosk or exercise application health checks
  until the later provisioning CLI supplies the application and operator inputs. CAN traffic,
  paired-host Ethernet and vehicle-safe wiring remain installation checks.
- Specification drift: None. Raspberry Pi Imager offered no customisation for the custom base
  image, so the runbook does not rely on Imager credentials. The test-card-only
  `systemd.debug_shell=1` method creates no account, key, password or provisioning format and
  leaves the reusable image unchanged. This resolves the specification's delegated test-access
  decision without changing image behavior.

## Independent review

- Reviewer: Codex (`gpt-5.6-sol`, fresh workstream reviewer).
- Verdict: Changes required.
- Required findings:
  1. The console touchscreen check matches only device descriptions containing `touchscreen`,
     `ft5` or `goodix`. Neither the specification nor the accepted console workstream fixes a
     touchscreen controller or kernel device name, so a working intended touchscreen can fail the
     checkpoint while an unrelated input description containing one of those strings can pass it.
     Detect an input device that udev classifies with `ID_INPUT_TOUCHSCREEN=1`, or use another
     model-independent capability check, and update the focused runbook test to protect that exact
     check.
- Optional observations: On Apple keyboards whose top row controls media rather than function
  keys, virtual-terminal switching also requires the Fn key. Adding that note would save a small
  troubleshooting detour, but it does not block acceptance.
- Questions for orchestrator: None.
- Evidence: The dynamic manifest selection follows the newest role-specific JSON file, derives the
  matching image path and verifies its SHA-256 digest before flashing. The pinned
  `rpi-image-gen` `simple_dual` template labels the FAT filesystem `BOOT` and mounts it at
  `/boot/firmware`, so both cmdline paths are correct. Its pinned systemd and OpenSSH layers install
  the debug generator and enforce `AuthenticationMethods publickey`; the image removes UID 1000
  and supplies no authorized key. The one-line cmdline edit changes only the verified test card,
  and the documented negative check, sync and poweroff remove the unauthenticated shell before
  reuse. Coordinator and console service, CAN, network and application-gating expectations agree
  with their accepted image definitions. The runbook does not create a provisioning format or
  modify an artifact or repository file. Local documentation links resolve. `uv run pytest
  hosts/tests/test_pi_image_build.py hosts/tests/test_host_deployment.py
  hosts/tests/test_reliability.py` passed (`59 passed`); Ruff on the same files and `git
  diff --check` passed. Hardware execution remains pending.

## Resolution

- Finding dispositions: Accepted the required touchscreen finding. The console check now scans
  input event devices for udev's model-independent `ID_INPUT_TOUCHSCREEN=1` capability instead of
  matching controller-name substrings. The focused test fixes that exact property query and
  rejects the old heuristic. Accepted the optional Apple keyboard note and documented the Fn key
  needed when the top row controls media.
- Simplification/deletion pass: Kept the check in the existing console command block with one
  short loop over input event devices. It needs no controller list, extra package or helper script.
- Final verification: `uv run pytest hosts/tests/test_pi_image_build.py
  hosts/tests/test_host_deployment.py hosts/tests/test_reliability.py` (`59 passed`); `uv run ruff
  check` for the same files; and `git diff --check` passed.

## Closure review

- Verdict: Accepted for the hardware checkpoint. The remediation resolves the required finding
  without introducing a release-blocking defect.
- Remaining required findings: None. The POSIX-shell loop handles an unmatched
  `/dev/input/event*` glob, queries each existing event device through `udevadm`, stops only on the
  exact `ID_INPUT_TOUCHSCREEN=1` property and fails the following assertion when no touchscreen is
  classified. It runs as written from the documented root debug shell and needs no new package.
  The focused test requires the exact udev property query and rejects the removed controller-name
  heuristic. The Fn note is scoped to Apple keyboards whose top row controls media.
- Closure verification: The remediated shell block passed `sh -n`; `udevadm info
  --query=property --name=/dev/null` confirmed the documented command form. `uv run pytest
  hosts/tests/test_pi_image_build.py hosts/tests/test_host_deployment.py
  hosts/tests/test_reliability.py` passed (`59 passed`); Ruff on the same files and `git
  diff --check` passed. Coordinator and console builds, flashes and Pi checks remain the external
  acceptance gate.
- Accepted commit: Pending the checkpoint candidate and successful external hardware evidence.
