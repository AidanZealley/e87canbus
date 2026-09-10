from __future__ import annotations

import ipaddress
import os
import secrets
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal, TypeAlias

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

from e87ctl.application import ApplicationArtifact
from e87ctl.artifacts import (
    APPLICATION_FORMAT_VERSION,
    MAX_APPLICATION_ARCHIVE_BYTES,
    PROVISIONING_FORMAT_VERSION,
    PROVISIONING_INTERFACE_VERSION,
    ROOT_FREE_RESERVE_BYTES,
    ApplicationManifest,
    FileRecord,
    ImageManifest,
    ProvisioningManifest,
    Role,
    canonical_json,
    digest_file,
    file_record,
    parse_json_model,
    validate_application_archive,
    validate_provisioning_archive,
)
from e87ctl.identity import derive_installation_id, parse_installation_id
from e87ctl.installation import hash_operator_password
from e87ctl.recovery import RecoveryPackage

_DEVICE_PASSWORD_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
_DEVICE_PASSWORD_LENGTH = 32
_ProvisioningEntry = bytes | Path
DeploymentProfile: TypeAlias = Literal["car", "bench"]
_HOSTNAME = StringConstraints(
    min_length=1,
    max_length=63,
    pattern=r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$",
)


class ProvisioningError(Exception):
    """A safe-to-display provisioning artifact error."""


class DeviceConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    format_version: Literal[1]
    role: Role
    deployment_profile: DeploymentProfile
    installation_id: Annotated[str, StringConstraints(pattern=r"^[a-z2-7]{52}$")]
    device_id: Annotated[str, StringConstraints(pattern=r"^[0-9a-f-]{36}$")]
    hostname: Annotated[str, _HOSTNAME]
    application_digest: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]

    @model_validator(mode="after")
    def validate_device_id(self) -> DeviceConfiguration:
        if str(uuid.UUID(self.device_id, version=4)) != self.device_id:
            raise ValueError("device ID is not a canonical UUIDv4")
        return self


@dataclass(frozen=True, slots=True)
class ProvisioningArtifact:
    path: Path
    manifest: ProvisioningManifest
    configuration: DeviceConfiguration
    size_bytes: int
    sha256: str


def build_provisioning_bundle(
    role: Role,
    *,
    recovery: RecoveryPackage,
    image: ImageManifest,
    application: ApplicationArtifact,
    output: Path,
    deployment_profile: DeploymentProfile,
    hostname: str | None = None,
    created_at: datetime | None = None,
) -> ProvisioningArtifact:
    try:
        created_at = (created_at or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0)
        application_manifest = validate_application_archive(
            application.path, expected_role=role
        )
        if image.role != role or application_manifest.provisioning_interface_version != (
            image.provisioning_interface_version
        ):
            raise ValueError("artifact roles or interfaces do not match")
        application_digest = digest_file(
            application.path, max_bytes=application.size_bytes
        )
        if application_digest != application.sha256:
            raise ValueError("application artifact changed after validation")

        device_id = str(uuid.uuid4())
        resolved_hostname = hostname or f"e87-{role}-{device_id.replace('-', '')[:12]}"
        configuration = DeviceConfiguration(
            format_version=1,
            role=role,
            deployment_profile=deployment_profile,
            installation_id=recovery.installation_id,
            device_id=device_id,
            hostname=resolved_hostname,
            application_digest=application_digest,
        )
        entries = _provisioning_entries(
            configuration=configuration,
            recovery=recovery,
            application_path=application.path,
            created_at=created_at,
        )
        manifest = ProvisioningManifest(
            format_version=PROVISIONING_FORMAT_VERSION,
            created_at=created_at,
            role=role,
            image_format_version=image.format_version,
            application_format_version=APPLICATION_FORMAT_VERSION,
            provisioning_interface_version=PROVISIONING_INTERFACE_VERSION,
            installation_id=recovery.installation_id,
            device_id=device_id,
            hostname=resolved_hostname,
            application_digest=application_digest,
            entries={name: _entry_record(contents) for name, contents in entries.items()},
        )
        _write_zip(output, manifest, entries)
        validated, validated_configuration = validate_provisioning_bundle(output, image=image)
        return ProvisioningArtifact(
            path=output,
            manifest=validated,
            configuration=validated_configuration,
            size_bytes=output.stat().st_size,
            sha256=digest_file(output, max_bytes=output.stat().st_size),
        )
    except ProvisioningError:
        raise
    except Exception:
        raise ProvisioningError("could not create provisioning artifact") from None


