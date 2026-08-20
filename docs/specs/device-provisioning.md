# Device provisioning CLI

- **Status:** Draft
- **Date:** 2026-08-20

## Goals

Provide one repository-owned CLI that prepares every project device and gets the project software
running on it. The CLI consumes Raspberry Pi image artifacts, writes SD cards and handles the
existing microcontroller projects without hiding their different flashing mechanisms behind a
plugin system.

The same work prepares the installation for a secure Wi-Fi connection between project devices and
for operator access through the coordinator hotspot. Wi-Fi is an optional capability of a device,
not a requirement for using the common provisioning workflow.

The intended lifecycle is:

```text
provision       host image or firmware + device inputs -> prepared device running current software
deploy          current working tree or supplied artifact -> updated provisioned device
verify          expected state + target -> structured result
```

A Raspberry Pi is normally provisioned once. Routine application changes use deployment and
preserve its machine configuration and identity. Reprovisioning is an explicit replacement
operation.

## Supported devices

The current provisioning targets are:

- `coordinator`, a Raspberry Pi 4 Model B;
- `console`, a Raspberry Pi 4 Model B;
- `button-pad`, the current Pro Micro firmware project;
- `servotronic-controller`, the current Pro Micro fan-bench prototype; and
- `coordinator-panel`, the current QT Py RP2040 firmware project.

The Servotronic controller remains bench-only and is not vehicle-safe. Provisioning it does not
change that status.

The ESP32-P4 cockpit is planned but does not exist. It is not a supported target and must not shape
the first implementation. It can adopt the same provisioning and Wi-Fi identity model later.

The current Wi-Fi participants are the coordinator and console. The three current
microcontrollers use the common build, flash and verification workflow but do not receive unused
Wi-Fi configuration or credentials.

## Terms

- An **installation** is this car and the project devices prepared for it.
- The **installation key** is a generated, high-entropy signing key kept outside the CLI. It is
  never installed on a device.
- The **installation ID** is a stable, non-secret identifier derived from the installation key.
- The **installation trust key** is the public key corresponding to the installation key. The
  coordinator and other verifiers may store it.
- A **device identity** contains an installation ID, a fixed role and a unique device ID.
- A **device credential** binds a Wi-Fi device public key to its identity using the installation
  key. The device stores the corresponding private key.
- A **host image** is a reusable Raspberry Pi image containing OS and machine-level software but no
  installation secrets.
- An **application bundle** contains application code and built frontend assets from one working
  tree state.
- A **provisioning bundle** contains the identity, secrets and machine-specific configuration
  needed by one target.

The Wi-Fi password and operator password are independent inputs. Neither derives from the
installation key.

## Stateless operation

The CLI does not own an installation profile, device inventory, key store or credential registry.
It does not remember installation values between commands. Every operation receives its desired
state from command-line arguments, environment variables, standard input or interactive prompts.

Interactive input is temporary process state. It does not make the CLI stateful.

The caller owns long-lived data such as:

- the installation key;
- operator details and the Wi-Fi password;
- optional device names and records; and
- image, firmware and application artifacts.

Arguments override environment variables. Interactive prompts fill only missing values. A
`--non-interactive` invocation fails with a useful error when a required value is missing.
Machine-readable output must not contain human prompts.

Secrets must not appear in process arguments, logs, generated frontend assets or repository
files. Interactive use reads them without echo. Automation may provide them through environment
variables or standard input.

Commands may write an explicitly requested artifact or target. They return generated values and
verification results but do not become the owner of those values.

## Installation creation and device trust

`e87canbus provision init` generates an installation key and derives its installation ID and
public trust key. It stores nothing and does not create a local profile. The operator saves the
installation key in a password manager, hardware-backed key store or equivalent backed-up
location.

The first implementation uses an encoded random key rather than a mnemonic recovery phrase. A
mnemonic adds transcription work but does not improve recovery when a key manager is the system
of record.

Running `init` again creates a different installation. The CLI must make that clear before showing
or returning the new key.

Provisioning does not require a device list. A Wi-Fi device can be provisioned at any time with a
unique key pair and a signed credential containing its installation ID, role and device ID. The
coordinator stores the installation trust key and verifies the credential without receiving the
installation key or a prior allowlist.

Authentication must prove possession of the device private key. Presenting its public credential
alone is insufficient. The signed role controls authorization and cannot be changed by the
device.

