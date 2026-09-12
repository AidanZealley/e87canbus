from __future__ import annotations

import base64
import http.client
import json
import os
import re
import socket
import ssl
import subprocess
import tempfile
from pathlib import Path
from typing import Annotated, Literal, cast

from cryptography import x509
from cryptography.x509.oid import ExtensionOID
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    model_validator,
)

from e87ctl.artifacts import Role
from e87ctl.recovery import RecoveryPackage, load_recovery_package

CheckState = Literal["passed", "failed", "unavailable"]
INSTALLATION_PATTERN = r"^[a-z2-7]{52}$"
DEVICE_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
HOSTNAME_PATTERN = r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
SHA256_PATTERN = r"^[0-9a-f]{64}$"
SSH_FINGERPRINT_PATTERN = r"^SHA256:[A-Za-z0-9+/]{43}$"
COORDINATOR_ADDRESS = "10.42.0.1"
ROLE_ADDRESSES: dict[Role, str] = {"coordinator": COORDINATOR_ADDRESS, "console": "10.42.0.2"}
REMOTE_COMMON_CHECKS = (
    "provisioning",
    "device_identity",
    "bundle_consumption",
    "application_release",
    "host_identity",
    "role_services",
    "wifi",
    "ssh_policy",
)
REMOTE_CONSOLE_CHECKS = (
    "console_http_mtls",
    "console_socketio_mtls",
    "console_operator_rejected",
)
HTTPS_CHECKS = (
    "coordinator_identity",
    "coordinator_liveness",
    "coordinator_readiness",
    "unauthenticated_denied",
    "operator_access",
)


class VerifyCommandError(Exception):
    """A safe-to-display verification error."""


class ProvisioningStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    format_version: Literal[1]
    role: Role
    installation_id: Annotated[str, StringConstraints(pattern=INSTALLATION_PATTERN)]
    device_id: Annotated[str, StringConstraints(pattern=DEVICE_PATTERN)]
    hostname: Annotated[str, StringConstraints(pattern=HOSTNAME_PATTERN)]
    completed_phase: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    artifact_digests: dict[
        Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_-]{0,31}$")],
        Annotated[str, StringConstraints(pattern=SHA256_PATTERN)],
    ] = Field(max_length=8)
    result: Literal["pending", "succeeded", "failed"]
    error_code: Annotated[str, StringConstraints(min_length=1, max_length=64)] | None


class VerificationCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    name: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
    status: CheckState
    detail: Annotated[str, StringConstraints(min_length=1, max_length=240)]


class VerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    format_version: Literal[1] = 1
    result: Literal["passed", "failed"]
    role: Role
    installation_id: Annotated[str, StringConstraints(pattern=INSTALLATION_PATTERN)]
    device_id: Annotated[str, StringConstraints(pattern=DEVICE_PATTERN)] | None
    hostname: Annotated[str, StringConstraints(pattern=HOSTNAME_PATTERN)] | None
    checks: tuple[VerificationCheck, ...]

    @model_validator(mode="after")
    def validate_result(self) -> VerificationResult:
        names = [check.name for check in self.checks]
        if not names or len(names) != len(set(names)):
            raise ValueError("verification checks must be non-empty and unique")
        expected_result = (
            "passed" if all(check.status == "passed" for check in self.checks) else "failed"
        )
        if self.result != expected_result:
            raise ValueError("verification result does not match its checks")
        return self


def verify_device(
    role: Role,
    installation_path: Path,
    *,
    offline_status_path: Path | None = None,
    expected_host_key_fingerprint: str | None = None,
) -> VerificationResult:
    if offline_status_path is None and expected_host_key_fingerprint is None:
        raise VerifyCommandError("expected SSH host-key fingerprint is required")
    if (
        expected_host_key_fingerprint is not None
        and re.fullmatch(SSH_FINGERPRINT_PATTERN, expected_host_key_fingerprint) is None
    ):
        raise VerifyCommandError("expected SSH host-key fingerprint is invalid")
    try:
        recovery = load_recovery_package(installation_path)
        if offline_status_path is not None:
            return _verify_offline(role, recovery, offline_status_path)
        if expected_host_key_fingerprint is None:
            raise AssertionError("online fingerprint requirement was not enforced")
        return _verify_online(role, recovery, expected_host_key_fingerprint)
    except Exception:
        raise VerifyCommandError("could not verify the selected device") from None


