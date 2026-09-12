from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from e87ctl.recovery import create_recovery_package
from e87ctl.verify import (
    _REMOTE_VERIFIER,
    REMOTE_COMMON_CHECKS,
    REMOTE_CONSOLE_CHECKS,
    VerificationCheck,
    VerificationResult,
    _coordinator_https_checks,
    _scan_and_pin_host_key,
    _ssh_checks,
    _verify_offline,
    render_human,
)

from e87ctl import cli

INSTALLATION_ID = "a" * 52
DEVICE_ID = "12345678-1234-4234-8234-123456789abc"
HOST_KEY_FINGERPRINT = "SHA256:" + "A" * 43


def result(*states: str) -> VerificationResult:
    checks = tuple(
        VerificationCheck(name=f"check_{index}", status=state, detail="diagnostic detail")
        for index, state in enumerate(states)
    )
    return VerificationResult(
        result="passed" if all(state == "passed" for state in states) else "failed",
        role="console",
        installation_id=INSTALLATION_ID,
        device_id=DEVICE_ID,
        hostname="e87-console-12345678",
        checks=checks,
    )


@pytest.mark.parametrize("state", ["failed", "unavailable"])
def test_verify_exits_nonzero_without_overclaiming(
    state: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    verification = result("passed", state)
    monkeypatch.setattr(cli, "verify_device", lambda *args, **kwargs: verification)

    assert cli.main(["verify", "console", "--installation", "recovery.json"]) == 1

    output = capsys.readouterr().out
    assert "Verification v1 failed for console" in output
    assert state.upper() in output
    assert "diagnostic detail" in output


def test_json_and_human_output_represent_the_same_checks(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    verification = result("passed", "passed")
    monkeypatch.setattr(cli, "verify_device", lambda *args, **kwargs: verification)

    assert cli.main(["verify", "console", "--installation", "recovery.json", "--json"]) == 0
    document = json.loads(capsys.readouterr().out)

    assert document == verification.model_dump(mode="json")
    assert [check["name"] for check in document["checks"]] == [
        check.name for check in verification.checks
    ]
    human = render_human(verification)
    assert f"Verification v{document['format_version']}" in human
    assert all(check.name in human and check.detail in human for check in verification.checks)


def test_offline_status_is_forwarded_without_starting_online_verification(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    status = tmp_path / "e87canbus-status-v1.json"
    verification = result("failed", "unavailable")
    observed: dict[str, object] = {}

    def verify(
        role: str,
        installation: Path,
        *,
        offline_status_path: Path | None,
        expected_host_key_fingerprint: str | None,
    ) -> VerificationResult:
        observed.update(
            role=role,
            installation=installation,
            status=offline_status_path,
            fingerprint=expected_host_key_fingerprint,
        )
        return verification

    monkeypatch.setattr(cli, "verify_device", verify)

    assert (
        cli.main(
            [
                "verify",
                "coordinator",
                "--installation",
                "recovery.json",
                "--status",
                str(status),
            ]
        )
        == 1
    )
    assert observed == {
        "role": "coordinator",
        "installation": Path("recovery.json"),
        "status": status,
        "fingerprint": None,
    }


def test_online_verify_requires_an_expected_ssh_host_key(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main(["verify", "coordinator", "--installation", "recovery.json"]) == 1
    assert "expected SSH host-key fingerprint is required" in capsys.readouterr().err


def test_verify_contract_rejects_unknown_check_states() -> None:
    with pytest.raises(ValueError):
        VerificationCheck(name="bad", status="skipped", detail="not allowed")  # type: ignore[arg-type]


def test_verify_contract_rejects_duplicate_checks_and_result_overclaim() -> None:
    check = VerificationCheck(name="identity", status="failed", detail="mismatch")
    with pytest.raises(ValueError):
        VerificationResult(
            result="passed",
            role="coordinator",
            installation_id=INSTALLATION_ID,
            device_id=None,
            hostname=None,
            checks=(check,),
        )
    with pytest.raises(ValueError):
        VerificationResult(
            result="failed",
            role="coordinator",
            installation_id=INSTALLATION_ID,
            device_id=None,
            hostname=None,
            checks=(check, check),
        )


def provisioning_status(
    installation_id: str, *, role: str = "coordinator", device_id: str = DEVICE_ID
) -> dict[str, object]:
    return {
        "format_version": 1,
        "role": role,
        "installation_id": installation_id,
        "device_id": device_id,
        "hostname": f"e87-{role}-{device_id[:8]}",
        "completed_phase": "complete",
        "artifact_digests": {"application": "b" * 64, "provisioning": "c" * 64},
        "result": "succeeded",
        "error_code": None,
    }


def test_remote_result_requires_every_named_boolean_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recovery = create_recovery_package()
    checks = {name: True for name in (*REMOTE_COMMON_CHECKS, *REMOTE_CONSOLE_CHECKS)}
    document = {
        "status": provisioning_status(recovery.installation_id, role="console"),
        "checks": checks,
    }

    def run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        kwargs["stdout"].write(json.dumps(document).encode())  # type: ignore[union-attr]
        return subprocess.CompletedProcess(
            args=[],
            returncode=0,
        )

    monkeypatch.setattr(
        "e87ctl.verify._scan_and_pin_host_key",
        lambda address, fingerprint, directory: directory / "known-hosts",
    )
    monkeypatch.setattr(subprocess, "run", run)

    verified = _ssh_checks("console", recovery, HOST_KEY_FINGERPRINT)

    assert verified is not None
    assert {check.name for check in verified[0]} == set(checks)
    document["unexpected"] = True
    assert _ssh_checks("console", recovery, HOST_KEY_FINGERPRINT) is None
    document.pop("unexpected")
    checks.pop("console_socketio_mtls")
    assert _ssh_checks("console", recovery, HOST_KEY_FINGERPRINT) is None


def test_ssh_command_uses_a_temporary_key_without_secret_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recovery = create_recovery_package()
    observed: dict[str, object] = {}

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        observed.update(command=command, input=kwargs["input"])
        kwargs["stdout"].write(  # type: ignore[union-attr]
            json.dumps(
                {
                    "status": provisioning_status(recovery.installation_id),
                    "checks": {name: True for name in REMOTE_COMMON_CHECKS},
                }
            ).encode()
        )
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
        )

    monkeypatch.setattr(
        "e87ctl.verify._scan_and_pin_host_key",
        lambda address, fingerprint, directory: directory / "known-hosts",
    )
    monkeypatch.setattr(subprocess, "run", run)

    assert _ssh_checks("coordinator", recovery, HOST_KEY_FINGERPRINT) is not None

    command = observed["command"]
    assert isinstance(command, list) and all(isinstance(value, str) for value in command)
    arguments = repr(command)
    assert recovery.ssh_private_key.get_secret_value() not in arguments
    assert recovery.operator_password.get_secret_value() not in arguments
    assert observed["input"] == _REMOTE_VERIFIER.encode()
    assert "StrictHostKeyChecking=yes" in command


def test_host_key_scan_pins_only_the_expected_ed25519_fingerprint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    commands: list[list[str]] = []

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        commands.append(command)
        output = kwargs["stdout"]
        if command[0] == "ssh-keyscan":
            output.write(b"10.42.0.1 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIA==\n")  # type: ignore[union-attr]
        else:
            output.write(f"256 {HOST_KEY_FINGERPRINT} 10.42.0.1 (ED25519)\n".encode())  # type: ignore[union-attr]
        return subprocess.CompletedProcess(args=command, returncode=0)

    monkeypatch.setattr(subprocess, "run", run)

    known_hosts = _scan_and_pin_host_key("10.42.0.1", HOST_KEY_FINGERPRINT, tmp_path)

    assert known_hosts == tmp_path / "known-hosts"
    assert commands[0][:6] == ["ssh-keyscan", "-T", "10", "-t", "ed25519", "10.42.0.1"]
    assert commands[1][:5] == ["ssh-keygen", "-l", "-E", "sha256", "-f"]
    assert _scan_and_pin_host_key("10.42.0.1", "SHA256:" + "B" * 43, tmp_path) is None


def test_remote_output_is_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recovery = create_recovery_package()

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        kwargs["stdout"].write(b"x" * (256 * 1024 + 1))  # type: ignore[union-attr]
        return subprocess.CompletedProcess(args=command, returncode=0)

    monkeypatch.setattr(
        "e87ctl.verify._scan_and_pin_host_key",
        lambda address, fingerprint, directory: directory / "known-hosts",
    )
    monkeypatch.setattr(subprocess, "run", run)

    assert _ssh_checks("coordinator", recovery, HOST_KEY_FINGERPRINT) is None


def test_offline_success_remains_unavailable_as_online_evidence(tmp_path: Path) -> None:
    recovery = create_recovery_package()
    status_path = tmp_path / "e87canbus-status-v1.json"
    status_path.write_text(json.dumps(provisioning_status(recovery.installation_id)))

    verified = _verify_offline("coordinator", recovery, status_path)

    assert verified.result == "failed"
    assert [(check.name, check.status) for check in verified.checks] == [
        ("boot_status", "passed"),
        ("online_verification", "unavailable"),
    ]


def test_offline_status_read_is_bounded(tmp_path: Path) -> None:
    recovery = create_recovery_package()
    status_path = tmp_path / "e87canbus-status-v1.json"
    status_path.write_bytes(b" " * (64 * 1024 + 1))

    verified = _verify_offline("coordinator", recovery, status_path)

    assert verified.result == "failed"
    assert verified.checks[0].name == "boot_status"
    assert verified.checks[0].status == "failed"


def test_remote_identity_cannot_overclaim_a_different_installation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recovery = create_recovery_package()

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        kwargs["stdout"].write(  # type: ignore[union-attr]
            json.dumps(
                {
                    "status": provisioning_status("b" * 52),
                    "checks": {name: True for name in REMOTE_COMMON_CHECKS},
                }
            ).encode()
        )
        return subprocess.CompletedProcess(args=command, returncode=0)

    monkeypatch.setattr(
        "e87ctl.verify._scan_and_pin_host_key",
        lambda address, fingerprint, directory: directory / "known-hosts",
    )
    monkeypatch.setattr(subprocess, "run", run)

    verified = _ssh_checks("coordinator", recovery, HOST_KEY_FINGERPRINT)

    assert verified is not None
    identity = next(check for check in verified[0] if check.name == "device_identity")
    assert identity.status == "failed"


def certificate(installation_id: str, device_id: str) -> x509.Certificate:
    key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(UTC)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "coordinator")])
    return (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.UniformResourceIdentifier(
                        f"urn:e87canbus:device:v1:{installation_id}:coordinator:{device_id}"
                    )
                ]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )


