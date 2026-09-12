from __future__ import annotations

import hashlib
import importlib.machinery
import importlib.util
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import pytest
from e87ctl.application import ApplicationArtifact, package_application
from e87ctl.artifacts import ImageFile, ImageManifest, digest_file
from e87ctl.provisioning import build_provisioning_bundle
from e87ctl.recovery import create_recovery_package

ROOT = Path(__file__).resolve().parents[2]
CONSUMER = ROOT / "deploy/bin/e87canbus-provision"
NOW = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)


def load_consumer() -> ModuleType:
    loader = importlib.machinery.SourceFileLoader("e87canbus_provision", str(CONSUMER))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def make_bundle(tmp_path: Path, role: str) -> tuple[Path, object]:
    payload = tmp_path / "payload"
    (payload / "venv/bin").mkdir(parents=True)
    entry_point = "e87canbus" if role == "coordinator" else "e87canbus-console"
    executable = payload / "venv/bin" / entry_point
    executable.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(0o755)
    (payload / "frontend").mkdir()
    (payload / "frontend/index.html").write_text("release\n")
    application_path = tmp_path / "application.tar.gz"
    application_manifest = package_application(
        payload,
        application_path,
        role=role,  # type: ignore[arg-type]
        built_at=NOW,
        git_commit="1" * 40,
        git_dirty=False,
    )
    application = ApplicationArtifact(
        path=application_path,
        manifest=application_manifest,
        size_bytes=application_path.stat().st_size,
        sha256=digest_file(application_path, max_bytes=application_path.stat().st_size),
    )
    image = ImageManifest(
        format_version=1,
        role=role,  # type: ignore[arg-type]
        raspberry_pi_model="Raspberry Pi 4 Model B",
        os_release="Raspberry Pi OS Lite Trixie",
        architecture="arm64",
        builder_revision="2" * 40,
        built_at=NOW,
        git_commit="3" * 40,
        git_dirty=False,
        provisioning_interface_version=1,
        boot_partition_size_bytes=2 * 1024 * 1024 * 1024,
        root_filesystem_size_bytes=4 * 1024 * 1024 * 1024,
        image=ImageFile(filename=f"e87-{role}.img", size_bytes=1, sha256="4" * 64),
    )
    artifact = build_provisioning_bundle(
        role,  # type: ignore[arg-type]
        recovery=create_recovery_package(NOW),
        image=image,
        application=application,
        output=tmp_path / "bundle.zip",
        deployment_profile="car",
        created_at=NOW,
    )
    return artifact.path, artifact


def sandbox(
    tmp_path: Path, role: str, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path, object]:
    root = tmp_path / "root"
    boot = tmp_path / "boot"
    (root / "usr/share/e87canbus").mkdir(parents=True)
    (root / "var/lib/e87canbus-provisioning").mkdir(parents=True)
    boot.mkdir()
    contract = {
        "format_version": 1,
        "role": role,
        "raspberry_pi_model": "Raspberry Pi 4 Model B",
        "os_release": "Raspberry Pi OS Lite Trixie",
        "architecture": "arm64",
        "provisioning_interface_version": 1,
        "boot_partition_size_bytes": 2 * 1024 * 1024 * 1024,
        "root_filesystem_size_bytes": 4 * 1024 * 1024 * 1024,
    }
    (root / "usr/share/e87canbus/image-contract.json").write_text(json.dumps(contract))
    (root / "var/lib/e87canbus-provisioning/unprovisioned").touch()
    bundle, artifact = make_bundle(tmp_path, role)
    (boot / "e87canbus-provisioning-v1.zip").write_bytes(bundle.read_bytes())
    monkeypatch.setenv("E87_PROVISIONING_ROOT", str(root))
    monkeypatch.setenv("E87_PROVISIONING_BOOT", str(boot))
    return root, boot, artifact


def replace_bundle_entry(bundle: Path, name: str, contents: bytes) -> None:
    with zipfile.ZipFile(bundle) as archive:
        entries = {item.filename: archive.read(item) for item in archive.infolist()}
    entries[name] = contents
    manifest = json.loads(entries["manifest.json"])
    manifest["entries"][name] = {
        "size_bytes": len(contents),
        "sha256": hashlib.sha256(contents).hexdigest(),
    }
    entries["manifest.json"] = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name in ["manifest.json", *sorted(set(entries) - {"manifest.json"})]:
            info = zipfile.ZipInfo(entry_name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100600 << 16
            archive.writestr(info, entries[entry_name])


def test_host_identity_initialization_creates_a_missing_machine_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    consumer = load_consumer()
    commands: list[list[str]] = []
    monkeypatch.setattr(consumer, "run", commands.append)

    consumer.initialize_host_identity("e87-coordinator")

    assert commands == [
        ["hostnamectl", "set-hostname", "e87-coordinator"],
        ["systemd-machine-id-setup"],
        ["ssh-keygen", "-A"],
    ]


@pytest.mark.parametrize("role", ["coordinator", "console"])
def test_consumer_installs_and_activates_a_valid_role_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, role: str
) -> None:
    root, boot, artifact = sandbox(tmp_path, role, monkeypatch)
    consumer = load_consumer()

    assert consumer.main() == 0

    state = root / "var/lib/e87canbus-provisioning"
    status = json.loads((state / "status.json").read_text())
    assert status == json.loads((boot / "e87canbus-status-v1.json").read_text())
    assert status["result"] == "succeeded"
    assert status["artifact_digests"]["application"] == artifact.manifest.application_digest
    assert not (state / "unprovisioned").exists()
    assert not (state / "staging").exists()
    assert not (boot / "e87canbus-provisioning-v1.zip").exists()
    current = root / "opt/e87canbus/current"
    assert current.is_symlink()
    assert (current / "frontend/index.html").read_text() == "release\n"
    assert json.loads((current / "manifest.json").read_text())["role"] == role
    network = root / "etc/NetworkManager/system-connections/e87canbus-wifi.nmconnection"
    assert network.stat().st_mode & 0o777 == 0o600
    assert f"id=e87canbus-{role}-wifi" in network.read_text()
    assert artifact.configuration.hostname in (root / "etc/e87canbus/device.json").read_text()
    assert f"127.0.1.1\t{artifact.configuration.hostname}\n" in (root / "etc/hosts").read_text()
    all_status = (state / "status.json").read_text()
    all_status += (boot / "e87canbus-status-v1.json").read_text()
    assert "PRIVATE KEY" not in all_status
    assert "psk=" not in all_status
    if role == "coordinator":
        assert (root / "etc/e87canbus/server-private-key.pem").stat().st_mode & 0o777 == 0o600
        controller_env = (root / "etc/e87canbus/controller.env").read_text()
        assert "E87CANBUS_CONSOLE_ORIGIN=http://127.0.0.1:8000" in controller_env
        assert "DEV_ORIGIN" not in controller_env
    else:
        policy = json.loads((root / "etc/chromium/policies/managed/e87canbus.json").read_text())
        assert policy["AutoSelectCertificateForUrls"][0]["pattern"] == "https://10.42.0.1"


