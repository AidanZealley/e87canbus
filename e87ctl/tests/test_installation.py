from __future__ import annotations

import base64
import hashlib
import json
import logging
import stat
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from argon2 import PasswordHasher
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from e87ctl.identity import derive_installation_id
from e87ctl.installation import hash_operator_password
from e87ctl.recovery import (
    RecoveryPackage,
    RecoveryPackageError,
    ca_sidecar_path,
    create_recovery_package,
    load_recovery_package,
    write_ca_sidecar,
    write_recovery_package,
)

from e87ctl import cli

CREATED_AT = datetime(2026, 9, 10, 9, 30, tzinfo=UTC)
EXPECTED_FIELDS = {
    "format_version",
    "created_at",
    "installation_id",
    "installation_ca_private_key",
    "installation_ca_certificate",
    "wifi_ssid",
    "wifi_password",
    "operator_username",
    "operator_password",
    "ssh_private_key",
    "ssh_public_key",
}


def document(package: RecoveryPackage) -> dict[str, object]:
    serialized = package.serialized()
    parsed = json.loads(serialized)
    assert isinstance(parsed, dict)
    return parsed


def write_document(path: Path, value: dict[str, object]) -> None:
    path.write_text(json.dumps(value))


def test_installation_id_uses_complete_domain_separated_spki_digest() -> None:
    private_key = ec.derive_private_key(1, ec.SECP256R1())
    spki = private_key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    expected = (
        base64.b32encode(hashlib.sha256(b"e87canbus-installation-v1\0" + spki).digest())
        .decode("ascii")
        .rstrip("=")
        .lower()
    )

    assert derive_installation_id(private_key.public_key()) == expected
    assert len(expected) == 52


def test_generated_recovery_package_has_the_exact_v1_schema_and_credentials() -> None:
    package = create_recovery_package(CREATED_AT)
    value = document(package)

    assert set(value) == EXPECTED_FIELDS
    assert value["format_version"] == 1
    assert value["created_at"] == "2026-09-10T09:30:00Z"
    assert value["operator_username"] == "operator"
    assert value["wifi_ssid"] == f"e87canbus-{package.installation_id[:12]}"
    assert value["wifi_password"] != value["operator_password"]
    assert len(str(value["wifi_password"])) == 32
    assert len(str(value["operator_password"])) == 32

    ca_key = serialization.load_pem_private_key(
        str(value["installation_ca_private_key"]).encode(), password=None
    )
    ssh_key = serialization.load_ssh_private_key(
        str(value["ssh_private_key"]).encode(), password=None
    )
    assert isinstance(ca_key, ec.EllipticCurvePrivateKey)
    assert isinstance(ca_key.curve, ec.SECP256R1)
    assert isinstance(ssh_key, ed25519.Ed25519PrivateKey)
    assert str(value["installation_ca_private_key"]).startswith("-----BEGIN PRIVATE KEY-----")
    assert str(value["ssh_private_key"]).startswith("-----BEGIN OPENSSH PRIVATE KEY-----")
    assert str(value["ssh_public_key"]).startswith("ssh-ed25519 ")


def test_generated_ca_has_the_fixed_profile_and_validity() -> None:
    package = create_recovery_package(CREATED_AT)
    certificate = package.authority.certificate

    constraints = certificate.extensions.get_extension_for_class(x509.BasicConstraints)
    usage = certificate.extensions.get_extension_for_class(x509.KeyUsage)
    assert constraints.critical
    assert constraints.value == x509.BasicConstraints(ca=True, path_length=None)
    assert usage.critical
    assert usage.value.key_cert_sign
    assert not usage.value.digital_signature
    assert not usage.value.crl_sign
    assert certificate.not_valid_before_utc == CREATED_AT - timedelta(hours=24)
    assert certificate.not_valid_after_utc == CREATED_AT.replace(year=2046)
    assert certificate.subject == certificate.issuer
    assert derive_installation_id(certificate.public_key()) == package.installation_id


def test_recovery_round_trip_returns_fresh_typed_private_keys(tmp_path: Path) -> None:
    output = tmp_path / "installation.json"
    original = create_recovery_package(CREATED_AT)
    write_recovery_package(output, original)

    loaded = load_recovery_package(output)

    assert loaded.serialized() == original.serialized()
    assert isinstance(loaded.authority.private_key, ec.EllipticCurvePrivateKey)
    assert isinstance(loaded.ssh_management_key, ed25519.Ed25519PrivateKey)
    assert loaded.authority is not loaded.authority
    assert loaded.ssh_management_key is not loaded.ssh_management_key