class FakeTls:
    def __init__(self, encoded: bytes) -> None:
        self.encoded = encoded

    def __enter__(self) -> FakeTls:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def getpeercert(self, *, binary_form: bool = False) -> bytes:
        assert binary_form
        return self.encoded


class FakeContext:
    def __init__(self, encoded: bytes) -> None:
        self.encoded = encoded

    def wrap_socket(self, connection: object, *, server_hostname: str) -> FakeTls:
        assert server_hostname == "10.42.0.1"
        return FakeTls(self.encoded)


def test_https_identity_matches_the_complete_status_device_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recovery = create_recovery_package()
    other_device = "87654321-4321-4321-8321-cba987654321"
    encoded = certificate(recovery.installation_id, other_device).public_bytes(
        serialization.Encoding.DER
    )
    context = FakeContext(encoded)
    monkeypatch.setattr("ssl.create_default_context", lambda **kwargs: context)
    monkeypatch.setattr("socket.create_connection", lambda *args, **kwargs: FakeTls(b""))

    def request(
        context_arg: object, method: str, path: str, headers: dict[str, str]
    ) -> tuple[int, bytes]:
        if path == "/api/system/provisioning":
            return 200, json.dumps(provisioning_status(recovery.installation_id)).encode()
        if path == "/health/ready":
            return (200 if headers else 401), b""
        return 200, b""

    monkeypatch.setattr("e87ctl.verify._https_request", request)

    checks = _coordinator_https_checks(recovery, expected_device_id=DEVICE_ID)

    assert (
        next(check for check in checks if check.name == "coordinator_identity").status == "failed"
    )
    assert (
        next(check for check in checks if check.name == "coordinator_readiness").status == "passed"
    )
    assert next(check for check in checks if check.name == "operator_access").status == "passed"