def test_invalid_bundle_changes_no_installed_state_and_keeps_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, boot, _ = sandbox(tmp_path, "coordinator", monkeypatch)
    bundle = boot / "e87canbus-provisioning-v1.zip"
    contents = bytearray(bundle.read_bytes())
    contents[len(contents) // 2] ^= 1
    bundle.write_bytes(contents)

    assert load_consumer().main() == 1

    state = root / "var/lib/e87canbus-provisioning"
    assert (state / "unprovisioned").exists()
    assert not (root / "opt/e87canbus/current").exists()
    assert not (state / "staging").exists()
    assert json.loads((state / "status.json").read_text())["result"] == "failed"
    assert bundle.exists()


def test_bundle_with_wrong_networkmanager_connection_id_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, boot, _ = sandbox(tmp_path, "coordinator", monkeypatch)
    bundle = boot / "e87canbus-provisioning-v1.zip"
    with zipfile.ZipFile(bundle) as archive:
        profile = archive.read("network/wifi.nmconnection")
    replace_bundle_entry(
        bundle,
        "network/wifi.nmconnection",
        profile.replace(b"id=e87canbus-coordinator-wifi", b"id=unexpected"),
    )

    assert load_consumer().main() == 1
    assert not (root / "opt/e87canbus/current").exists()
    assert (root / "var/lib/e87canbus-provisioning/unprovisioned").exists()


def test_interrupted_install_records_identity_and_resumes_from_durable_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, boot, artifact = sandbox(tmp_path, "coordinator", monkeypatch)
    consumer = load_consumer()
    install = consumer.install_files
    attempts = 0

    def interrupted(*args: object) -> None:
        nonlocal attempts
        attempts += 1
        install(*args)
        if attempts == 1:
            raise OSError("simulated power loss")

    monkeypatch.setattr(consumer, "install_files", interrupted)
    assert consumer.main() == 1
    assert not (boot / "e87canbus-provisioning-v1.zip").exists()
    assert (root / "var/lib/e87canbus-provisioning/staging").is_dir()
    assert (root / "var/lib/e87canbus-provisioning/unprovisioned").exists()
    root_status = json.loads((root / "var/lib/e87canbus-provisioning/status.json").read_text())
    assert root_status == json.loads((boot / "e87canbus-status-v1.json").read_text())
    assert root_status["result"] == "failed"
    assert root_status["completed_phase"] == "boot_removed"
    assert root_status["device_id"] == str(artifact.configuration.device_id)

    monkeypatch.setattr(consumer, "install_files", install)
    assert consumer.main() == 0
    assert not (root / "var/lib/e87canbus-provisioning/unprovisioned").exists()


def test_partial_release_staging_is_rebuilt_before_activation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _, artifact = sandbox(tmp_path, "coordinator", monkeypatch)
    partial = root / f"opt/e87canbus/releases/.{artifact.manifest.application_digest}.new"
    partial.mkdir(parents=True)
    (partial / "partial").write_text("incomplete")

    assert load_consumer().main() == 0

    current = root / "opt/e87canbus/current"
    assert not (current / "partial").exists()
    assert (current / "frontend/index.html").read_text() == "release\n"


def test_existing_release_must_match_every_manifest_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, boot, artifact = sandbox(tmp_path, "coordinator", monkeypatch)
    consumer = load_consumer()
    install = consumer.install_files

    def interrupted(*args: object) -> None:
        install(*args)
        raise OSError("simulated power loss")

    monkeypatch.setattr(consumer, "install_files", interrupted)
    assert consumer.main() == 1
    (root / "opt/e87canbus/current/frontend/index.html").write_text("tampered\n")

    monkeypatch.setattr(consumer, "install_files", install)
    assert consumer.main() == 1
    status = json.loads((boot / "e87canbus-status-v1.json").read_text())
    assert status["result"] == "failed"
    assert status["device_id"] == str(artifact.configuration.device_id)
    assert (root / "var/lib/e87canbus-provisioning/unprovisioned").exists()
