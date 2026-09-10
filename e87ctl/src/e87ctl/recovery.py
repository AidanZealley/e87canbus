from __future__ import annotations

import json
import os
import secrets
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    SecretStr,
    field_validator,
    model_validator,
)

from e87ctl.identity import InstallationId, derive_installation_id, parse_installation_id
from e87ctl.installation import (
    InstallationAuthority,
    create_installation_authority,
    installation_ca_validity,
)

RECOVERY_FORMAT_VERSION: Literal[1] = 1
OPERATOR_USERNAME: Literal["operator"] = "operator"
_PASSWORD_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
_PASSWORD_LENGTH = 32
_SSID_PREFIX_LENGTH = 12


class RecoveryPackageError(Exception):
    """A safe-to-display recovery package error."""


class RecoveryPackage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    format_version: Literal[1]
    created_at: AwareDatetime
    installation_id: InstallationId
    installation_ca_private_key: SecretStr
    installation_ca_certificate: str
    wifi_ssid: str
    wifi_password: SecretStr
    operator_username: Literal["operator"]
    operator_password: SecretStr
    ssh_private_key: SecretStr
    ssh_public_key: str

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        if value.utcoffset() != timedelta(0) or value.microsecond != 0:
            raise ValueError("creation time must use second-precision UTC")
        return value

    @model_validator(mode="after")
    def validate_contents(self) -> RecoveryPackage:
        try:
            installation_id = parse_installation_id(self.installation_id)
            if self.wifi_ssid != f"e87canbus-{installation_id[:_SSID_PREFIX_LENGTH]}":
                raise ValueError("Wi-Fi SSID does not match the installation ID")
            _validate_password(self.wifi_password.get_secret_value())
            _validate_password(self.operator_password.get_secret_value())

            private_key = _load_ca_private_key(self.installation_ca_private_key.get_secret_value())
            certificate = _load_ca_certificate(self.installation_ca_certificate)
            _validate_authority(private_key, certificate, installation_id, self.created_at)
            ssh_private_key = _load_ssh_private_key(self.ssh_private_key.get_secret_value())
            _validate_ssh_pair(ssh_private_key, self.ssh_public_key)
        except (TypeError, ValueError) as error:
            raise ValueError("recovery package contents are inconsistent") from error
        return self

    @property
    def authority(self) -> InstallationAuthority:
        private_key = _load_ca_private_key(self.installation_ca_private_key.get_secret_value())
        certificate = _load_ca_certificate(self.installation_ca_certificate)
        return InstallationAuthority(
            parse_installation_id(self.installation_id), private_key, certificate
        )

    @property
    def ssh_management_key(self) -> ed25519.Ed25519PrivateKey:
        return _load_ssh_private_key(self.ssh_private_key.get_secret_value())

    def serialized(self) -> bytes:
        document = {
            "format_version": self.format_version,
            "created_at": self.created_at.isoformat().replace("+00:00", "Z"),
            "installation_id": self.installation_id,
            "installation_ca_private_key": self.installation_ca_private_key.get_secret_value(),
            "installation_ca_certificate": self.installation_ca_certificate,
            "wifi_ssid": self.wifi_ssid,
            "wifi_password": self.wifi_password.get_secret_value(),
            "operator_username": self.operator_username,
            "operator_password": self.operator_password.get_secret_value(),
            "ssh_private_key": self.ssh_private_key.get_secret_value(),
            "ssh_public_key": self.ssh_public_key,
        }
        return (json.dumps(document, indent=2) + "\n").encode()


class InstallationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    format_version: Literal[1] = 1
    installation_id: InstallationId
    recovery_package: str
    ca_certificate: str


def _password() -> str:
    return "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(_PASSWORD_LENGTH))


def _validate_password(value: str) -> None:
    if len(value) != _PASSWORD_LENGTH or any(
        character not in _PASSWORD_ALPHABET for character in value
    ):
        raise ValueError("invalid generated password encoding")