def validate_provisioning_bundle(
    path: Path,
    *,
    image: ImageManifest,
    available_boot_bytes: int | None = None,
    available_root_bytes: int | None = None,
) -> tuple[ProvisioningManifest, DeviceConfiguration]:
    try:
        manifest = validate_provisioning_archive(
            path,
            image=image,
            available_boot_bytes=available_boot_bytes,
            available_root_bytes=available_root_bytes,
        )
        with zipfile.ZipFile(path) as archive:
            configuration = parse_json_model(
                archive.read("configuration/device.json"), DeviceConfiguration
            )
            if (
                configuration.role != manifest.role
                or configuration.installation_id != manifest.installation_id
                or configuration.device_id != manifest.device_id
                or configuration.hostname != manifest.hostname
                or configuration.application_digest != manifest.application_digest
            ):
                raise ValueError("device configuration does not match manifest")
            ca = x509.load_pem_x509_certificate(archive.read("identity/installation-ca.pem"))
            public_key = ca.public_key()
            if not isinstance(public_key, ec.EllipticCurvePublicKey) or (
                parse_installation_id(manifest.installation_id)
                != derive_installation_id(public_key)
            ):
                raise ValueError("installation authority does not match manifest")
            _validate_public_ca(ca, public_key)
            if manifest.role == "coordinator":
                device_certificate = x509.load_pem_x509_certificate(
                    archive.read("identity/server-certificate.pem")
                )
                loaded_key = serialization.load_pem_private_key(
                    archive.read("identity/server-private-key.pem"), password=None
                )
                if not isinstance(loaded_key, ec.EllipticCurvePrivateKey):
                    raise ValueError("device key is invalid")
                device_private_key = loaded_key
            else:
                password = archive.read("identity/chromium-client-password").decode("ascii")
                client_key, client_certificate, chain = pkcs12.load_key_and_certificates(
                    archive.read("identity/chromium-client.p12"), password.encode("ascii")
                )
                if list(chain or []) != [ca]:
                    raise ValueError("client certificate chain is invalid")
                if not isinstance(client_key, ec.EllipticCurvePrivateKey) or (
                    client_certificate is None
                ):
                    raise ValueError("device key is invalid")
                device_private_key = client_key
                device_certificate = client_certificate
            _validate_leaf(
                device_certificate,
                device_private_key,
                ca,
                configuration,
                created_at=manifest.created_at,
            )
            application_manifest = _validate_embedded_application(
                archive, expected_role=manifest.role
            )
            root_bytes = (
                image.root_filesystem_size_bytes
                if available_root_bytes is None
                else available_root_bytes
            )
            installed_bytes = sum(
                record.size_bytes for record in application_manifest.files.values()
            ) + sum(
                record.size_bytes
                for name, record in manifest.entries.items()
                if name != "application.tar.gz"
            )
            if installed_bytes + ROOT_FREE_RESERVE_BYTES > root_bytes:
                raise ValueError("installed content does not fit the root filesystem")
            return manifest, configuration
    except Exception:
        raise ProvisioningError("invalid provisioning artifact") from None


def _validate_public_ca(
    certificate: x509.Certificate, public_key: ec.EllipticCurvePublicKey
) -> None:
    expected_subject = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "e87canbus installation CA")]
    )
    if (
        not isinstance(public_key.curve, ec.SECP256R1)
        or certificate.subject != expected_subject
        or certificate.issuer != expected_subject
        or not isinstance(certificate.signature_hash_algorithm, hashes.SHA256)
    ):
        raise ValueError("installation authority profile is invalid")
    public_key.verify(
        certificate.signature,
        certificate.tbs_certificate_bytes,
        ec.ECDSA(hashes.SHA256()),
    )
    authority_created_at = certificate.not_valid_before_utc + timedelta(hours=24)
    if certificate.not_valid_after_utc != _add_years(authority_created_at, 20):
        raise ValueError("installation authority validity is invalid")
    constraints = certificate.extensions.get_extension_for_class(x509.BasicConstraints)
    usage = certificate.extensions.get_extension_for_class(x509.KeyUsage)
    if (
        not constraints.critical
        or not constraints.value.ca
        or not usage.critical
        or usage.value.digital_signature
        or usage.value.content_commitment
        or usage.value.key_encipherment
        or usage.value.data_encipherment
        or usage.value.key_agreement
        or not usage.value.key_cert_sign
        or usage.value.crl_sign
        or len(certificate.extensions) != 2
    ):
        raise ValueError("installation authority profile is invalid")


