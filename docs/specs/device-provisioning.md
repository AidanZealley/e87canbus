# Device lifecycle tooling

- **Status:** Approved for implementation
- **Date:** 2026-09-10

## Goal

Provide one repository-owned workstation tool that builds Raspberry Pi images and prepares a
coordinator and console from blank SD cards. A completed pair must boot the current application,
connect over the coordinator's private Wi-Fi network and authenticate each other without a manual
device login.

The first implementation is one complete coordinator-to-console path. It does not attempt to cover
every project device or every later lifecycle operation.

The tool is called `e87ctl`. It is separate from the two programs that run on the Pis:

```text
e87ctl             workstation image, provisioning and verification tool
e87canbus          coordinator runtime
e87canbus-console  console runtime
```

## Scope

The first implementation must:

- build the reusable coordinator and console images through the existing Docker builder;
- create an explicit installation recovery package;
- build self-contained ARM64 application bundles from the current checkout;
- discover, write and verify SD cards safely on macOS;
- provision one coordinator and one console;
- create unique device and Linux host identity;
- install the application and secrets through a one-time first-boot consumer;
- configure the isolated coordinator Wi-Fi network;
- authenticate console HTTP and Socket.IO traffic with mutual TLS; and
- report offline preparation and online first-boot verification separately.

Routine deployment and microcontroller support are later milestones. They must not add unused
abstractions to this implementation.

## Simplicity and security boundary

Meet the stated threat model with standard protocols and existing operating-system facilities.
Do not add competing implementations, configurable cryptographic suites or recovery machinery for
hypothetical failures.

The first implementation accepts these limits:

- Physical control of an unencrypted SD card grants access to secrets installed on that card.
- Deleting a file from flash media is not secure erasure.
- A reusable image cannot authenticate its first provisioning bundle because it contains no
  installation-specific trust anchor. Physical control of the card authorizes initial
  provisioning.
- There is no credential revocation or rotation. Loss or compromise of a device or the recovery
  package is handled by creating a new installation and reprovisioning both Pis.
- Certificate expiry is handled by reprovisioning.

Disk encryption, secure boot, verified boot, hardware-backed device keys, remote access and an
online enrollment service are outside this milestone.

## Repository and package boundary

`e87ctl` is a top-level Python package with its own source and tests:

```text
e87ctl/
  pyproject.toml
  src/e87ctl/
  scripts/
    build-pi-image
  tests/

hosts/
  src/e87canbus/

images/
deploy/
devices/
artifacts/
```

The root development environment exposes `e87ctl` as an editable local dependency, so commands run
from the checkout as `uv run e87ctl ...`. The `e87ctl` distribution and its workstation-only
dependencies are not included in either Pi application bundle.

Move the existing `scripts/build-pi-image` implementation and its tests under `e87ctl`. Do not
rewrite the proven Docker orchestration merely to replace shell with Python. The old public script
path is removed after documentation and tests use `e87ctl image build`.

The root `images/` directory remains the source for reusable image definitions. `deploy/` remains
the canonical source for files installed on the Pis.

## Command interface

The first public commands are:

```text
uv run e87ctl image build coordinator
uv run e87ctl image build console

uv run e87ctl installation create --output <recovery-package>

uv run e87ctl provision coordinator --installation <recovery-package>
uv run e87ctl provision console --installation <recovery-package>

uv run e87ctl verify coordinator --installation <recovery-package>
uv run e87ctl verify console --installation <recovery-package>
```

Interactive provisioning lists compatible images and eligible disks, selects a `car` or `bench`
profile and requires confirmation of the resolved destructive action. Every interactive selection
has an explicit non-interactive input. `--non-interactive` fails if any required value is absent.

Secrets are read from the recovery package, standard input or a protected file. They never appear
in process arguments, prompts with echo enabled, logs, generated frontend assets or repository
files. Machine-readable output contains no interactive prompts.