def _ca_private_key_pem(private_key: ec.EllipticCurvePrivateKey) -> str:
    return private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("ascii")


def _certificate_pem(certificate: x509.Certificate) -> str:
    return certificate.public_bytes(serialization.Encoding.PEM).decode("ascii")


def _ssh_private_key_pem(private_key: ed25519.Ed25519PrivateKey) -> str:
    return private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.OpenSSH,
        serialization.NoEncryption(),
    ).decode("ascii")


def _ssh_public_key_line(private_key: ed25519.Ed25519PrivateKey) -> str:
    return (
        private_key.public_key()
        .public_bytes(
            serialization.Encoding.OpenSSH,
            serialization.PublicFormat.OpenSSH,
        )
        .decode("ascii")
    )


def create_recovery_package(created_at: datetime | None = None) -> RecoveryPackage:
    created_at = (created_at or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0)
    authority = create_installation_authority(created_at)
    ssh_private_key = ed25519.Ed25519PrivateKey.generate()
    return RecoveryPackage(
        format_version=RECOVERY_FORMAT_VERSION,
        created_at=created_at,
        installation_id=authority.installation_id,
        installation_ca_private_key=SecretStr(_ca_private_key_pem(authority.private_key)),
        installation_ca_certificate=_certificate_pem(authority.certificate),
        wifi_ssid=f"e87canbus-{authority.installation_id[:_SSID_PREFIX_LENGTH]}",
        wifi_password=SecretStr(_password()),
        operator_username=OPERATOR_USERNAME,
        operator_password=SecretStr(_password()),
        ssh_private_key=SecretStr(_ssh_private_key_pem(ssh_private_key)),
        ssh_public_key=_ssh_public_key_line(ssh_private_key),
    )


def load_recovery_package(path: Path) -> RecoveryPackage:
    try:
        encoded = path.read_bytes()
        json.loads(encoded, object_pairs_hook=_reject_duplicate_fields)
        return RecoveryPackage.model_validate_json(encoded)
    except Exception:
        raise RecoveryPackageError("invalid installation recovery package") from None


def ca_sidecar_path(path: Path) -> Path:
    return path.with_name(f"{path.stem}-ca.pem")


def _reject_duplicate_fields(pairs: list[tuple[str, object]]) -> dict[str, object]:
    document: dict[str, object] = {}
    for key, value in pairs:
        if key in document:
            raise ValueError("duplicate recovery package field")
        document[key] = value
    return document


def write_recovery_package(path: Path, package: RecoveryPackage) -> Path:
    sidecar = ca_sidecar_path(path)
    descriptors: list[tuple[int, Path]] = []
    try:
        for target, mode in ((path, 0o600), (sidecar, 0o644)):
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
            descriptors.append((descriptor, target))
        _write_file(descriptors[0][0], package.serialized(), 0o600)
        _write_file(descriptors[1][0], package.installation_ca_certificate.encode("ascii"), 0o644)
    except (OSError, UnicodeError):
        for descriptor, _ in descriptors:
            with suppress(OSError):
                os.close(descriptor)
        for _, target in descriptors:
            with suppress(OSError):
                target.unlink()
        raise RecoveryPackageError("could not create installation recovery package") from None
    return sidecar


def write_ca_sidecar(path: Path, package: RecoveryPackage) -> None:
    descriptor: int | None = None
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        _write_file(descriptor, package.installation_ca_certificate.encode("ascii"), 0o644)
    except (OSError, UnicodeError):
        if descriptor is not None:
            with suppress(OSError):
                os.close(descriptor)
            with suppress(OSError):
                path.unlink()
        raise RecoveryPackageError("could not create public CA certificate") from None


def _write_file(descriptor: int, contents: bytes, mode: int) -> None:
    with os.fdopen(descriptor, "wb", closefd=False) as output:
        os.fchmod(descriptor, mode)
        output.write(contents)
        output.flush()
        os.fsync(descriptor)
    os.close(descriptor)


