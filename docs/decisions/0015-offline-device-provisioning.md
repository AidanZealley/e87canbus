# ADR 0015: Provision devices from an offline installation authority

- **Status:** Accepted
- **Date:** 2026-09-16

## Context

Coordinator and console cards need installation-specific identity, credentials and application
code, but reusable images cannot contain a shared secret. The project has no enrollment service,
device inventory or secure hardware root. Adding any of those would create infrastructure without
improving the physical trust boundary of an unencrypted SD card.

## Decision

Each car has one caller-owned recovery package containing an installation certificate authority,
independent Wi-Fi and operator credentials, and an SSH maintenance identity. `e87ctl` reads that
package for each operation and keeps no hidden installation database.

Physical control of a blank card authorizes its first provisioning. `e87ctl` writes a bounded,
role-specific bundle containing a complete immutable application release and a certificate whose
signed identity names the installation, role and device. The reusable image's first-boot consumer
validates the complete bundle before installation, keeps role services disabled while
`unprovisioned` exists, and clears that marker only after identity, configuration, application and
secret cleanup succeed.

The installed device never receives the installation authority private key. The coordinator and
console receive only their own private keys and the public installation trust certificate.
Application releases are addressed by digest and activated through one `current` symlink after
complete validation.

There is no credential rotation or individual-device revocation in this version. A lost or
possibly copied device, card, SSH key or recovery package requires a new installation and
reprovisioning both Pis. A failed card that stayed under operator control may be replaced within
the existing installation.

## Consequences

- A reusable image contains no installation secret or reusable host identity.
- First boot does not need network enrollment, a repository checkout or application compilation.
- The recovery package is the installation's root secret and must be backed up in an encrypted
  secret store.
- Power loss or invalid input cannot enable a partial installation.
- Physical access to an installed, unencrypted card exposes that device's secrets.
- Secure boot, disk encryption, remote enrollment, credential rotation and device inventory remain
  separate future work.