Separate `devices` and `inspect` commands are not part of the first implementation. Provisioning
already performs the discovery and inspection it needs.

## Terms

- An **installation** is one car and the project devices prepared for it.
- The **installation authority** is a private X.509 certificate authority created for one
  installation and kept in its recovery package.
- The **installation ID** is a stable public identifier derived from the authority's public key.
- The **installation trust certificate** is the public CA certificate installed on devices and
  imported by service clients where needed.
- A **device identity** contains the installation ID, a fixed role and a unique device ID.
- A **device certificate** binds a device public key to that identity.
- A **host image** is a reusable Raspberry Pi image with no installation-specific secrets.
- An **application bundle** is a complete role-specific ARM64 Linux application release.
- A **provisioning bundle** contains one application bundle and the identity, secrets and
  machine-specific configuration for one Pi.

The Wi-Fi password, operator password and SSH management key are independent credentials. None is
derived from the installation authority.

## Installation recovery package

`e87ctl installation create` writes one versioned JSON document, normally named
`e87canbus-installation-v1.json`. It contains:

- its format version and creation time;
- the installation ID;
- the installation CA private key and public certificate;
- the generated Wi-Fi SSID and password;
- the fixed operator username and generated operator password; and
- a generated Ed25519 SSH management key pair.

The JSON stores the CA private key as unencrypted PKCS#8 PEM, the CA certificate as PEM, the SSH
private key as unencrypted OpenSSH PEM and the SSH public key in its one-line OpenSSH form. The
format has no alternate key encodings in v1.

The operator username is `operator`. Generated passwords use cryptographically secure randomness
and alphabets accepted by their consumers.

The CLI creates the file with mode `0600`, refuses to overwrite an existing path and prints only a
non-secret summary. It also writes the public CA certificate beside the package as
`<package-stem>-ca.pem` for service-laptop import. The public sidecar contains no secret and may be
recreated from the recovery package.

The operator stores the JSON document in a password manager or equivalent backed-up secret store.
The document is plaintext because encrypting it would create another recovery secret; the chosen
secret store owns encryption.

The CLI keeps no hidden profile, key store or device inventory. It reads the caller-owned recovery
package for each operation that needs installation authority. Provisioning-generated device
private keys exist only in process memory, the target bundle and the installed target. They are not
added to the recovery package.

## Installation and device identity

The installation authority and TLS certificates use ECDSA with the P-256 curve. The CA certificate
is valid for 20 years. Coordinator and console certificates are valid for 10 years without
exceeding the CA expiry. Certificates become valid 24 hours before their creation timestamp. The
provisioning manifest records its creation time, and the first-boot consumer moves a stale system
clock forward to at least that time before installing or using certificates. It never moves the
clock backward.

Derive the installation ID from:

```text
SHA-256("e87canbus-installation-v1\0" || DER SubjectPublicKeyInfo)
```

Encode the complete digest as unpadded lowercase base32 for stored identity. Short prefixes may be
used for display, SSIDs and hostnames, but authorization always compares the complete identity.

Each Pi receives a random UUID device ID. Its certificate carries this signed URI subject
alternative name:

```text
urn:e87canbus:device:v1:<installation-id>:<role>:<device-id>
```

Extended key usage restricts the coordinator certificate to TLS server authentication and the
console certificate to TLS client authentication. The CA certificate has critical CA basic
constraints and key-cert-sign usage. Leaf certificates cannot sign certificates.

The coordinator stores the public installation trust certificate, its own server private key and
certificate. It never stores the CA private key or the console private key. The console stores its
own private key and certificate plus the public installation trust certificate.

TLS certificate verification provides proof of private-key possession. Do not add JWTs, bearer
tokens, request signing or a separate challenge protocol.

## Host and local account identity

Provisioning chooses hostnames in these forms unless the operator supplies a valid explicit name:

```text
e87-coordinator-<device-id-prefix>
e87-console-<device-id-prefix>
```

