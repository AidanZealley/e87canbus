# Device firmware provisioning

- **Status:** Proposed
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

The chip appears once on the manifest. Flash entries are a list of offset, length and SHA-256,
because the bootloader, partition table and application are separate images at separate offsets.

Earlier drafts put the chip on each entry so one manifest could span two targets, for a cockpit
built on an ESP32-P4, which has no radio and reaches a network through a companion ESP32-C6. That
board is not selected and this work provisions one radio-equipped ESP32. Add multi-target manifests
if that hardware is chosen.

## Identity partition

This is the direct analogue of the Pi provisioning ZIP. `provision` generates it at flash time from
the recovery package and writes it at the `e87id` offset in the same `esptool` invocation as the
firmware. It contains the SSID, Wi-Fi password, installation CA certificate, device private key and
device certificate. It contains no address and no configuration.

The recovery package needs no changes. `_create_leaf` in `provisioning.py` already mints a leaf with
a role-parameterised URI SAN, so there is no format bump and no v2.

The coordinator side is not already generic, despite the SAN grammar being so. `_console_principal`
in `auth.py` rejects every certificate whose role is not `console`, so accepting device certificates
is new authentication work in workflow 03, described in device-platform, "Authentication".

Because identity and the configuration store are separate partitions, firmware can be reflashed
without reprovisioning identity, and identity can be reprovisioned without destroying stored
configuration. The Pi path cannot do either. Reflashing firmware therefore preserves the device ID;
only reprovisioning identity mints a new one.

The fail-closed marker analogue is firmware that refuses to bring up Wi-Fi when the identity
partition is absent or fails validation. It still performs its primary function, per the device
contract.

## Identity partition format

It is an NVS partition, not a hand-rolled binary layout. `e87cfg` is already NVS for its atomic
commit and wear levelling, ESP-IDF ships `nvs_partition_gen.py` to build an image from a CSV, and
firmware reads it with the same API it uses for everything else. Inventing a struct here would mean
writing a parser, a bounds checker and a versioning scheme that NVS already provides, for a
partition written once.

One namespace, `identity`, with six entries:

| Key | Type | Contents |
|---|---|---|
| `format` | `u8` | Format version, currently `1` |
| `ssid` | `str` | Installation SSID, 1 to 32 bytes |
| `wifi_pass` | `str` | WPA2 passphrase, 8 to 63 ASCII characters |
| `ca_pem` | `str` | Installation CA certificate, PEM |
| `dev_key` | `str` | Device private key, PEM, ECDSA P-256 |
| `dev_crt` | `str` | Device certificate, PEM, ECDSA P-256 |

The bounds on `ssid` and `wifi_pass` are 802.11 and WPA2 limits rather than choices. PEM is stored
rather than DER because `e87ctl` already produces PEM, mbedtls parses it directly, and the few
hundred bytes saved by converting buy nothing in a 24 KB partition.

There is no address, no installation ID field and no role field. The address comes from DHCP, and
the installation and role are both inside the certificate, where they are authenticated rather than
merely stored. A separate copy could disagree with the certificate, and then something would have to
decide which one wins.

**Validation before Wi-Fi comes up.** Firmware checks, in order: `format` is present and is a
version it knows; all five other keys are present and within bounds; `dev_crt` parses as X.509 and
carries exactly one URI SAN matching the `urn:e87canbus:device:v1:<installation>:<role>:<device-id>`
grammar, with a role the firmware implements; and `dev_key` parses as a P-256 private key. Any
failure means the radio never starts and the device runs its primary function on its compiled-in
default, which is the fail-closed-on-network, fail-open-on-function rule from the device contract.

It deliberately does not check that the key matches the certificate, that the certificate is signed
by `ca_pem`, or that the certificate is within its validity window. The TLS handshake tests all
three against the coordinator, which is the party that has to be convinced, and duplicating them
here would report the same failure twice in a place with no way to show it.

`format` exists so a later layout change is detectable rather than silently misread. There is no
migration path: a device with an unrecognised `format` is reprovisioned over USB, which is the only
way to change identity anyway.

## Partition table

The layout is fixed before the first board is provisioned, because changing it afterwards means
physically erasing every device.

| Partition | Type | Size |
|---|---|---|
| `nvs` | data, nvs | 24 KB |
| `otadata` | data, ota | 8 KB |
| `phy_init` | data, phy | 4 KB |
| `e87id` | data, nvs | 24 KB |
| `e87cfg` | data, nvs | 32 KB |
| `ota_0` | app, ota_0 | remainder, halved |
| `ota_1` | app, ota_1 | remainder, halved |

`e87id` at 24 KB holds two certificates, a key and the network credentials with room to spare:
a P-256 leaf is around 700 bytes of PEM and the key around 250. `e87cfg` at 32 KB carries the 8 KiB
payload bound plus its envelope, with NVS's own overhead and enough free pages that wear levelling
has somewhere to go.

The two OTA slots take what is left. Their size follows the confirmed flash size, which is the one
number here that waits on `esptool.py flash_id`. Everything above it is fixed regardless.

## Inherited decisions

One fact comes from [the device platform](device-platform.md) and is not decided here: DHCP
addressing, which is why the identity partition carries no address.

The partition table is stated above rather than in the platform specification, because provisioning
writes to its offsets and generates two of its partitions. The platform specification describes
which regions exist and why; the table here is the authority on their sizes.

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