The credential includes a stable device ID so revocation can be added later. The first
implementation does not include a denylist, credential rotation, expiry, generations or revocation
commands. Losing a credential may require replacing installation trust during this phase.

The exact credential format, signing algorithm and proof protocol remain open. The selected
construction must use established cryptographic libraries and include an explicit format version
and project-specific domain separation.

## Local artifacts and development workflow

The first implementation runs from a repository checkout:

```text
cd /path/to/e87canbus
uv run e87canbus <command>
```

`uv run` is the normal prefix for each command. An operator may instead activate `.venv` and call
`e87canbus` directly. A standalone installation that works without the repository may be added
after the workflow is proven.

Generated artifacts consumed by the CLI have fixed locations:

```text
artifacts/
  images/
    coordinator/
    console/
  applications/
    coordinator/
    console/
  firmware/
```

`artifacts/` is local build output and must be ignored by Git. Raspberry Pi images are expected to
be large. External artifact storage may replace the local directory later without changing the
provisioning operations.

The project does not require tagged releases or semantic versions for development deployment.
Image and application manifests record enough automatic provenance to identify what was used:

- target role and artifact format version;
- build time;
- Git commit when available;
- whether the working tree was dirty;
- compatibility information; and
- the artifact digest.

The digest is the artifact identity. Git metadata is diagnostic context. A dirty or untracked
working-tree change included in the build remains identified by the artifact digest even though it
does not match the recorded commit exactly.

Interactive commands list compatible artifacts from these directories by default and allow an
explicit path elsewhere.

## Raspberry Pi image inputs

The CLI consumes completed coordinator and console host images produced by the separate
[Raspberry Pi image building](raspberry-pi-image-building.md) task. It does not own the image build
implementation.

Provisioning validates the selected image manifest, writes the image and adds the current
application and device-specific provisioning bundles. It must not depend on undocumented details
of the image builder.

## Application bundles and rapid deployment

The CLI builds an application bundle from the current working tree. It may include uncommitted and
untracked source files selected by the build definition. A clean working tree, tag and version bump
are not required.

The application bundle contains the Python application and built frontend needed by one Pi role.
Provisioning injects the current bundle alongside the first-boot provisioning data so a newly
flashed Pi starts with the code being tested. The reusable host image does not need rebuilding for
each application change.

After provisioning, the default deployment command builds and deploys the current working tree:

```text
uv run e87canbus deploy coordinator --host <host>
uv run e87canbus deploy console --host <host>
```

An explicit application artifact remains supported for repeating a deployment or returning to a
known build:

```text
uv run e87canbus deploy coordinator --host <host> --artifact <path>
```

Pi deployment transfers the application bundle over an authenticated management connection,
activates it, restarts the affected services and checks their health. It preserves device
identity, installation trust, Wi-Fi settings, operator configuration, databases and host identity.
It does not rewrite the SD card or require the installation key.

The installed Pi does not use Git to update itself. It does not retain a repository clone as the
deployment mechanism.

## Raspberry Pi provisioning

The interactive Pi command selects a compatible host image and eligible SD card, builds the current
application bundle, then shows the complete destructive action for confirmation:

```text
uv run e87canbus provision coordinator
uv run e87canbus provision console
```

Equivalent command-line arguments support repeatable non-interactive use:

```text
uv run e87canbus provision coordinator --image <path> --target <device>
```

Provisioning performs these phases:

1. Resolve, inspect and confirm the target SD card.
2. Validate the host image manifest and application compatibility.
3. Write the host image and verify the written bytes.
4. Create a unique device identity where the role requires one.
5. Add the application and one-time provisioning bundles to the boot partition.
6. Verify the bundles and safely unmount the card.
7. After first boot, report the online checks available through the current connection.

Depending on the role, a provisioning bundle may contain its signed identity, private device key,
installation trust key, hostname, SSH authorized key, deployment profile, network settings, HTTPS
trust and operator configuration.

On first boot, the provisioning service:

1. validates the bundle format, artifact compatibility and role;
2. installs the application, configuration and secrets with the required ownership and
   permissions;
3. creates unique host identity where the base image requires it;
4. removes the consumed secrets and bundle;
5. records non-secret provisioning status; and
6. starts the services or reboots when required.

Removing a file from flash media is not secure erasure. This design assumes that someone with
physical access to an unencrypted SD card can recover that device's installed secrets. Disk
encryption, secure boot and verified boot are outside the first implementation.