def test_https_identity_binds_ssh_and_operator_status_to_the_same_device(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recovery = create_recovery_package()
    other_device = "87654321-4321-4321-8321-cba987654321"
    encoded = certificate(recovery.installation_id, DEVICE_ID).public_bytes(
        serialization.Encoding.DER
    )
    context = FakeContext(encoded)
    monkeypatch.setattr("ssl.create_default_context", lambda **kwargs: context)
    monkeypatch.setattr("socket.create_connection", lambda *args, **kwargs: FakeTls(b""))

    def request(
        context_arg: object, method: str, path: str, headers: dict[str, str]
    ) -> tuple[int, bytes]:
        if path == "/api/system/provisioning":
            return 200, json.dumps(
                provisioning_status(recovery.installation_id, device_id=other_device)
            ).encode()
        if path == "/health/ready":
            return (200 if headers else 401), b""
        return 200, b""

    monkeypatch.setattr("e87ctl.verify._https_request", request)

    checks = _coordinator_https_checks(recovery, expected_device_id=DEVICE_ID)

    assert (
        next(check for check in checks if check.name == "coordinator_identity").status == "failed"
    )


def test_remote_verifier_is_valid_python() -> None:
    compile(_REMOTE_VERIFIER, "<e87ctl remote verifier>", "exec")
