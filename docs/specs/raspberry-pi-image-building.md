# Raspberry Pi image building

- **Status:** Draft
- **Date:** 2026-08-20

## Goal

Build reusable coordinator and console host images before implementing the provisioning CLI. The
images must boot on the current Raspberry Pi 4 hardware and contain the stable machine-level setup
needed by each role.

The output of this task is two image artifacts that Raspberry Pi Imager can flash:

```text
artifacts/images/coordinator/<build>.img
artifacts/images/console/<build>.img
```

Generated images remain local and are ignored by Git. External artifact storage can be added later
without changing the image definitions.

This task proves image construction and boot behaviour. It does not implement the provisioning
CLI, write SD cards itself or turn a flashed card into an installation-specific device.

## Initial targets

Both images use Raspberry Pi OS Lite 64-bit Trixie and initially target the Raspberry Pi 4 Model B.

The coordinator and console share a common image definition. Each role adds only its own packages,
configuration and services. The build should keep the target board explicit so a Raspberry Pi 5
definition can be added later. Pi 5 support is not part of this task.

## Build interface

Docker is the only supported build interface. The repository provides these commands:

```text
./scripts/build-pi-image coordinator
./scripts/build-pi-image console
```

The wrapper invokes a pinned version of
[`rpi-image-gen`](https://github.com/raspberrypi/rpi-image-gen) inside an arm64 Debian container. It
checks that Docker is available, reports the host and container architectures and fails with a
useful message when the host cannot run the supported builder.

The first supported build host is the M1 Pro MacBook running Docker Desktop or an equivalent
Docker provider. The container runs as arm64 without CPU emulation. Other hosts use the same
wrapper, but the first implementation does not promise emulated arm64 builds on x86 hardware.

`rpi-image-gen` needs Linux mount and filesystem capabilities that macOS does not provide. The
container receives only the privileges needed for the build. Repository source is mounted
read-only. Dedicated work, package-cache and artifact directories are writable.

The build requires a network connection. It downloads packages from the configured Debian and
Raspberry Pi repositories at build time and reuses a persistent local cache. The repository does
not contain or require a manually downloaded base OS image.

## Repository structure

The initial implementation should stay small:

```text
images/
  builder/
    Dockerfile
  common/
  coordinator/
  console/

scripts/
  build-pi-image

artifacts/
  images/
    coordinator/
    console/
```

The exact files inside each image definition should follow the pinned `rpi-image-gen` version
rather than adding a project-specific configuration system. Common configuration belongs in
`images/common/`. Role directories contain real differences only.

The host needs Docker and, for physical testing, Raspberry Pi Imager. Build dependencies such as
`rpi-image-gen`, `bdebstrap`, `mmdebstrap` and `genimage` stay inside the pinned container. The
wrapper should use the Docker CLI directly. This task does not need a Python package or another
command framework.

## Image contents

Each role image contains everything stable enough to avoid repeating machine setup after flashing:

- Raspberry Pi OS and required system packages;
- Python and other application runtimes;
- service users and filesystem layout;
- systemd units;
- boot, CAN, display and network defaults;
- key-only SSH configuration;
- console kiosk dependencies where required; and
- the one-time provisioning service expected by the later CLI.

The image build performs package installation and other slow machine-level work. First boot must
not clone the repository, install build tools, run `apt`, resolve application dependencies or build
the frontend.

The reusable images do not contain an installation key, device credential, Wi-Fi password,
operator password, installation-specific certificate or persistent host identity. They also do
not contain a repository clone.

Normal Python and frontend edits should not require a new host image. Those changes belong in the
application bundle described by the provisioning specification. Rebuild a host image when its OS
packages, runtimes, boot configuration or first-boot behaviour changes.

## Artifact manifest

Each image has a machine-readable manifest beside it. The manifest records:

- image format version and target role;
- supported Raspberry Pi model;
- OS release and architecture;
- pinned builder revision;
- build time and available Git context;
- whether the working tree was dirty; and
- image size and digest.

The later provisioning CLI uses this manifest to reject an incompatible image. The image digest is
its identity. Git information explains where it came from but does not replace the digest.

## What happens after flashing

During this task, Raspberry Pi Imager writes the image to an SD card. Temporary test access, such
as a user and SSH key, must be supplied during imaging or through a documented test-only input. It
must not be baked into the reusable image.

The first hardware test proves that the Pi boots, uses the expected role configuration and reaches
the documented systemd state. A flashed host image is not yet a fully provisioned project device.
It lacks the current application bundle, installation identity, device secrets and operator
configuration.

The later provisioning CLI adds those values and the current application bundle before first boot.
The image's one-time service consumes them on the Pi. That path must not require cloning the
repository or running the current setup script. Any remaining parts of that script must move into
the image build, the application build or the one-time provisioning service according to their
responsibility.

## Verification and handoff

Image building crosses a hardware boundary that a remote agent may not be able to test. An agent
can implement the container, image definitions and automated checks elsewhere, but it must not
claim macOS or Pi compatibility without the physical tests.

The work has two checkpoints.

### Checkpoint one: prove the builder

1. Implement the Docker wrapper and enough configuration to build an otherwise unmodified
   Raspberry Pi OS Lite 64-bit Trixie image.
2. Push a checkpoint commit with the exact Mac command and expected artifact path.
3. On the M1 Pro MacBook, run the build through Docker.
4. Flash the output with Raspberry Pi Imager and confirm that a Raspberry Pi 4 boots.
5. Hand the build output and any failure details back before role work continues.

### Checkpoint two: prove the role images

1. Add the shared, coordinator and console image contents.
2. Push a checkpoint commit with build and inspection instructions.
3. Build both images on the M1 Pro MacBook.
4. Flash and boot each image on its target hardware.
5. Confirm the role-specific checks and record the results.

Failure at either checkpoint returns to this task. The image-building task is complete only after
both role images pass the MacBook build, Raspberry Pi Imager flash and Raspberry Pi 4 boot checks.

Automated checks should validate the wrapper, manifests and configuration without Docker or
hardware where practical. They do not replace the two checkpoints.

## Acceptance criteria

- Both repository commands build through the same Docker implementation.
- The build runs as arm64 on the M1 Pro MacBook without CPU emulation.
- The builder downloads OS packages at build time and reuses a local cache.
- No generated image or package cache is committed to Git.
- Coordinator and console images share one common definition without a generic plugin system.
- Each output has a manifest and verified digest.
- Neither image contains installation secrets, operator details or a repository clone.
- First boot performs no package installation, dependency resolution or application build.
- The base image passes checkpoint one.
- Both role images pass checkpoint two.
- The test instructions state what the image proves and what later provisioning must still supply.

## Out of scope

- Provisioning or deployment CLI commands.
- SD-card discovery, safety checks and writing code.
- Installation keys, device credentials and Wi-Fi secrets.
- Application bundle construction or deployment.
- Microcontroller firmware.
- Raspberry Pi 5 support.
- Tagged releases and external artifact storage.

## Open decisions

1. The exact pinned `rpi-image-gen` revision and Debian container version.
2. The package repository snapshots or pinning needed for repeatable builds.
3. The precise common, coordinator and console package lists.
4. The test-only method used to gain first-boot access without embedding credentials.
5. The systemd checks that prove each role image booted correctly before provisioning exists.

## Related specifications

The [implementation workflow](raspberry-pi-image-building/implementation/README.md) turns this
specification into sequential implementation, review and hardware-validation workstreams.

The [device provisioning CLI](device-provisioning.md) consumes these images, writes them to SD
cards and supplies the application and installation-specific data.

The [Wi-Fi device network](wifi-device-network.md) defines the network behaviour enabled by later
provisioning. Image building installs its stable system requirements but does not create network
credentials.