def _verify_offline(role: Role, recovery: RecoveryPackage, status_path: Path) -> VerificationResult:
    try:
        if status_path.stat().st_size > 64 * 1024:
            raise ValueError("boot status is oversized")
        status = ProvisioningStatus.model_validate_json(status_path.read_bytes(), strict=True)
    except (OSError, ValueError):
        return _result(
            role,
            recovery.installation_id,
            None,
            None,
            [
                VerificationCheck(
                    name="boot_status", status="failed", detail="boot status is missing or invalid"
                ),
                VerificationCheck(
                    name="online_verification",
                    status="unavailable",
                    detail="offline status cannot prove the running device",
                ),
            ],
        )

    matches = status.role == role and status.installation_id == recovery.installation_id
    succeeded = status.result == "succeeded" and status.completed_phase == "complete"
    if status.result == "failed":
        detail = f"first boot failed with {status.error_code or 'unknown_error'}"
        if not matches:
            detail += "; status identity could not be confirmed"
    elif not matches:
        detail = "boot status belongs to another role or installation"
    elif succeeded:
        detail = "first boot completed successfully"
    else:
        detail = f"first boot has not completed, last phase {status.completed_phase}"
    checks = [
        VerificationCheck(
            name="boot_status",
            status="passed" if matches and succeeded else "failed",
            detail=detail,
        ),
        VerificationCheck(
            name="online_verification",
            status="unavailable",
            detail="offline status cannot prove the running device",
        ),
    ]
    return _result(role, recovery.installation_id, status.device_id, status.hostname, checks)


def _verify_online(
    role: Role, recovery: RecoveryPackage, expected_host_key_fingerprint: str
) -> VerificationResult:
    checks: list[VerificationCheck] = []
    remote = _ssh_checks(role, recovery, expected_host_key_fingerprint)
    if remote is None:
        names = ["ssh_access", *REMOTE_COMMON_CHECKS]
        if role == "console":
            names.extend(REMOTE_CONSOLE_CHECKS)
        checks.extend(
            VerificationCheck(
                name=name,
                status="unavailable",
                detail="authenticated SSH failed or returned invalid evidence",
            )
            for name in names
        )
        status = None
    else:
        checks.append(
            VerificationCheck(name="ssh_access", status="passed", detail="key-only SSH succeeded")
        )
        checks.extend(remote[0])
        status = remote[1]

    expected_coordinator_device_id = (
        status.device_id if role == "coordinator" and status is not None else None
    )
    checks.extend(
        _coordinator_https_checks(
            recovery,
            expected_device_id=expected_coordinator_device_id,
        )
    )
    return _result(
        role,
        recovery.installation_id,
        status.device_id if status else None,
        status.hostname if status else None,
        checks,
    )


def _result(
    role: Role,
    installation_id: str,
    device_id: str | None,
    hostname: str | None,
    checks: list[VerificationCheck],
) -> VerificationResult:
    result: Literal["passed", "failed"] = (
        "passed" if all(check.status == "passed" for check in checks) else "failed"
    )
    return VerificationResult(
        result=result,
        role=role,
        installation_id=installation_id,
        device_id=device_id,
        hostname=hostname,
        checks=tuple(checks),
    )