The first-boot consumer sets the hostname before enabling role services. The rebuilt images contain
no reusable `/etc/machine-id`, SSH host keys or other cloned host identity. The Pi generates its
machine ID and SSH host keys locally.

The installed accounts are:

- `e87canbus`, the existing non-login service account;
- `e87-kiosk`, a fixed non-login console display account; and
- `e87-admin`, a key-only SSH maintenance account on both Pis.

The recovery package's SSH public key is authorized for `e87-admin`. SSH password login and root
login remain disabled. `e87-admin` has passwordless sudo and the private SSH key is therefore
root-equivalent. This direct maintenance path is simpler and more useful than an incomplete sudo
allowlist. Protecting the recovery package is the security boundary.

The web operator account is unrelated to Linux accounts. The coordinator stores an Argon2id hash
of its password, while the recovery package retains the plaintext value for the operator.

## Artifact locations and provenance

Generated artifacts use fixed Git-ignored locations:

```text
artifacts/
  images/
    coordinator/
    console/
  applications/
    coordinator/
    console/
```

The project does not require a clean working tree, tag or semantic version. Image and application
manifests record:

- format version and role;
- target architecture and compatibility versions;
- build time;
- Git commit when available;
- whether tracked or untracked build inputs were dirty;
- byte sizes; and
- SHA-256 digests.

The digest identifies the artifact. Git metadata is diagnostic context.

## Host image contract

The current validated Pi images are non-provisionable prototypes. They have a versioned interface
marker and fail-closed role services, but no consumer. Cards written from one artifact also share
the upstream builder hostname.

This feature adds the consumer and unique-host-identity behavior to the image source, then rebuilds
both images through `e87ctl image build`. Rebuilt images must repeat the relevant automated,
MacBook, Raspberry Pi Imager and Pi 4 checks before provisioning accepts them.

Each provisionable image exposes a machine-readable contract containing its role, board,
architecture, OS version, provisioning-interface version and storage limits. The CLI validates the
image manifest before writing. The on-device consumer independently validates the baked contract
against the provisioning bundle.

Reusable images contain no application, repository clone, operator account, installation
certificate, device key, Wi-Fi password or installation-specific host identity.

## Application bundle

`e87ctl provision` builds the current role's application before writing the card. A clean working
tree is not required.

The build runs in a pinned ARM64 Linux container and produces `application-v1.tar.gz`. It includes:

- a manifest;
- the installed Python application and all runtime dependencies in a ready-to-run virtual
  environment; and
- the built frontend assets for that role.

The Pi does not run `apt`, `uv sync`, `pip`, `npm` or `pnpm` during first boot. It does not compile
Python packages or build a frontend.

Install releases under:

```text
/opt/e87canbus/releases/<application-digest>/
/opt/e87canbus/current -> releases/<application-digest>
```

Systemd services execute through `current`. Configuration lives in `/etc/e87canbus`; mutable data
lives in `/var/lib/e87canbus`. The application archive contains no absolute paths and cannot write
outside its release directory.

The manifest binds the bundle to one role, `linux-aarch64`, the host Python version and a compatible
provisioning-interface version. The CLI and first-boot consumer reject mismatches before
activation. This layout may support later atomic deployment, but deployment and rollback behavior
are not implemented here.

## Provisioning bundle

The CLI writes one `e87canbus-provisioning-v1.zip` to the boot partition after it has written and
verified the image. The ZIP has a fixed schema:

```text
manifest.json
application.tar.gz
identity/installation-ca.pem
identity/ssh-authorized-key
network/wifi.nmconnection
configuration/device.json
configuration/operator-password.hash       coordinator only
identity/server-certificate.pem             coordinator only
identity/server-private-key.pem             coordinator only
identity/chromium-client.p12                console only
identity/chromium-client-password           console only
```

The console PKCS#12 document contains its client certificate and private key. Its generated
one-time import password is passed to the certificate tool through standard input, never a process
argument, and is removed with staging after import.