def _provisioning_entries(
    *,
    configuration: DeviceConfiguration,
    recovery: RecoveryPackage,
    application_path: Path,
    created_at: datetime,
) -> dict[str, _ProvisioningEntry]:
    private_key, certificate = _create_leaf(recovery, configuration, created_at)
    entries: dict[str, _ProvisioningEntry] = {
        "application.tar.gz": application_path,
        "identity/installation-ca.pem": recovery.installation_ca_certificate.encode("ascii"),
        "identity/ssh-authorized-key": (recovery.ssh_public_key + "\n").encode("ascii"),
        "network/wifi.nmconnection": _network_profile(configuration.role, recovery).encode(),
        "configuration/device.json": canonical_json(configuration),
    }
    if configuration.role == "coordinator":
        entries.update(
            {
                "configuration/operator-password.hash": (
                    hash_operator_password(recovery.operator_password.get_secret_value()) + "\n"
                ).encode(),
                "identity/server-certificate.pem": certificate.public_bytes(
                    serialization.Encoding.PEM
                ),
                "identity/server-private-key.pem": private_key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8,
                    serialization.NoEncryption(),
                ),
            }
        )
    else:
        password = _device_password()
        entries.update(
            {
                "identity/chromium-client.p12": pkcs12.serialize_key_and_certificates(
                    b"e87canbus console",
                    private_key,
                    certificate,
                    [recovery.authority.certificate],
                    serialization.BestAvailableEncryption(password.encode("ascii")),
                ),
                "identity/chromium-client-password": password.encode("ascii"),
            }
        )
    return entries


def _create_leaf(
    recovery: RecoveryPackage,
    configuration: DeviceConfiguration,
    created_at: datetime,
) -> tuple[ec.EllipticCurvePrivateKey, x509.Certificate]:
    authority = recovery.authority
    private_key = ec.generate_private_key(ec.SECP256R1())
    expires_at = _add_years(created_at, 10)
    ca_expires = authority.certificate.not_valid_after_utc
    identity = (
        f"urn:e87canbus:device:v1:{configuration.installation_id}:"
        f"{configuration.role}:{configuration.device_id}"
    )
    alternative_names: list[x509.GeneralName] = [x509.UniformResourceIdentifier(identity)]
    eku = ExtendedKeyUsageOID.CLIENT_AUTH
    if configuration.role == "coordinator":
        alternative_names.extend(
            [
                x509.IPAddress(ipaddress.ip_address("10.42.0.1")),
                x509.DNSName(configuration.hostname),
            ]
        )
        eku = ExtendedKeyUsageOID.SERVER_AUTH
    certificate = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, configuration.hostname)]))
        .issuer_name(authority.certificate.subject)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(created_at - timedelta(hours=24))
        .not_valid_after(min(expires_at, ca_expires))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.SubjectAlternativeName(alternative_names), critical=False)
        .add_extension(x509.ExtendedKeyUsage([eku]), critical=False)
        .sign(authority.private_key, hashes.SHA256())
    )
    return private_key, certificate


def _validate_leaf(
    certificate: x509.Certificate,
    private_key: ec.EllipticCurvePrivateKey,
    ca: x509.Certificate,
    configuration: DeviceConfiguration,
    *,
    created_at: datetime,
) -> None:
    certificate_key = certificate.public_key()
    if not isinstance(certificate_key, ec.EllipticCurvePublicKey) or not isinstance(
        certificate_key.curve, ec.SECP256R1
    ):
        raise ValueError("device certificate key is invalid")
    if private_key.public_key().public_numbers() != certificate_key.public_numbers():
        raise ValueError("device certificate key pair does not match")
    ca_key = ca.public_key()
    if not isinstance(ca_key, ec.EllipticCurvePublicKey):
        raise ValueError("installation CA key is invalid")
    ca_key.verify(
        certificate.signature,
        certificate.tbs_certificate_bytes,
        ec.ECDSA(hashes.SHA256()),
    )
    if certificate.issuer != ca.subject:
        raise ValueError("device certificate issuer is invalid")
    if not isinstance(certificate.signature_hash_algorithm, hashes.SHA256):
        raise ValueError("device certificate signature is invalid")
    if certificate.not_valid_before_utc != created_at - timedelta(hours=24) or (
        certificate.not_valid_after_utc != min(_add_years(created_at, 10), ca.not_valid_after_utc)
    ):
        raise ValueError("device certificate validity is invalid")
    identity = (
        f"urn:e87canbus:device:v1:{configuration.installation_id}:"
        f"{configuration.role}:{configuration.device_id}"
    )
    san = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    if san.get_values_for_type(x509.UniformResourceIdentifier) != [identity]:
        raise ValueError("device identity SAN is invalid")
    expected_eku = (
        ExtendedKeyUsageOID.SERVER_AUTH
        if configuration.role == "coordinator"
        else ExtendedKeyUsageOID.CLIENT_AUTH
    )
    extended_usage = certificate.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
    if extended_usage != x509.ExtendedKeyUsage([expected_eku]):
        raise ValueError("device certificate role is invalid")
    constraints = certificate.extensions.get_extension_for_class(x509.BasicConstraints)
    usage = certificate.extensions.get_extension_for_class(x509.KeyUsage)
    if (
        not constraints.critical
        or constraints.value.ca
        or not usage.critical
        or not usage.value.digital_signature
        or usage.value.content_commitment
        or usage.value.key_encipherment
        or usage.value.data_encipherment
        or usage.value.key_agreement
        or usage.value.key_cert_sign
        or usage.value.crl_sign
    ):
        raise ValueError("device certificate key usage is invalid")
    if len(certificate.extensions) != 4:
        raise ValueError("device certificate has unexpected extensions")
    if configuration.role == "coordinator":
        if san.get_values_for_type(x509.IPAddress) != [ipaddress.ip_address("10.42.0.1")]:
            raise ValueError("coordinator IP SAN is invalid")
        if san.get_values_for_type(x509.DNSName) != [configuration.hostname]:
            raise ValueError("coordinator hostname SAN is invalid")