def _ssh_checks(
    role: Role, recovery: RecoveryPackage, expected_host_key_fingerprint: str
) -> tuple[list[VerificationCheck], ProvisioningStatus] | None:
    with tempfile.TemporaryDirectory(prefix="e87ctl-ssh-") as temporary:
        directory = Path(temporary)
        known_hosts = _scan_and_pin_host_key(
            ROLE_ADDRESSES[role], expected_host_key_fingerprint, directory
        )
        if known_hosts is None:
            return None
        key_path = directory / "management-key"
        key_path.write_text(recovery.ssh_private_key.get_secret_value())
        os.chmod(key_path, 0o600)
        output_path = directory / "remote-output"
        try:
            with output_path.open("wb") as output:
                completed = subprocess.run(
                    [
                        "ssh",
                        "-o",
                        "BatchMode=yes",
                        "-o",
                        "ConnectTimeout=10",
                        "-o",
                        "IdentitiesOnly=yes",
                        "-o",
                        "StrictHostKeyChecking=yes",
                        "-o",
                        f"UserKnownHostsFile={known_hosts}",
                        "-i",
                        str(key_path),
                        f"e87-admin@{ROLE_ADDRESSES[role]}",
                        "sudo",
                        "-n",
                        "/opt/e87canbus/current/venv/bin/python",
                        "-",
                        role,
                        recovery.installation_id,
                    ],
                    input=_REMOTE_VERIFIER.encode(),
                    stdout=output,
                    stderr=subprocess.DEVNULL,
                    timeout=180,
                    check=False,
                )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if completed.returncode != 0:
            return None
        try:
            with output_path.open("rb") as output:
                remote_output = output.read(256 * 1024 + 1)
            if len(remote_output) > 256 * 1024:
                return None
            document = json.loads(remote_output)
        except (OSError, ValueError, json.JSONDecodeError):
            return None
    try:
        if not isinstance(document, dict) or set(document) != {"status", "checks"}:
            raise ValueError
        status = ProvisioningStatus.model_validate(document["status"], strict=True)
        raw_checks = document["checks"]
        expected_checks = {
            *REMOTE_COMMON_CHECKS,
            *(REMOTE_CONSOLE_CHECKS if role == "console" else ()),
        }
        if not isinstance(raw_checks, dict) or set(raw_checks) != expected_checks:
            raise ValueError
        identity_matches = (
            status.role == role and status.installation_id == recovery.installation_id
        )
        checks = [
            VerificationCheck(
                name=name,
                status="passed"
                if value is True and (name != "device_identity" or identity_matches)
                else "failed",
                detail=(
                    "check passed"
                    if value is True and (name != "device_identity" or identity_matches)
                    else "device reported a mismatch"
                ),
            )
            for name, value in sorted(raw_checks.items())
            if isinstance(value, bool)
        ]
        if len(checks) != len(raw_checks):
            raise ValueError
        return checks, status
    except (KeyError, TypeError, ValueError, ValidationError, json.JSONDecodeError):
        return None


def _scan_and_pin_host_key(address: str, expected_fingerprint: str, directory: Path) -> Path | None:
    known_hosts = directory / "known-hosts"
    fingerprint_output = directory / "host-key-fingerprint"
    try:
        with known_hosts.open("wb") as output:
            scan = subprocess.run(
                ["ssh-keyscan", "-T", "10", "-t", "ed25519", address],
                stdout=output,
                stderr=subprocess.DEVNULL,
                timeout=15,
                check=False,
            )
        with known_hosts.open("rb") as source:
            scanned = source.read(16 * 1024 + 1)
        if scan.returncode != 0 or len(scanned) > 16 * 1024:
            return None
        lines = [line for line in scanned.decode("ascii").splitlines() if line]
        if len(lines) != 1:
            return None
        host, key_type, encoded_key = lines[0].split()
        if (
            host != address
            or key_type != "ssh-ed25519"
            or re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", encoded_key) is None
        ):
            return None
        os.chmod(known_hosts, 0o600)
        with fingerprint_output.open("wb") as output:
            fingerprint = subprocess.run(
                ["ssh-keygen", "-l", "-E", "sha256", "-f", str(known_hosts)],
                stdout=output,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
            )
        with fingerprint_output.open("rb") as source:
            fingerprint_text = source.read(4097)
        fields = fingerprint_text.decode("ascii").split()
        if (
            fingerprint.returncode != 0
            or len(fingerprint_text) > 4096
            or len(fields) < 4
            or fields[1] != expected_fingerprint
            or fields[-1] != "(ED25519)"
        ):
            return None
    except (OSError, UnicodeDecodeError, ValueError, subprocess.TimeoutExpired):
        return None
    return known_hosts