The consumer addresses known entries by exact name. It rejects duplicate or unknown entries,
links, device files, unknown manifest fields, unsupported versions and any archive path that is
absolute, contains `..` or falls outside the fixed schema. It never performs unrestricted archive
extraction.

The manifest records the expected image role and compatibility versions plus the declared size and
SHA-256 digest of every entry. The CLI validates source artifacts before creating the ZIP and reads
the completed ZIP back from the card. The consumer validates the complete ZIP before changing the
installed system.

The CLI rejects a bundle unless it fits the boot partition while preserving 64 MiB of free space.
Before staging or extracting, the consumer checks declared and actual byte counts against available
space while preserving 256 MiB on the root filesystem. Reads are bounded by the declared sizes, so
a compressed entry cannot expand without limit.

Digest checks detect corruption and incomplete writes. They are not an authenticity boundary for
initial provisioning.

## First-boot consumer and secret lifecycle

The image contains one root-owned systemd service that runs while the protected
`unprovisioned` marker exists. Role application services remain gated by that marker.

The consumer performs these phases in order:

1. Locate the exact provisioning ZIP and validate its structure, sizes, digests, compatibility and
   role without changing installed state.
2. Copy required inputs into a root-owned staging directory on the root filesystem and sync them.
3. Remove the boot-partition ZIP after durable staging succeeds.
4. Record progress and install host identity, accounts, certificates, secrets, network
   configuration and the application release.
5. Validate ownership, permissions, systemd configuration, NetworkManager configuration and the
   installed application manifest.
6. Write non-secret success status, remove staged secrets and clear `unprovisioned` last.
7. Reboot once if required, then allow the role services to start.

Progress is durable and each phase is idempotent. A power interruption resumes from the last
completed phase. Invalid input records a terminal failure and keeps role services disabled. The
first implementation has no in-place repair command; the operator corrects the input and
reprovisions the card.

Installed private keys and NetworkManager secrets use the narrowest ownership and mode required by
their consumers. The consumer never writes their values to status or the journal.

## Raspberry Pi provisioning flow

The interactive commands are:

```text
uv run e87ctl provision coordinator --installation <recovery-package>
uv run e87ctl provision console --installation <recovery-package>
```

Each command:

1. Validates the recovery package.
2. Selects a compatible image and resolves an eligible SD card.
3. Selects a deployment profile and shows the complete destructive action.
4. Revalidates the disk and requires confirmation.
5. Builds and validates the current application bundle.
6. Creates the role identity and first-boot bundle.
7. Writes the image and verifies the image-sized bytes.
8. Mounts the boot partition, writes and reads back the provisioning ZIP, then safely unmounts the
   whole disk.
9. Reports the hostname, device ID, artifact digests and `first boot pending`.

The coordinator bundle contains its HTTPS identity, installation trust certificate, Wi-Fi access
point configuration, operator password hash and SSH authorization. The console bundle contains its
client identity, installation trust certificate, Wi-Fi client configuration, Chromium certificate
configuration and SSH authorization.

Reprovisioning always rewrites the SD card. It is an explicit replacement operation.

## macOS SD-card safety

macOS is the only supported writer host in the first implementation. Use structured `diskutil`
property-list output for discovery and identity checks.

The writer must:

- resolve partitions, APFS containers and synthesized devices to their physical stores;
- protect every disk backing the running system;
- reject internal disks even when explicitly named;
- accept only a whole external physical disk, never a partition;
- reject unresolved paths, globs and ambiguous aliases;
- report the resolved device, model, capacity, serial, protocol and mounts;
- require confirmation of the resolved device, model and capacity;
- re-read and compare identity immediately before writing;
- let the operating system handle administrator authentication;
- write through the resolved raw disk device;
- read back and hash the image-sized region; and
- mount only the boot partition for bundle injection before a final whole-disk unmount.

