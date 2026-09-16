# Device firmware provisioning

- **Status:** Draft, shape agreed
- **Date:** 2026-09-16

## Goal

Extend `e87ctl` to build firmware for ESP32 devices and provision them into an installation, using
the same model it already applies to the Raspberry Pi hosts: a reusable artifact with no secrets, a
caller-owned recovery package, and a physical target.

This document records the agreed shape. It is deliberately less detailed than
[device provisioning](../device-provisioning.md) and is fleshed out after
[the device platform](device-platform.md) is implemented, which in turn follows
[the live event transport](live-event-transport.md).

## Why firmware is a durable artifact

The existing CLI contains both patterns and the difference is instructive. The Pi image is a
durable artifact chosen with `--image`, because it is reusable and slow to build. The application
bundle is built inside `provision` from the current checkout, because a Pi is recoverable: it has
SSH, a `releases/` directory and a `current` symlink, so a bad bundle is a redeploy away.

An ESP32 has neither property. The binary is the whole device, and the only fix is physical USB
access to a board behind a dash. Building inside `provision` means the binary that went into the car
was never the binary that was bench-tested. So firmware follows the image pattern.

## Command shape

```text
uv run e87ctl firmware build <device>
uv run e87ctl provision <device> --firmware <manifest> --port <serial>
```

`provision` keeps one positional device argument across Pi hosts and microcontrollers, dispatching
on a device table rather than a parallel command tree. Flag resolution follows the existing order of
flag, then environment, then interactive prompt, and `--non-interactive` fails on any missing value.

`_provision` in `e87ctl/src/e87ctl/cli.py` currently refuses to run outside macOS because `diskutil`
is macOS-only. That guard moves onto the Pi branch. Serial flashing has no such constraint.

## Device table

One table names every provisionable target and how to reach it: the provisioning method
(`pi-sd` or `esp-serial`), the chip, the firmware project directory, and the certificate role. The
coordinator's `DeviceRole` in `hosts/src/e87canbus/domain/devices/catalogue.py` is the source of the
role vocabulary. Certificates use the hyphenated form the URI SAN grammar already requires.

`Role` in `e87ctl/src/e87ctl/artifacts.py` is currently `Literal["coordinator", "console"]` and does
three jobs at once: image role, application role and device identity role. Those separate into host
roles, which have images and application bundles, and device roles, which have firmware.

## Firmware manifest

The manifest mirrors `ImageManifest`: format version, device, chip, build environment, build time,
Git commit and dirty flag, the provisioning interface version, and a digest per artifact. Artifacts
are written under `artifacts/firmware/<device>/`.

Flash entries are a list, each naming chip, offset, length and SHA-256, not a single binary with an
offset. Two reasons. The partition table and bootloader are separate images at separate offsets. And
a device may span two chips: the ESP32-P4 considered for the cockpit has no radio and reaches a
network through a companion ESP32-C6 running hosted firmware, which is a second binary on a second
target. A multi-chip flash sequence is something to record and verify, not reassemble per flash.

## Identity partition

This is the direct analogue of the Pi provisioning ZIP. `provision` generates it at flash time from
the recovery package and writes it at the `e87id` offset in the same `esptool` invocation as the
firmware. It contains the SSID, Wi-Fi password, installation CA certificate, device private key and
device certificate. It contains no address and no configuration.

The recovery package needs no changes. `_create_leaf` in `provisioning.py` already mints a leaf with
a role-parameterised URI SAN, and `auth.py` already parses role generically from it. Device
identity anticipated this, so there is no format bump and no v2.

Because identity and the configuration store are separate partitions, firmware can be reflashed
without reprovisioning identity, and identity can be reprovisioned without destroying stored
configuration. The Pi path cannot do either.

The fail-closed marker analogue is firmware that refuses to bring up Wi-Fi when the identity
partition is absent or fails validation. It still performs its primary function, per the device
contract.

## Inherited decisions

Three facts come from [the device platform](device-platform.md) and are not decided here:

1. The partition table, because provisioning writes to its offsets.
2. The identity partition contents and layout.
3. DHCP addressing, which is why the identity partition carries no address.

Nothing else crosses the boundary. `e87ctl` writes firmware and identity and has no opinion about
what the device does afterwards.

## Sequencing

The work these three specifications describe is sequenced in the [effort README](README.md). This
specification is one of six workflows and runs alongside the coordinator work, because it owns
`e87ctl/` and touches nothing those workflows write.

A partition table change after devices ship means physically erasing every device, so the layout is
fixed before the first board is provisioned. This specification is completed once that layout is
settled and the board is confirmed.

## Open questions

- The exact chip and module on the acquired CAN boards, confirmed by `esptool.py flash_id` rather
  than from the listing. This decides the PlatformIO board, the flash size, and whether hardware
  crypto acceleration is available for the TLS handshake.
- Whether the build uses PlatformIO or ESP-IDF directly. The existing projects use PlatformIO; a
  cockpit running LVGL on a P4 may force ESP-IDF, and the identity partition generator comes from
  ESP-IDF either way.
- Whether `firmware build` produces the partition table and bootloader images or consumes them from
  the build system's output unchanged.
