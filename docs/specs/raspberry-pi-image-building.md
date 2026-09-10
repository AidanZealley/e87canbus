# Raspberry Pi host images

- **Status:** V1 host-image prototypes accepted; provisionable successors pending
- **Date:** 2026-09-10

## Purpose and lifecycle boundary

Build reusable coordinator and console host-image prototypes before implementing the provisioning
CLI. The images must boot on the current Raspberry Pi 4 hardware and contain the stable
machine-level setup needed by each role.

The output is two image artifacts that Raspberry Pi Imager or `e87ctl` can flash:

```text
artifacts/images/coordinator/<build>.img
artifacts/images/console/<build>.img
```

Generated images remain local and are ignored by Git. External artifact storage can be added later
without changing the image definitions.

The completed v1 task proved image construction and boot behaviour. It did not implement the
provisioning CLI, write SD cards itself or turn a flashed card into an installation-specific
device.

The validated v1 artifacts are not yet provisionable images. They expose the handoff described
below, but they do not contain a first-boot provisioning consumer. The approved
[device lifecycle feature](device-provisioning.md) owns that successor work: it adds the consumer,
rebuilds both images and proves the complete provisioning path.

The shared image design and accepted v1 evidence remain here because they constrain that successor.
Requirements labelled as provisionable successors are not claims about the accepted v1 artifacts.

## Accepted v1 baseline

Both images use Raspberry Pi OS Lite 64-bit Trixie and initially target the Raspberry Pi 4 Model B.

The coordinator and console share a common image definition. Each role adds only its own packages,
configuration and services. The build should keep the target board explicit so a Raspberry Pi 5
definition can be added later. Pi 5 support is not part of this task.

## Provisionable build interface

Docker remains the only build implementation. The provisioning feature replaces the public shell
entry point with these repository-local commands:

```text
uv run e87ctl image build coordinator
uv run e87ctl image build console
```

`e87ctl` invokes the existing shell wrapper after it moves to `e87ctl/scripts/build-pi-image`. The
wrapper invokes a pinned version of
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

## Provisionable repository structure

The provisionable implementation keeps this structure:

```text
e87ctl/
  scripts/
    build-pi-image

images/
  builder/
    Dockerfile
  common/
  coordinator/
  console/

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
wrapper uses the Docker CLI directly. `e87ctl` only supplies the common repository command and does
not reproduce the builder.

## Shared image contents and successor changes

Each role image contains everything stable enough to avoid repeating machine setup after flashing:

- Raspberry Pi OS and required system packages;
- Python and other application runtimes;
- service users and filesystem layout;
- systemd units;
- boot, CAN, display and network defaults;
- key-only SSH configuration;
- console kiosk dependencies where required;
- a versioned provisioning-interface marker; and
- protected unprovisioned state that keeps role services disabled.

The validated v1 images do not contain a first-boot provisioning unit or consumer. The approved
provisioning feature adds one root-owned systemd consumer for the fixed
`e87canbus-provisioning-v1.zip` contract. It validates and stages the bundle, installs identity,
configuration, secrets and the application, records non-secret status, removes staged secrets and
clears `unprovisioned` last. The role services remain fail-closed until that transition succeeds.

The image build performs package installation and other slow machine-level work. First boot must
not clone the repository, install build tools, run `apt`, resolve application dependencies or build
the frontend.

The reusable images do not contain an installation key, device credential, Wi-Fi password,
operator password, installation-specific certificate or installation-specific host identity. They
also do not contain a repository clone. Provisionable successors contain no reusable
`/etc/machine-id` or SSH host keys.

The validated prototypes contain the hostname generated by the upstream image builder. Every card
flashed from one artifact therefore starts with the same hostname. This value is not an installation
identity or secret. The provisionable successors remove that reusable identity and let the
first-boot consumer install the assigned hostname before enabling role services.

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

The provisionable successor also records its provisioning-interface version and the boot and root
storage limits enforced for application and provisioning bundles.

`e87ctl` uses this manifest to reject an incompatible image. The image digest is
its identity. Git information explains where it came from but does not replace the digest.

## V1 behavior after flashing

During this task, Raspberry Pi Imager writes the image to an SD card. Temporary test access, such
as a user and SSH key, must be supplied during imaging or through a documented test-only input. It
must not be baked into the reusable image.

The first hardware test proves that the Pi boots, uses the expected role configuration and reaches
the documented systemd state. A flashed host image is not yet a fully provisioned project device.
It lacks the current application bundle, installation identity, device secrets and operator
configuration.

The provisioning feature uses the fixed application and provisioning bundles defined in the
[device lifecycle specification](device-provisioning.md). It adds the consumer and unique host
identity, builds new images through `e87ctl image build` and reruns the relevant image and hardware
checks. The resulting path does not clone the repository or run the current setup script. Any
remaining parts of that script move into the image build, application build or one-time consumer
according to their responsibility.

## Hardware evidence and successor handoff

Image building crosses a hardware boundary that a remote agent may not be able to test. An agent
can implement the container, image definitions and automated checks elsewhere, but it must not
claim macOS or Pi compatibility without the physical tests.

The completed prototype work had two checkpoints. The provisioning feature adds a third.

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

### Checkpoint three: prove provisionable successors

1. Add the fixed first-boot consumer and remove reusable host identity.
2. Build both roles on the M1 Pro MacBook through `e87ctl image build`.
3. Provision and boot one coordinator and one console through the new card workflow.
4. Confirm successful bundle consumption, unique host identity, secret cleanup, marker transition,
   role services and the Wi-Fi checks owned by the network specification.
5. Confirm the non-secret boot-partition status remains useful when a deliberately invalid bundle
   fails before networking starts.

The provisioning feature is incomplete until checkpoint three passes. A failure returns to that
feature rather than changing the accepted evidence for the v1 prototypes.

Automated checks should validate the wrapper, manifests and configuration without Docker or
hardware where practical. They do not replace the applicable physical checkpoints.

## V1 prototype acceptance criteria

- Both historical `./scripts/build-pi-image coordinator|console` commands build through the same
  Docker implementation.
- The build runs as arm64 on the M1 Pro MacBook without CPU emulation.
- The builder downloads OS packages at build time and reuses a local cache.
- No generated image or package cache is committed to Git.
- Coordinator and console images share one common definition without a generic plugin system.
- Each output has a manifest and verified digest.
- Neither image contains installation secrets, operator details or a repository clone.
- First boot performs no package installation, dependency resolution or application build.
- The images expose a versioned interface marker and protected unprovisioned state, but no
  first-boot provisioning consumer.
- The base image passes checkpoint one.
- Both role images pass checkpoint two.
- The test instructions state what the image proves and what later provisioning must still supply.

These criteria describe the accepted prototype artifacts recorded in the
[final review](raspberry-pi-image-building/implementation/final-review.md).

## Provisionable successor owned by device lifecycle tooling

The [device lifecycle tooling](device-provisioning.md) workflow owns the implementation and
acceptance of every item in this section. The completed image-building workflow must remain closed.

### Acceptance criteria

- `e87ctl image build` is the only public image-build interface and still uses the accepted Docker
  implementation.
- Each image contains the fixed first-boot consumer and keeps role services gated while
  `unprovisioned` exists.
- Neither image contains reusable machine identity, SSH host keys or installation secrets.
- The consumer validates all bundle contents before changing installed state.
- A power interruption cannot enable a partial installation and can resume from durable staging.
- Success removes the boot bundle and staged secrets, records non-secret status and clears
  `unprovisioned` last.
- Invalid input records a safe failure while leaving role services disabled.
- First boot installs a ready application without package installation, dependency resolution or
  frontend compilation.
- Both rebuilt roles pass checkpoint three on the target hardware.

## Out of scope

- Provisioning or deployment CLI commands.
- SD-card discovery, safety checks and writing code.
- Installation keys, device credentials and Wi-Fi secrets.
- Application bundle construction or deployment.
- Microcontroller firmware.
- Raspberry Pi 5 support.
- Tagged releases and external artifact storage.

## Related specifications

The accepted [implementation workflow](raspberry-pi-image-building/implementation/README.md)
records the v1 prototype work. Do not reopen or reuse that workflow for the provisionable
successors.

The [device lifecycle tooling](device-provisioning.md) specification owns the successor consumer,
rebuild and hardware checkpoint. It writes the images to SD cards and supplies the application and
installation-specific data.

The [Wi-Fi device network](wifi-device-network.md) defines the network behavior enabled by
provisioning. Image building installs its stable system requirements but does not create network
credentials.