No flag bypasses system-disk, internal-disk, whole-disk or identity checks. Mounted eligible targets
remain unavailable until the confirmed operation unmounts them.

The low-level writer accepts only a validated target value produced by these checks. It cannot
accept an arbitrary path through another call site.

## First-boot reporting and verification

Card preparation and first-boot verification are separate facts. `provision` reports only the
former.

The consumer writes detailed non-secret state to
`/var/lib/e87canbus-provisioning/status.json` and a smaller status document to the boot partition.
Both identify the format version, role, installation ID, device ID, hostname, completed phase,
artifact digests, result and a bounded safe error code. Neither contains raw configuration or
secrets.

If networking starts, `e87ctl verify` uses the coordinator HTTPS endpoint and key-only SSH access
to the selected host as appropriate. It checks:

- coordinator certificate trust and expected installation identity;
- successful bundle consumption and marker removal;
- installed application identity;
- host role, device ID and hostname;
- application and role-service health;
- Wi-Fi association and expected network configuration;
- console mutual-TLS authentication for HTTP and Socket.IO; and
- rejection of console identity on an operator-only endpoint.

An offline target is not fully verified. If first boot fails before networking starts, the operator
can power down the Pi, return the card to the Mac and read the non-secret boot-partition status.

Each check reports `passed`, `failed` or `unavailable`. Human output explains unavailable checks.
`--json` returns the same versioned structured result without prompts. The command exits nonzero if
any required check fails or remains unavailable.

## Installation replacement

Loss or suspected compromise of a Pi, its card, the management SSH key or the recovery package
invalidates the installation. Recovery is:

1. Run `e87ctl installation create` to create a new installation.
2. Reprovision the coordinator and console.
3. Replace the stored recovery package.

The first implementation does not preserve the old installation ID, certificates or passwords.
Ordinary card failure without suspected compromise may provision a replacement device using the
existing recovery package. The old credential remains valid until the installation is replaced.

## Acceptance criteria

- `e87ctl` is a top-level workstation package and is absent from Pi application bundles.
- `e87canbus` and `e87canbus-console` retain their runtime-only responsibilities.
- `e87ctl image build` is the only public image-build interface.
- The CLI keeps no hidden installation state and creates one explicit caller-owned recovery
  package without logging its secrets.
- Neither reusable image contains application code, installation secrets or cloned host identity.
- Application and provisioning bundles have fixed, versioned schemas, bounded reads, complete
  digests and explicit compatibility rules.
- First boot performs no package installation, dependency resolution or application build.
- Power loss cannot clear `unprovisioned` or enable a partially installed application.
- A fresh coordinator starts the isolated Wi-Fi network and HTTPS endpoint.
- A fresh console joins automatically and uses its client certificate without a prompt.
- A laptop with only the Wi-Fi password cannot read application data.
- The console can use every current production operation required by its UI and cannot use an
  operator-only endpoint.
- System and internal disks cannot reach the writer, including through explicit input.
- The writer detects target replacement before writing and verifies image and bundle bytes.
- Provisioning reports card preparation without claiming first-boot success.
- Online verification proves the installed identities, network path and application health.
- Rebuilt coordinator and console images pass the relevant automated and physical checks.

## Deferred work

- Routine `e87ctl deploy` and release rollback.
- Linux or Windows SD-card writers.
- Button pad, Servotronic controller and coordinator-panel provisioning.
- USB device discovery and firmware preservation rules.
- Cockpit identity or firmware.
- Credential revocation, rotation, expiry renewal or device inventory.
- Multiple operators, password recovery or a management UI.
- Disk encryption, secure boot and verified boot.
- Tagged releases or external artifact storage.

## Related specifications

The [Wi-Fi device network](wifi-device-network.md) defines the network, HTTPS and authorization
behavior enabled by this provisioning path.

The [Raspberry Pi host images](raspberry-pi-image-building.md) specification defines the
reusable images and the hardware checks that their provisionable successors must repeat.