def _network_profile(role: Role, recovery: RecoveryPackage) -> str:
    if role == "coordinator":
        wifi = "mode=ap\n"
        ipv4 = "address1=10.42.0.1/24\nmethod=manual\nnever-default=true\n"
    else:
        wifi = "mode=infrastructure\n"
        ipv4 = "address1=10.42.0.2/24\nmethod=manual\nnever-default=true\n"
    return (
        "[connection]\n"
        f"id=e87canbus-{role}-wifi\n"
        "type=wifi\ninterface-name=wlan0\nautoconnect=true\n\n"
        "[wifi]\n"
        f"{wifi}ssid={recovery.wifi_ssid}\n\n"
        "[wifi-security]\nkey-mgmt=sae\npmf=3\n"
        f"psk={recovery.wifi_password.get_secret_value()}\n\n"
        f"[ipv4]\n{ipv4}gateway=\ndns=\nignore-auto-dns=true\n\n"
        "[ipv6]\nmethod=disabled\n"
    )


def _write_zip(
    output: Path, manifest: ProvisioningManifest, entries: dict[str, _ProvisioningEntry]
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".provisioning-", dir=output.parent)
    os.close(descriptor)
    try:
        with zipfile.ZipFile(
            temporary_name, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as archive:
            _write_zip_entry(archive, "manifest.json", canonical_json(manifest))
            for name in sorted(entries):
                _write_zip_entry(archive, name, entries[name])
        os.replace(temporary_name, output)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def _write_zip_entry(
    archive: zipfile.ZipFile, name: str, contents: _ProvisioningEntry
) -> None:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100600 << 16
    if isinstance(contents, bytes):
        archive.writestr(info, contents)
        return
    remaining = contents.stat().st_size
    with contents.open("rb") as source, archive.open(info, "w", force_zip64=True) as target:
        while remaining:
            chunk = source.read(min(1024 * 1024, remaining))
            if not chunk:
                raise ValueError("application archive ended while writing provisioning bundle")
            target.write(chunk)
            remaining -= len(chunk)
        if source.read(1):
            raise ValueError("application archive grew while writing provisioning bundle")


def _entry_record(contents: _ProvisioningEntry) -> FileRecord:
    if isinstance(contents, bytes):
        return file_record(contents)
    size = contents.stat().st_size
    return FileRecord(size_bytes=size, sha256=digest_file(contents, max_bytes=size))


def _validate_embedded_application(
    archive: zipfile.ZipFile, *, expected_role: Role
) -> ApplicationManifest:
    info = archive.getinfo("application.tar.gz")
    if info.file_size > MAX_APPLICATION_ARCHIVE_BYTES:
        raise ValueError("application archive is oversized")
    descriptor, temporary_name = tempfile.mkstemp(prefix="e87-application-", suffix=".tar.gz")
    try:
        with os.fdopen(descriptor, "wb") as temporary, archive.open(
            "application.tar.gz"
        ) as source:
            remaining = info.file_size
            while remaining:
                chunk = source.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise ValueError("application archive ended early")
                temporary.write(chunk)
                remaining -= len(chunk)
            if source.read(1):
                raise ValueError("application archive exceeds declared size")
        return validate_application_archive(Path(temporary_name), expected_role=expected_role)
    finally:
        Path(temporary_name).unlink(missing_ok=True)


def _add_years(value: datetime, years: int) -> datetime:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(year=value.year + years, month=2, day=28)


def _device_password() -> str:
    return "".join(
        secrets.choice(_DEVICE_PASSWORD_ALPHABET) for _ in range(_DEVICE_PASSWORD_LENGTH)
    )