def test_recovery_file_permissions_sidecar_and_no_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "named.package.json"
    package = create_recovery_package(CREATED_AT)

    sidecar = write_recovery_package(output, package)

    assert sidecar == tmp_path / "named.package-ca.pem"
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert stat.S_IMODE(sidecar.stat().st_mode) == 0o644
    assert sidecar.read_text() == package.installation_ca_certificate
    before = output.read_bytes()
    with pytest.raises(RecoveryPackageError, match="could not create"):
        write_recovery_package(output, create_recovery_package(CREATED_AT))
    assert output.read_bytes() == before


def test_existing_sidecar_prevents_partial_recovery_file(tmp_path: Path) -> None:
    output = tmp_path / "installation.json"
    sidecar = ca_sidecar_path(output)
    sidecar.write_text("keep me")

    with pytest.raises(RecoveryPackageError, match="could not create"):
        write_recovery_package(output, create_recovery_package(CREATED_AT))

    assert not output.exists()
    assert sidecar.read_text() == "keep me"


def test_public_sidecar_can_be_recreated_from_loaded_recovery(tmp_path: Path) -> None:
    output = tmp_path / "installation.json"
    package = create_recovery_package(CREATED_AT)
    sidecar = write_recovery_package(output, package)
    sidecar.unlink()

    loaded = load_recovery_package(output)
    write_ca_sidecar(sidecar, loaded)

    assert sidecar.read_text() == loaded.installation_ca_certificate


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("format_version", 2),
        ("installation_id", "a" * 52),
        ("installation_ca_private_key", "not a private key"),
        ("wifi_ssid", "e87canbus-wrong"),
        ("operator_username", "root"),
        ("ssh_public_key", "ssh-ed25519 AAAA"),
    ],
)
def test_loader_rejects_unsupported_or_inconsistent_documents(
    tmp_path: Path, field: str, replacement: object
) -> None:
    path = tmp_path / "installation.json"
    value = document(create_recovery_package(CREATED_AT))
    value[field] = replacement
    write_document(path, value)

    with pytest.raises(RecoveryPackageError, match="invalid installation recovery package"):
        load_recovery_package(path)


def test_loader_rejects_unknown_and_duplicate_fields(tmp_path: Path) -> None:
    path = tmp_path / "installation.json"
    package = create_recovery_package(CREATED_AT)
    value = document(package)
    value["unexpected"] = True
    write_document(path, value)
    with pytest.raises(RecoveryPackageError):
        load_recovery_package(path)

    encoded = package.serialized().decode()
    duplicate = encoded.replace('"format_version": 1,', '"format_version": 1, "format_version": 1,')
    path.write_text(duplicate)
    with pytest.raises(RecoveryPackageError):
        load_recovery_package(path)


def test_operator_password_hash_is_argon2id_and_verifiable() -> None:
    password = "test-only-operator-password"

    encoded = hash_operator_password(password)

    assert encoded.startswith("$argon2id$")
    assert PasswordHasher().verify(encoded, password)


@pytest.mark.parametrize("json_output", [False, True])
def test_cli_summaries_and_logs_do_not_expose_secrets(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    json_output: bool,
) -> None:
    output = tmp_path / "installation.json"
    arguments = ["installation", "create", "--output", str(output)]
    if json_output:
        arguments.append("--json")

    with caplog.at_level(logging.DEBUG):
        assert cli.main(arguments) == 0

    captured = capsys.readouterr()
    package = load_recovery_package(output)
    for secret in (
        package.installation_ca_private_key.get_secret_value(),
        package.wifi_password.get_secret_value(),
        package.operator_password.get_secret_value(),
        package.ssh_private_key.get_secret_value(),
    ):
        assert secret not in captured.out
        assert secret not in captured.err
        assert secret not in caplog.text
        assert secret not in repr(package)
    if json_output:
        assert set(json.loads(captured.out)) == {
            "format_version",
            "installation_id",
            "recovery_package",
            "ca_certificate",
        }


def test_cli_exception_boundary_does_not_print_internal_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    leaked = "test-secret-that-must-not-be-printed"

    def fail(path: Path, package: object) -> Path:
        raise RuntimeError(leaked)

    monkeypatch.setattr(cli, "write_recovery_package", fail)

    assert cli.main(["installation", "create", "--output", str(tmp_path / "out.json")]) == 1
    captured = capsys.readouterr()
    assert leaked not in captured.out
    assert leaked not in captured.err
    assert captured.err == "error: could not create installation\n"