def _coordinator_https_checks(
    recovery: RecoveryPackage, *, expected_device_id: str | None
) -> list[VerificationCheck]:
    try:
        context = ssl.create_default_context(cadata=recovery.installation_ca_certificate)
        with (
            socket.create_connection((COORDINATOR_ADDRESS, 443), timeout=10) as connection,
            context.wrap_socket(connection, server_hostname=COORDINATOR_ADDRESS) as tls,
        ):
            encoded_certificate = tls.getpeercert(binary_form=True)
            if encoded_certificate is None:
                raise ValueError("coordinator did not supply a certificate")
            certificate = x509.load_der_x509_certificate(encoded_certificate)
        certificate_device_id = _certificate_device_id(
            certificate, recovery.installation_id, "coordinator"
        )
    except Exception:
        return [
            VerificationCheck(
                name=name, status="unavailable", detail="trusted coordinator HTTPS is unavailable"
            )
            for name in HTTPS_CHECKS
        ]

    operator = base64.b64encode(
        f"{recovery.operator_username}:{recovery.operator_password.get_secret_value()}".encode()
    ).decode("ascii")
    requests: tuple[tuple[str, str, dict[str, str], int], ...] = (
        ("coordinator_liveness", "/health/live", {}, 200),
        (
            "coordinator_readiness",
            "/health/ready",
            {"Authorization": f"Basic {operator}"},
            200,
        ),
        ("unauthenticated_denied", "/health/ready", {}, 401),
        (
            "operator_access",
            "/api/system/provisioning",
            {"Authorization": f"Basic {operator}"},
            200,
        ),
    )
    results: dict[str, VerificationCheck] = {}
    coordinator_status: ProvisioningStatus | None = None
    for name, path, headers, expected_status in requests:
        try:
            code, body = _https_request(context, "GET", path, headers)
            passed = code == expected_status
            if name == "operator_access" and passed:
                try:
                    coordinator_status = ProvisioningStatus.model_validate_json(body, strict=True)
                except ValidationError:
                    passed = False
                else:
                    passed = (
                        coordinator_status.role == "coordinator"
                        and coordinator_status.installation_id == recovery.installation_id
                    )
            results[name] = VerificationCheck(
                name=name,
                status="passed" if passed else "failed",
                detail=(
                    "HTTPS policy check passed"
                    if passed
                    else f"unexpected or invalid HTTP response {code}"
                ),
            )
        except Exception:
            results[name] = VerificationCheck(
                name=name, status="unavailable", detail="HTTPS request failed"
            )

    identity_reference = expected_device_id or (
        coordinator_status.device_id if coordinator_status is not None else None
    )
    if identity_reference is None:
        identity = VerificationCheck(
            name="coordinator_identity",
            status="unavailable",
            detail="coordinator status is unavailable for complete identity comparison",
        )
    else:
        matches = certificate_device_id == identity_reference and (
            coordinator_status is not None and coordinator_status.device_id == identity_reference
        )
        identity = VerificationCheck(
            name="coordinator_identity",
            status="passed" if matches else "failed",
            detail=(
                "trusted coordinator certificate and status match the complete device identity"
                if matches
                else "coordinator certificate or status device identity does not match"
            ),
        )
    return [identity, *(results[name] for name in HTTPS_CHECKS[1:])]


def _certificate_device_id(
    certificate: x509.Certificate, installation_id: str, role: Role
) -> str | None:
    alternative_names = cast(
        x509.SubjectAlternativeName,
        certificate.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value,
    )
    uris = alternative_names.get_values_for_type(x509.UniformResourceIdentifier)
    pattern = re.compile(
        rf"urn:e87canbus:device:v1:{re.escape(installation_id)}:{role}:"
        + f"({DEVICE_PATTERN.removeprefix('^').removesuffix('$')})"
    )
    if len(uris) != 1 or (match := pattern.fullmatch(uris[0])) is None:
        return None
    return match.group(1)


def _https_request(
    context: ssl.SSLContext, method: str, path: str, headers: dict[str, str]
) -> tuple[int, bytes]:
    connection = http.client.HTTPSConnection(COORDINATOR_ADDRESS, timeout=10, context=context)
    try:
        connection.request(method, path, headers=headers)
        response = connection.getresponse()
        body = response.read(64 * 1024 + 1)
        if len(body) > 64 * 1024:
            raise ValueError("HTTPS response is oversized")
        return response.status, body
    finally:
        connection.close()


def render_human(result: VerificationResult) -> str:
    lines = [f"Verification v{result.format_version} {result.result} for {result.role}"]
    if result.hostname is not None:
        lines.append(f"Host: {result.hostname}")
    if result.device_id is not None:
        lines.append(f"Device ID: {result.device_id}")
    lines.append(f"Installation ID: {result.installation_id}")
    for check in result.checks:
        lines.append(f"{check.status.upper():11} {check.name}: {check.detail}")
    return "\n".join(lines)


