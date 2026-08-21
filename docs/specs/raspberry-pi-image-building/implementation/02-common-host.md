# Workstream 2: Common host image

Status: accepted.

## Task packet

### Outcome

Coordinator and console builds share one auditable host definition for stable OS packages,
runtimes, service ownership, filesystem layout and the later first-boot handoff.

### Scope

- Derive common requirements from `scripts/setup_host_common.sh`, both role setup scripts and
  existing `deploy/` assets.
- Add the smallest shared `rpi-image-gen` configuration needed by both hosts.
- Install stable runtime packages and create service users and directories with fixed ownership.
- Define the versioned image side of the first-boot handoff without defining final application,
  credential or secret bundle formats.
- Prevent package installation, dependency resolution and application builds on first boot.
- Add structural tests for shared contents and secret exclusions.

### Non-goals

Do not configure role-specific CAN, UART, hotspot, Ethernet, kiosk or application services. Do not
delete the current setup scripts, install a repository clone or create a generic image layer system.

### Initial ownership

- `images/common/**`
- `hosts/tests/test_pi_image_build.py`, transferred from workstream 1
- This workstream record

Changes to the builder or existing deployment assets require orchestrator approval and return to
their owner when practical.

### Required seams

Common files expose explicit inputs to the two role definitions. Existing files in `deploy/`
remain the source for runtime units, udev rules, helpers and kiosk scripts. Record any temporary
duplication with the legacy setup scripts.

### Acceptance criteria

- Both role definitions can consume one common definition without role conditionals spread through
  shared files.
- Common packages and filesystem state map to current setup behavior.
- No first-boot path runs `apt`, Git, `uv`, `pnpm` or frontend compilation.
- No key, password, user identity or final provisioning bundle format is embedded.
- Tests state the frozen first-boot boundary used by later role work.

### Targeted verification

```bash
bash -n scripts/build-pi-image
uv run pytest hosts/tests/test_pi_image_build.py hosts/tests/test_host_deployment.py
uv run ruff check hosts/tests/test_pi_image_build.py hosts/tests/test_host_deployment.py
```

## Implementation handoff

- Base commit: `56fdbabbbefb574061a6a4488c4a254db348acfd`
- Outcome: Added one role-neutral Pi 4 configuration and one shared `rpi-image-gen` layer for
  runtime packages, key-only SSH, the service account and filesystem state.
- Files changed: `images/common/image.yaml`, `images/layer/e87-common.yaml`,
  `images/layer/e87-common.rootfs-overlay/usr/share/e87canbus/provisioning-interface`,
  `hosts/tests/test_pi_image_build.py` and this record. The orchestrator approved the narrow
  `images/layer/**` exception because pinned `rpi-image-gen` discovers project layers only below
  `SRCROOT/layer`; keeping the file there avoids a builder override or project-specific loader.
- Common package and filesystem decisions: The image installs `ca-certificates`, `can-utils`,
  `curl`, `iproute2` and Python 3, then uses upstream NetworkManager and IWD layers. It
  creates the system `e87canbus` user and group with a nologin shell, `/opt/e87canbus` as
  `root:e87canbus` mode `0750`, and `/etc/e87canbus` plus `/var/lib/e87canbus` as
  `e87canbus:e87canbus` mode `0750`, matching the current setup script. After upstream SSH setup,
  it removes the default login account and private group without creating an operator identity.
  Git, compilers, Node, npm, pip, `uv` and `pnpm` stay out of the runtime image.
- First-boot boundary: `/usr/share/e87canbus/provisioning-interface` contains version `1`, and the
  image creates `/var/lib/e87canbus-provisioning/unprovisioned` below a root-owned mode `0700`
  directory. Role application units must remain gated while that marker exists. The future
  validated provisioning consumer owns removing it after successful application and provisioning
  data installation. This freezes no boot-partition path, payload schema, credential format or
  secret transport.
- Verification: `bash -n scripts/build-pi-image`; `uv run pytest
  hosts/tests/test_pi_image_build.py hosts/tests/test_host_deployment.py` (`34 passed`); `uv run
  ruff check hosts/tests/test_pi_image_build.py hosts/tests/test_host_deployment.py`;
  `git diff --check`; pinned `ig metadata --lint images/layer/e87-common.yaml`; and a pinned
  `ig pipeline` resolution of the complete common configuration all passed.
- Known limitations or external checks: No provisioning consumer exists because its bundle and
  secret formats remain open in the provisioning specification. Role layers still need to install
  and gate their units. Docker image construction and Pi behavior remain for the final role-image
  checkpoint.
- Specification drift: None.

## Independent review