def _load_ca_private_key(value: str) -> ec.EllipticCurvePrivateKey:
    encoded = value.encode("ascii")
    private_key = serialization.load_pem_private_key(encoded, password=None)
    if not isinstance(private_key, ec.EllipticCurvePrivateKey) or not isinstance(
        private_key.curve, ec.SECP256R1
    ):
        raise ValueError("invalid installation CA private key")
    if _ca_private_key_pem(private_key) != value:
        raise ValueError("installation CA private key is not canonical PKCS#8 PEM")
    return private_key


def _load_ca_certificate(value: str) -> x509.Certificate:
    certificate = x509.load_pem_x509_certificate(value.encode("ascii"))
    if _certificate_pem(certificate) != value:
        raise ValueError("installation CA certificate is not canonical PEM")
    return certificate


def _load_ssh_private_key(value: str) -> ed25519.Ed25519PrivateKey:
    if not value.startswith("-----BEGIN OPENSSH PRIVATE KEY-----\n") or not value.endswith(
        "-----END OPENSSH PRIVATE KEY-----\n"
    ):
        raise ValueError("SSH management private key is not OpenSSH PEM")
    encoded = value.encode("ascii")
    private_key = serialization.load_ssh_private_key(encoded, password=None)
    if not isinstance(private_key, ed25519.Ed25519PrivateKey):
        raise ValueError("invalid SSH management private key")
    return private_key


def _validate_authority(
    private_key: ec.EllipticCurvePrivateKey,
    certificate: x509.Certificate,
    installation_id: InstallationId,
    created_at: datetime,
) -> None:
    certificate_public_key = certificate.public_key()
    if not isinstance(certificate_public_key, ec.EllipticCurvePublicKey) or not isinstance(
        certificate_public_key.curve, ec.SECP256R1
    ):
        raise ValueError("invalid installation CA certificate key")
    if private_key.public_key().public_numbers() != certificate_public_key.public_numbers():
        raise ValueError("installation CA key pair does not match")
    if derive_installation_id(certificate_public_key) != installation_id:
        raise ValueError("installation ID does not match the installation CA")
    if certificate.subject != certificate.issuer:
        raise ValueError("installation CA certificate is not self-issued")
    signature_hash_algorithm = certificate.signature_hash_algorithm
    if not isinstance(signature_hash_algorithm, hashes.SHA256):
        raise ValueError("invalid installation CA signature algorithm")
    certificate_public_key.verify(
        certificate.signature,
        certificate.tbs_certificate_bytes,
        ec.ECDSA(signature_hash_algorithm),
    )
    basic_constraints = certificate.extensions.get_extension_for_class(x509.BasicConstraints)
    if not basic_constraints.critical or basic_constraints.value != x509.BasicConstraints(
        ca=True, path_length=None
    ):
        raise ValueError("invalid installation CA basic constraints")
    key_usage = certificate.extensions.get_extension_for_class(x509.KeyUsage)
    usage = key_usage.value
    if not key_usage.critical or (
        usage.digital_signature
        or usage.content_commitment
        or usage.key_encipherment
        or usage.data_encipherment
        or usage.key_agreement
        or not usage.key_cert_sign
        or usage.crl_sign
    ):
        raise ValueError("invalid installation CA key usage")
    if len(certificate.extensions) != 2:
        raise ValueError("unexpected installation CA certificate extension")
    expected_not_before, expected_not_after = installation_ca_validity(created_at.astimezone(UTC))
    if (
        certificate.not_valid_before_utc != expected_not_before
        or certificate.not_valid_after_utc != expected_not_after
    ):
        raise ValueError("installation CA validity does not match creation time")
def _validate_ssh_pair(private_key: ed25519.Ed25519PrivateKey, public_key: str) -> None:
    if public_key != _ssh_public_key_line(private_key):
        raise ValueError("SSH management key pair does not match")
    parsed_public_key = serialization.load_ssh_public_key(public_key.encode("ascii"))
    if not isinstance(parsed_public_key, ed25519.Ed25519PublicKey):
        raise ValueError("invalid SSH management public key")