_REMOTE_VERIFIER = r"""
import hashlib, http.client, json, os, pathlib, secrets, ssl, subprocess, sys, tempfile
from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat
from cryptography.hazmat.primitives.serialization.pkcs12 import load_key_and_certificates
from cryptography.x509.oid import ExtensionOID

def read_json(path, limit):
    if path.stat().st_size > limit:
        raise ValueError("oversized JSON")
    return json.loads(path.read_bytes())

role, expected_installation = sys.argv[1:]
status_path = pathlib.Path("/var/lib/e87canbus-provisioning/status.json")
status = read_json(status_path, 64 * 1024)
device = read_json(pathlib.Path("/etc/e87canbus/device.json"), 32 * 1024)
digests = status.get("artifact_digests", {})
application_digest = digests.get("application", "")
current = pathlib.Path("/opt/e87canbus/current")
services = (["e87canbus-kcan.service", "e87canbus-ptcan.service", "e87canbus-fcan.service",
             "e87canbus-controller.service", "e87canbus-firewall.service",
             "e87canbus-dnsmasq.service", "e87canbus-nginx.service"] if role == "coordinator"
            else ["e87canbus-console-kcan.service", "e87canbus-console.service",
                  "e87canbus-console-kiosk.service"])

def command_ok(command):
    completed = subprocess.run(
        command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    return completed.returncode == 0

def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()

def application_ok():
    if len(application_digest) != 64 or not current.is_symlink():
        return False
    expected = pathlib.Path("/opt/e87canbus/releases") / application_digest
    try:
        if current.resolve() != expected:
            return False
        manifest = read_json(current / "manifest.json", 1024 * 1024)
    except Exception:
        return False
    if set(manifest) != {
        "format_version", "role", "architecture", "python_version",
        "provisioning_interface_version", "built_at", "git_commit", "git_dirty",
        "builder_image", "builder_revision", "python_lock_sha256", "frontend_lock_sha256",
        "files"
    } or manifest.get("role") != role or manifest.get("format_version") != 1 or \
            manifest.get("architecture") != "linux-aarch64" or \
            manifest.get("provisioning_interface_version") != 1:
        return False
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        return False
    paths = list(current.rglob("*"))
    if any(path.is_symlink() or (not path.is_dir() and not path.is_file()) for path in paths):
        return False
    actual = {
        path.relative_to(current).as_posix()
        for path in paths if path.is_file()
    }
    if actual != {"manifest.json", *files}:
        return False
    for name, record in files.items():
        path = current / name
        if not isinstance(name, str) or not isinstance(record, dict) or \
                not name or name.startswith("/") or "\\" in name or \
                ".." in pathlib.PurePosixPath(name).parts or \
                pathlib.PurePosixPath(name).as_posix() != name or \
                set(record) != {"size_bytes", "sha256"} or path.is_symlink():
            return False
        if path.stat().st_size != record["size_bytes"] or digest(path) != record["sha256"]:
            return False
    return True

def ssh_policy_ok():
    completed = subprocess.run(
        ["/usr/sbin/sshd", "-T"], text=True, capture_output=True
    )
    if completed.returncode != 0:
        return False
    settings = dict(
        line.split(None, 1) for line in completed.stdout.splitlines() if " " in line
    )
    return settings.get("authenticationmethods") == "publickey" and \
        settings.get("passwordauthentication") == "no" and \
        settings.get("kbdinteractiveauthentication") == "no" and \
        settings.get("permitrootlogin") == "no" and \
        settings.get("allowusers") == "e87-admin"

checks = {
    "provisioning": status.get("result") == "succeeded" and
        status.get("completed_phase") == "complete",
    "device_identity": status.get("role") == role == device.get("role") and
        status.get("installation_id") == expected_installation == device.get("installation_id") and
        status.get("device_id") == device.get("device_id") and
        status.get("hostname") == device.get("hostname"),
    "bundle_consumption": not pathlib.Path(
        "/var/lib/e87canbus-provisioning/unprovisioned"
    ).exists() and
        not pathlib.Path("/var/lib/e87canbus-provisioning/staging").exists() and
        not pathlib.Path("/boot/firmware/e87canbus-provisioning-v1.zip").exists(),
    "application_release": application_ok(),
    "host_identity": pathlib.Path("/etc/machine-id").read_text().strip() not in {
        "", "uninitialized"
    } and any(pathlib.Path("/etc/ssh").glob("ssh_host_*_key")) and
        os.uname().nodename == status.get("hostname"),
    "role_services": command_ok(["systemctl", "is-active", "--quiet", *services]),
    "ssh_policy": ssh_policy_ok(),
}
connection = "e87canbus-coordinator-wifi" if role == "coordinator" else "e87canbus-console-wifi"
expected_address = "10.42.0.1/24" if role == "coordinator" else "10.42.0.2/24"
def nm(field):
    return subprocess.run(["nmcli", "-g", field, "connection", "show", connection],
                          text=True, capture_output=True).stdout.strip()
checks["wifi"] = (nm("GENERAL.STATE") == "activated" and
                  nm("802-11-wireless-security.key-mgmt") == "sae" and
                  nm("802-11-wireless-security.pmf") == "3" and
                  nm("ipv4.addresses") == expected_address and
                  nm("ipv4.gateway") == "" and nm("ipv4.dns") == "" and
                  nm("ipv4.never-default") == "yes" and
                  subprocess.run(["sysctl", "-n", "net.ipv4.ip_forward"],
                                 text=True, capture_output=True).stdout.strip() == "0" and
                  subprocess.run(["sysctl", "-n", "net.ipv6.conf.all.forwarding"],
                                 text=True, capture_output=True).stdout.strip() == "0")
if role == "coordinator":
    checks["wifi"] = checks["wifi"] and command_ok(
        ["nft", "list", "table", "inet", "e87canbus"]
    ) and command_ok(
        ["dnsmasq", "--test", "--conf-file=/etc/e87canbus/dnsmasq.conf"]
    )

if role == "console":
    try:
        with tempfile.TemporaryDirectory(prefix="e87-verify-") as temporary:
            directory = pathlib.Path(temporary)
            password = secrets.token_urlsafe(24)
            password_file = directory / "password"
            password_file.write_text(password)
            os.chmod(password_file, 0o600)
            bundle = directory / "console.p12"
            subprocess.run(["pk12util", "-o", str(bundle), "-n", "e87canbus console", "-d",
                            "sql:/var/lib/e87-kiosk/.pki/nssdb", "-k", "/dev/null", "-w",
                            str(password_file)], check=True, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
            key, certificate, _ = load_key_and_certificates(bundle.read_bytes(), password.encode())
            if key is None or certificate is None:
                raise ValueError
            san = certificate.extensions.get_extension_for_oid(
                ExtensionOID.SUBJECT_ALTERNATIVE_NAME
            ).value
            uris = san.get_values_for_type(x509.UniformResourceIdentifier)
            expected_uri = (
                "urn:e87canbus:device:v1:" + expected_installation + ":console:" +
                str(status.get("device_id"))
            )
            if uris != [expected_uri]:
                raise ValueError
            key_file, certificate_file = directory / "key.pem", directory / "certificate.pem"
            key_file.write_bytes(
                key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
            )
            certificate_file.write_bytes(certificate.public_bytes(Encoding.PEM))
            os.chmod(key_file, 0o600)
            context = ssl.create_default_context(cafile="/etc/e87canbus/installation-ca.pem")
            context.load_cert_chain(certificate_file, key_file)
            def request(method, path, body=None):
                connection = http.client.HTTPSConnection("10.42.0.1", timeout=10, context=context)
                headers = {"Content-Type": "text/plain;charset=UTF-8"} if body is not None else {}
                try:
                    connection.request(method, path, body=body, headers=headers)
                    response = connection.getresponse()
                    data = response.read(262145)
                    if len(data) > 262144:
                        raise ValueError("HTTPS response is oversized")
                finally:
                    connection.close()
                return response.status, data
            ready, _ = request("GET", "/health/ready")
            rejected, _ = request("GET", "/api/system/provisioning")
            opened, packet = request("GET", "/socket.io/?EIO=4&transport=polling")
            session = (
                json.loads(packet[1:]).get("sid")
                if opened == 200 and packet.startswith(b"0") else None
            )
            socket_ok = False
            if session:
                path = f"/socket.io/?EIO=4&transport=polling&sid={session}"
                posted, _ = request("POST", path, b"40")
                received, events = request("GET", path)
                socket_ok = posted == 200 and received == 200 and b"controller.snapshot" in events
            checks["console_http_mtls"] = ready == 200
            checks["console_operator_rejected"] = rejected == 403
            checks["console_socketio_mtls"] = socket_ok
    except Exception:
        checks["console_http_mtls"] = False
        checks["console_operator_rejected"] = False
        checks["console_socketio_mtls"] = False

print(json.dumps({"status": status, "checks": checks}, separators=(",", ":")))
"""