## SD card safety

The CLI treats image writing as destructive. It must never pass an unchecked string directly to
the image writer.

Normal discovery hides the disk that backs the running system and all its partitions. Supplying a
protected disk explicitly does not bypass the check. The first implementation has no option to
write the current system disk.

On Linux, discovery may use structured output from `lsblk` and `findmnt`. It must:

- resolve partitions and virtual devices to their parent physical disks;
- protect the disks backing `/`, `/boot` and `/boot/firmware`;
- accept only a whole disk, not a partition;
- report the resolved path, model, capacity, serial, transport, removability and mounts;
- reject unresolved paths, globs and ambiguous aliases;
- re-read device identity immediately before writing; and
- require confirmation of the resolved device, model and capacity.

Removability alone is not a safety decision. Built-in card readers and external system drives may
report it incorrectly or unexpectedly.

Mounted non-system targets appear as unavailable until the command explicitly unmounts them after
confirmation. The writer accepts only a validated target produced by the safety checks. It cannot
accept an arbitrary path through another call site.

The first implementation may support only the development host operating system that is tested.
Other operating systems need their own system-disk discovery and elevation implementation before
they can write images.

## Microcontroller provisioning and deployment

The CLI uses each existing project's normal USB tooling:

- `button-pad` uses its fixed PlatformIO environment;
- `servotronic-controller` uses its fixed PlatformIO environment; and
- `coordinator-panel` uses the existing `picotool` upload path.

The first implementation may invoke the existing PlatformIO and upload commands directly from the
checkout. It should not reproduce their compilation, board support or upload logic.

Interactive commands list compatible connected USB candidates and allow the operator to rescan or
provide a port. USB metadata does not always distinguish the two Pro Micro projects, so the CLI
must describe uncertain matches as candidates and require confirmation.

Provisioning flashes the current firmware and writes installation-specific configuration where
the target supports it. Deployment updates firmware while preserving stored identity and
configuration where possible. A target without separate persistent configuration may use the same
physical upload operation for both commands. Its implementation must state what an update
preserves.

Do not force Raspberry Pi and microcontroller transports behind a common plugin or transport
interface. Keep one explicit implementation for each supported target. They may share artifact,
identity and verification formats where that reduces real duplication.

## Verification

Provision and deploy commands verify their own writes. A separate command can inspect an existing
target without changing it:

```text
uv run e87canbus verify <target>
```

Verification reports only checks supported by the target and current connection. Its structured
result identifies checks as passed, failed or unavailable. It does not treat an offline target as
fully verified.

Checks may include:

- artifact identity, digest and compatibility;
- installation ID, role and device ID where installed;
- presence and permissions of device key material;
- successful first-boot bundle consumption;
- application service health;
- Wi-Fi association for a Wi-Fi role;
- coordinator identity verification;
- authenticated coordinator access with the device credential; and
- rejection of a credential from another installation or role.

The Wi-Fi checks can be added without changing how a device is provisioned. Non-Wi-Fi devices skip
them.

## Interactive command model

The existing `e87canbus` Python entry point remains the only project CLI. Extend its current
`argparse` command structure instead of adding another CLI framework or executable.

Command names remain provisional. The intended shape is:

```text
uv run e87canbus run
uv run e87canbus devices
uv run e87canbus inspect <target>

uv run e87canbus provision init
uv run e87canbus provision coordinator
uv run e87canbus provision console
uv run e87canbus provision button-pad
uv run e87canbus provision servotronic-controller
uv run e87canbus provision coordinator-panel

uv run e87canbus deploy coordinator --host <host>
uv run e87canbus deploy console --host <host>
uv run e87canbus deploy button-pad
uv run e87canbus deploy servotronic-controller
uv run e87canbus deploy coordinator-panel

uv run e87canbus verify <target>
```

When a required value is absent and standard input is an interactive terminal, the CLI shows a
numbered menu or prompt. Initial prompts use normal terminal input rather than an arrow-key UI
dependency. Prompts may select:

- a compatible local image or firmware artifact;
- an eligible SD card;
- a plausible connected USB device;
- a role-specific deployment profile; and
- required non-secret settings and hidden secrets.

All choices are also available through explicit arguments or environment variables. Interactive
and non-interactive paths create the same typed operation request and call the same implementation.

