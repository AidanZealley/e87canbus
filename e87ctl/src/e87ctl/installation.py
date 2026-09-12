from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from e87ctl.identity import InstallationId, derive_installation_id


@dataclass(frozen=True, slots=True)
class InstallationAuthority:
    installation_id: InstallationId
    private_key: ec.EllipticCurvePrivateKey
    certificate: x509.Certificate


def installation_ca_validity(created_at: datetime) -> tuple[datetime, datetime]:
    try:
        expires_at = created_at.replace(year=created_at.year + 20)
    except ValueError:
        expires_at = created_at.replace(year=created_at.year + 20, month=2, day=28)
    return created_at - timedelta(hours=24), expires_at


def create_installation_authority(created_at: datetime) -> InstallationAuthority:
    if created_at.tzinfo is None:
        raise ValueError("creation time must include a timezone")
    created_at = created_at.astimezone(UTC).replace(microsecond=0)
    private_key = ec.generate_private_key(ec.SECP256R1())
    installation_id = derive_installation_id(private_key.public_key())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "e87canbus installation CA")])
    valid_from, valid_until = installation_ca_validity(created_at)

    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(valid_from)
        .not_valid_after(valid_until)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=False,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(private_key, algorithm=hashes.SHA256())
    )
    return InstallationAuthority(installation_id, private_key, certificate)


def hash_operator_password(password: str) -> str:
    return PasswordHasher().hash(password)
