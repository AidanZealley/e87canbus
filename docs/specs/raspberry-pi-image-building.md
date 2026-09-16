# Raspberry Pi host images

- **Status:** Implemented and accepted
- **Date:** 2026-09-10

## Purpose

The repository builds reusable Raspberry Pi 4 images for the coordinator and console. The images
contain stable operating-system configuration and a strict first-boot provisioning consumer. They
do not contain an application release, installation credential or reusable host identity.

Generated images and manifests remain local under:

```text
artifacts/images/coordinator/
artifacts/images/console/
```

The [device lifecycle specification](device-provisioning.md) defines provisioning, identity,
application bundles and verification. The [image runbook](../../images/README.md) contains current
build and physical-check instructions.

## Build architecture

`e87ctl` is the only public image-build interface:

```text
uv run e87ctl image build coordinator
uv run e87ctl image build console
```

Both commands invoke the repository's pinned `rpi-image-gen` Docker builder. The first supported
host is an arm64 Mac running Docker Desktop or an equivalent Docker provider. The build downloads
Debian and Raspberry Pi packages and reuses a local package cache. The repository does not require
a separately downloaded base image.

Repository source is mounted read-only. Dedicated work, package-cache and artifact directories are
writable. Build dependencies stay inside the pinned container.

The shared image definition lives under `images/common/`. Role directories contain only real
coordinator or console differences. The definitions use Raspberry Pi OS Lite 64-bit Trixie and the
kernel and firmware packages selected by the pinned Raspberry Pi layers.

## Image contract

Both images contain:

- required runtimes and system packages;
- service users, filesystem layout and systemd units;
- role-specific boot, CAN, display and network defaults;
- key-only SSH configuration;
- a versioned provisioning-interface marker;
- `e87canbus-provision.service`; and
- an `unprovisioned` marker that keeps role services disabled.

Before publication, the build removes the builder hostname, `/etc/machine-id` and SSH host keys.
The image contains no repository clone, installation key, device credential, Wi-Fi password,
operator password or application release.

First boot validates the fixed `e87canbus-provisioning-v1.zip` bundle before changing installed
state. It installs identity, configuration, secrets and a complete application release without
running `apt`, `pip`, `uv`, `npm` or `pnpm`. Success records non-secret status, removes the boot
bundle and staged secrets, and clears `unprovisioned` last. Invalid input leaves role services
disabled and records a bounded failure status.

The coordinator image contains nginx, dnsmasq and nftables for the authenticated installation
network. The console image contains Cage, Chromium and NSS tooling for the local kiosk and its
client identity. Their current network and authentication behavior is defined by
[ADR 0013](../decisions/0013-provisioned-wifi-device-network.md) and
[ADR 0014](../decisions/0014-use-wpa2-personal-for-pi-network.md).

## Artifact manifest

Each image has a strict machine-readable manifest beside it. The manifest records:

- image format and target role;
- supported Raspberry Pi model;
- OS release and architecture;
- pinned builder revision;
- build time and available Git context;
- dirty-worktree state;
- image size and digest;
- provisioning-interface version; and
- boot and root storage limits for application and provisioning bundles.

The image digest is its identity. Git information records provenance but does not replace the
digest. Provisioning rejects an incompatible image and verifies the selected image before writing
the card.

## Change boundary

Normal Python and frontend changes belong in the application bundle and do not require a new host
image. Rebuild and repeat the physical checkpoint when changing OS packages, runtimes, boot
configuration, first-boot behavior, role services, network configuration, certificate installation
or kiosk setup.

Automated checks cover image definitions, manifests and provisioning contracts without Docker or
hardware where practical. They do not replace the macOS writer and Raspberry Pi 4 checks in the
[image runbook](../../images/README.md).

The console display assembly can interfere with the Pi's 2.4 GHz reception. The image remains on
the normal pinned Raspberry Pi Trixie kernel and firmware path. Mounting and retest requirements
are recorded in [console display interference](../requires-hardware/console-display-interference.md).

## Non-goals

- Raspberry Pi 5 support
- x86 emulated arm64 builds
- external artifact storage
- secure boot, verified boot or disk encryption
- package installation or application compilation on first boot
- a generic image plugin system