The final confirmation for a destructive write remains mandatory in interactive use. Convenience
options must not bypass system-disk protection, target identity checks or role compatibility.

## Implementation direction

Keep provisioning code separate from the running vehicle application's `domain`, `kernel` and
`service` layers. A suitable initial package shape is:

```text
hosts/src/e87canbus/
  cli/
    main.py
    provision.py
    deploy.py
    devices.py

  provisioning/
    models.py
    identity.py
    bundle.py
    block_devices.py
    raspberry_pi.py
    microcontrollers.py
    verification.py
    command_runner.py

  device_deployment/
    raspberry_pi.py
    microcontrollers.py
```

Argument parsing, environment lookup, prompts and rendering belong in `cli`. Provisioning and
deployment functions accept typed requests and return typed results. They do not prompt or depend
on terminal output. This keeps the implementation testable and leaves room for another caller
without building an application protocol now.

The one extra type boundary justified by risk is the SD-card writer. It accepts a validated write
target produced by system-disk checks, never a raw device path.

Subprocess integration stays small and explicit. Tests can supply a recording command runner to
check PlatformIO and system-command invocation without accessing hardware.

## First CLI implementation milestone

After the separate image-building task passes, the first CLI milestone covers the current devices
and repository-local workflow:

1. Add interactive command dispatch and explicit non-interactive inputs.
2. Generate and return an installation key, ID and public trust key without storing them.
3. Discover SD cards while excluding the running system disk.
4. Write and verify either Pi image, current application bundle and first-boot bundle.
5. Provision the coordinator with its hotspot inputs and installation trust key.
6. Provision a console identity and the inputs needed for the planned secure Wi-Fi connection.
7. Flash the button pad, Servotronic controller and coordinator panel through their existing USB
   tooling.
8. Deploy the current working tree to an already provisioned Pi without rewriting its card.
9. Return structured verification for every supported operation.

The first Wi-Fi cutover may follow as a separate implementation milestone using the identity and
configuration placed here. Do not add the cockpit, revocation, a desktop UI, a generic device
plugin API, over-the-air updates, disk encryption or secure boot in this milestone.

## Acceptance criteria

- The CLI stores no installation profile, key, device inventory or implicit configuration.
- The documented development path works from the checkout through `uv run e87canbus`.
- Local images and application bundles live under a known Git-ignored artifact directory.
- No tag, semantic version or clean working tree is required to deploy current application code.
- Artifact manifests identify their contents with a digest and record available Git context.
- Interactive commands list only compatible artifacts and eligible write targets by default.
- Every interactive choice has a corresponding explicit input for non-interactive use.
- `provision init` returns a new installation key and its derived public identity without storing
  either value.
- A coordinator can authenticate a console provisioned later with the same installation key
  without a prior allowlist update.
- The first implementation does not require or expose revocation behaviour.
- A freshly provisioned Pi starts the supplied application without cloning the repository,
  installing build tools or building software on first boot.
- System disks are absent from writable candidates and rejected when supplied explicitly.
- The CLI revalidates the selected disk identity immediately before writing and verifies the
  completed write.
- Button pad, Servotronic controller and coordinator panel flashing use their existing supported
  toolchains and require confirmation of the resolved USB target.
- A normal Pi deployment preserves provisioned identity and persistent configuration.
- Devices without Wi-Fi use the same CLI without receiving unused Wi-Fi credentials.
- No reusable artifact contains an installation secret.
- No secret appears in the repository, logs, process command line or generated frontend assets.

## Open decisions

1. The encoded installation key format and versioned signing construction.
2. Whether device keys are generated by the CLI or on capable targets.
3. The signed credential format and proof used by HTTP and Socket.IO clients.
4. The application and first-boot bundle formats, size limits and compatibility rules.
5. The authenticated Pi deployment transport and on-device application layout.
6. How the CLI observes first-boot completion after the operator moves a card into a Pi.
7. Which development host operating systems the first SD-card writer supports.
8. What persistent identity or configuration each current microcontroller can preserve across a
   firmware update.
9. Which USB details identify each supported microcontroller with useful confidence.

## Related specifications

The [Wi-Fi device network](wifi-device-network.md) defines how the coordinator, console and hotspot
communicate after provisioning. It does not own image creation, installation identity, flashing or
application deployment.

The [Raspberry Pi image building](raspberry-pi-image-building.md) specification defines the
reusable host images consumed by Pi provisioning.