- Reviewer: Codex (`gpt-5.6-sol`, fresh workstream reviewer)
- Verdict: Changes required.
- Required findings:
  1. The common configuration includes upstream `openssh-server`, whose `device-user-admin`
     dependency resolves `IGconf_device_user1=pi` and creates that login account. A locked account
     with no key is not usable, but it is still a baked-in user identity. This conflicts with the
     task packet's exclusion of user identity and the plan's requirement that the reusable image
     contain no operator account. Remove the default account after the upstream SSH layer has
     finished, without replacing it with a project-chosen operator identity. Keep SSH key-only so
     later provisioning can create its account and key together.
  2. `/var/lib/e87canbus/unprovisioned` is root-owned, but `e87canbus` owns and can write its parent
     directory. Unix deletion and rename permissions come from the parent, so a role application
     running as `e87canbus` could remove or move the marker and defeat the planned systemd gate.
     Put provisioning state below a root-owned path that the service account cannot rename or
     write. Preserve `/var/lib/e87canbus` ownership for application data.
  3. The structural tests check package-name strings but do not enforce the acceptance criterion
     for secret and identity exclusions. Add a focused assertion over the common configuration
     and overlay that rejects an embedded login identity, authorized key, password or secret file,
     and fixes the expected provisioning files. This should protect the boundary without trying to
     detect arbitrary secrets heuristically.
- Optional observations: None. The runtime package split matches the stable shared part of the
  current installers. Role-only packages and assets remain correctly deferred. The explicit IWD
  and NetworkManager composition is valid and resolves cleanly through the pinned upstream layer
  dependencies.
- Questions for orchestrator: None. Version `1` plus an unprovisioned marker is an honest image-side
  lifecycle boundary once the marker is protected. It does not choose a boot-partition path,
  bundle schema, credential format or transport. The missing consumer remains a documented later
  provisioning responsibility rather than hidden implementation drift in this workstream.
- Evidence: `bash -n scripts/build-pi-image`; `uv run pytest
  hosts/tests/test_pi_image_build.py hosts/tests/test_host_deployment.py` (`33 passed`); `uv run
  ruff check hosts/tests/test_pi_image_build.py hosts/tests/test_host_deployment.py`; `git diff
  --check`; pinned `ig metadata --lint images/layer/e87-common.yaml`; inspection of the pinned
  `openssh-server`, `device-user-admin`, `network-manager-iwd` and per-layer overlay definitions;
  and comparison with both current host setup scripts and deployment units.

## Resolution

- Finding dispositions: Accepted all three findings. The common hook now removes the upstream
  `IGconf_device_user1` account and matching private group after the SSH layer has created its
  files, without adding an operator account. It keeps key-only SSH policy for later provisioning.
  Provisioning state moved from the application-owned directory to root-owned
  `/var/lib/e87canbus-provisioning`. Tests now exclude explicit credential configuration, require
  removal of the upstream login, and fix the common overlay to its one public version file.
- Simplification/deletion pass: Kept the existing single common hook and one-file overlay. No
  account replacement, credential scanner, secret filename convention, first-boot executable or
  bundle layout was added.
- Final verification: `bash -n scripts/build-pi-image`; `uv run pytest
  hosts/tests/test_pi_image_build.py hosts/tests/test_host_deployment.py` (`34 passed`); `uv run
  ruff check hosts/tests/test_pi_image_build.py hosts/tests/test_host_deployment.py`; `git diff
  --check`; pinned layer metadata lint; and pinned full common pipeline resolution all passed.

## Closure review

- Verdict: Accepted. All three required findings are resolved, and the remediation introduces no
  release-blocking defect.
- Remaining required findings: None. The pinned layer plan orders `device-user-admin`, then
  `openssh-server`, then `e87-common`, so the common hook removes the upstream login and its empty
  SSH home only after SSH configuration. Key-only SSH and first-boot host-key generation remain.
  The marker now sits below root-owned mode `0700` `/var/lib/e87canbus-provisioning`, outside the
  service account's writable application state. The focused tests reject explicit login or
  credential inputs and fix the overlay to the single public interface-version file.
- Closure verification: `bash -n scripts/build-pi-image`; shell syntax check of the extracted
  common customize hook; `uv run pytest hosts/tests/test_pi_image_build.py
  hosts/tests/test_host_deployment.py` (`34 passed`); `uv run ruff check
  hosts/tests/test_pi_image_build.py hosts/tests/test_host_deployment.py`; `git diff --check`;
  pinned layer metadata lint; and pinned focused pipeline resolution confirming the remediation
  order and empty SSH credential inputs.
- Accepted commit: `bc38ac6` (`Add common Raspberry Pi host image`).
