from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tarfile
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import ExtendedKeyUsageOID
from e87ctl.application import (
    APPLICATION_BUILDER_BASE,
    ApplicationArtifact,
    package_application,
)
from e87ctl.artifacts import (
    BOOT_FREE_RESERVE_BYTES,
    ROOT_FREE_RESERVE_BYTES,
    ApplicationManifest,
    ArtifactError,
    ImageFile,
    ImageManifest,
    canonical_json,
    digest_file,
    load_image_manifest,
    provisioning_entry_names,
    validate_application_archive,
    validate_provisioning_archive,
)
from e87ctl.provisioning import (
    ProvisioningError,
    build_provisioning_bundle,
    validate_provisioning_bundle,
)
from e87ctl.recovery import RecoveryPackage, create_recovery_package
from pydantic import ValidationError

NOW = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)
BUILDER_REVISION = "262d4df5a9f9d4133370465399a7958a7c22cdc7"


@pytest.fixture
def recovery() -> RecoveryPackage:
    return create_recovery_package(NOW)


@pytest.fixture(params=["coordinator", "console"])
def role(request: pytest.FixtureRequest) -> str:
    value = request.param
    assert isinstance(value, str)
    return value


def image_manifest(role: str) -> ImageManifest:
    return ImageManifest(
        format_version=1,
        role=role,
        raspberry_pi_model="Raspberry Pi 4 Model B",
        os_release="Raspberry Pi OS Lite Trixie",
        architecture="arm64",
        builder_revision=BUILDER_REVISION,
        built_at=NOW,
        git_commit="0" * 40,
        git_dirty=True,
        provisioning_interface_version=1,
        boot_partition_size_bytes=512 * 1024 * 1024,
        root_filesystem_size_bytes=4 * 1024 * 1024 * 1024,
        image=ImageFile(filename=f"e87-{role}.img", size_bytes=4, sha256="0" * 64),
    )


def application_artifact(tmp_path: Path, role: str) -> ApplicationArtifact:
    payload = tmp_path / f"payload-{role}"
    (payload / "venv/bin").mkdir(parents=True)
    (payload / "venv/bin/e87canbus").write_bytes(b"#!/bin/sh\n")
    (payload / "frontend").mkdir()
    (payload / "frontend/index.html").write_bytes(b"<html>release</html>\n")
    output = tmp_path / f"application-{role}.tar.gz"
    manifest = package_application(
        payload,
        output,
        role=role,  # type: ignore[arg-type]
        built_at=NOW,
        git_commit="1" * 40,
        git_dirty=True,
    )
    return ApplicationArtifact(
        path=output,
        manifest=manifest,
        size_bytes=output.stat().st_size,
        sha256=digest_file(output, max_bytes=output.stat().st_size),
    )


def test_application_archive_is_manifest_first_complete_and_reproducible(
    tmp_path: Path, role: str
) -> None:
    artifact = application_artifact(tmp_path, role)

    manifest = validate_application_archive(
        artifact.path, expected_role=role  # type: ignore[arg-type]
    )

    assert manifest == artifact.manifest
    assert manifest.builder_image == APPLICATION_BUILDER_BASE
    assert manifest.architecture == "linux-aarch64"
    assert manifest.python_version == "3.13"
    assert set(manifest.files) == {"venv/bin/e87canbus", "frontend/index.html"}
    first_bytes = artifact.path.read_bytes()
    rebuilt = application_artifact(tmp_path / "again", role)
    assert rebuilt.path.read_bytes() == first_bytes


@pytest.mark.parametrize("bad_name", ["../escape", "/absolute", "venv/../../escape"])
def test_application_archive_rejects_traversal_and_absolute_entries(
    tmp_path: Path, bad_name: str
) -> None:
    artifact = application_artifact(tmp_path, "coordinator")
    malicious = tmp_path / "malicious.tar.gz"
    with tarfile.open(artifact.path, "r:gz") as source, tarfile.open(malicious, "w:gz") as archive:
        for member in source.getmembers():
            archive.addfile(member, source.extractfile(member))
        info = tarfile.TarInfo(bad_name)
        info.size = 1
        archive.addfile(info, io.BytesIO(b"x"))

    with pytest.raises(ArtifactError, match="invalid application artifact"):
        validate_application_archive(malicious)


def test_application_archive_rejects_links_and_unknown_files(tmp_path: Path) -> None:
    artifact = application_artifact(tmp_path, "coordinator")
    malicious = tmp_path / "linked.tar.gz"
    with tarfile.open(artifact.path, "r:gz") as source, tarfile.open(malicious, "w:gz") as output:
        for member in source.getmembers():
            stream = source.extractfile(member)
            output.addfile(member, stream)
        link = tarfile.TarInfo("venv/bin/python")
        link.type = tarfile.SYMTYPE
        link.linkname = "/usr/bin/python3"
        output.addfile(link)

    with pytest.raises(ArtifactError, match="invalid application artifact"):
        validate_application_archive(malicious)


def test_strict_application_manifest_rejects_unknown_fields() -> None:
    document = {
        "format_version": 1,
        "role": "coordinator",
        "architecture": "linux-aarch64",
        "python_version": "3.13",
        "provisioning_interface_version": 1,
        "built_at": NOW.isoformat(),
        "git_commit": None,
        "git_dirty": False,
        "builder_image": APPLICATION_BUILDER_BASE,
        "builder_revision": "2" * 64,
        "python_lock_sha256": "3" * 64,
        "frontend_lock_sha256": "4" * 64,
        "files": {
            "venv/app": {"size_bytes": 1, "sha256": "0" * 64},
            "frontend/index.html": {"size_bytes": 1, "sha256": "0" * 64},
        },
        "later_option": True,
    }
    with pytest.raises(ValidationError):
        ApplicationManifest.model_validate(document)


def test_image_manifest_requires_provisioning_storage_contract() -> None:
    document = image_manifest("coordinator").model_dump()
    del document["boot_partition_size_bytes"]

    with pytest.raises(ValidationError):
        ImageManifest.model_validate(document)


def test_image_artifact_loader_checks_closed_schema_size_and_digest(tmp_path: Path) -> None:
    image = tmp_path / "e87-coordinator.img"
    image.write_bytes(b"image")
    manifest = image_manifest("coordinator").model_copy(
        update={
            "image": ImageFile(
                filename=image.name,
                size_bytes=image.stat().st_size,
                sha256=digest_file(image, max_bytes=image.stat().st_size),
            )
        }
    )
    manifest_path = image.with_suffix(".json")
    manifest_path.write_bytes(canonical_json(manifest))

    assert load_image_manifest(manifest_path, expected_role="coordinator") == manifest
    image.write_bytes(b"changed")
    with pytest.raises(ArtifactError, match="invalid image artifact"):
        load_image_manifest(manifest_path)


def test_application_builder_is_pinned_and_builds_only_runtime_payload() -> None:
    root = Path(__file__).resolve().parents[2]
    dockerfile = (root / "e87ctl/application-builder/Dockerfile").read_text()
    script = (root / "e87ctl/application-builder/build-application").read_text()
    sources = (root / "e87ctl/application-builder/debian.sources").read_text()

    assert f"FROM --platform=linux/arm64 {APPLICATION_BUILDER_BASE}" in dockerfile
    assert "snapshot.debian.org/archive/debian/20260813T000000Z" in sources
    assert "pnpm@9.15.1" in dockerfile
    assert "python3 -m venv --copies /output/venv" in script
    assert 'pnpm --filter "@e87canbus/$role" build' in script
    assert "--requirement /locked/runtime.txt" in script
    assert "--requirement /locked/build.txt" in script
    assert "--require-hashes" in script
    assert "--no-build-isolation" in script
    assert "pip install --disable-pip-version-check --no-cache-dir /source" not in script
    assert "/source/e87ctl" not in script


def test_locked_exports_cover_runtime_and_pep517_build_requirements() -> None:
    root = Path(__file__).resolve().parents[2]
    runtime = subprocess.run(
        [
            "uv",
            "export",
            "--locked",
            "--no-dev",
            "--no-emit-project",
            "--format",
            "requirements-txt",
        ],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    build = subprocess.run(
        [
            "uv",
            "export",
            "--locked",
            "--only-group",
            "application-build",
            "--no-emit-project",
            "--format",
            "requirements-txt",
        ],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    ).stdout

    assert "can-isotp==2.0.7" in runtime
    assert "hatchling==" not in runtime
    assert "hatchling==1.32.0" in build
    assert "--hash=sha256:" in runtime
    assert "--hash=sha256:" in build


def test_packaged_entry_point_runs_after_release_relocation(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    helper = root / "e87ctl/application-builder/make-entry-points-relocatable"
    payload = tmp_path / "output"
    bin_directory = payload / "venv/bin"
    bin_directory.mkdir(parents=True)
    interpreter = bin_directory / "python3"
    interpreter.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n')
    interpreter.chmod(0o755)
    entry_point = bin_directory / "e87canbus"
    entry_point.write_text("#!/output/venv/bin/python3\nprint('relocated entry point')\n")
    entry_point.chmod(0o755)
    (payload / "frontend").mkdir()
    (payload / "frontend/index.html").write_text("release")
    subprocess.run([sys.executable, helper, entry_point], check=True)
    archive_path = tmp_path / "application.tar.gz"
    package_application(
        payload,
        archive_path,
        role="coordinator",
        built_at=NOW,
        git_commit=None,
        git_dirty=False,
    )

    release = tmp_path / "opt/e87canbus/releases" / digest_file(
        archive_path, max_bytes=archive_path.stat().st_size
    )
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive.getmembers()[1:]:
            contents = archive.extractfile(member)
            assert contents is not None
            target = release / member.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(contents.read())
            target.chmod(member.mode)
    result = subprocess.run(
        [release / "venv/bin/e87canbus"],
        text=True,
        capture_output=True,
        check=True,
        env={**os.environ, "PATH": f"{release / 'venv/bin'}:{os.environ['PATH']}"},
    )
    assert result.stdout == "relocated entry point\n"


@pytest.mark.parametrize("deployment_profile", ["car", "bench"])
def test_role_bundles_bind_exact_deployment_profile_and_entries(
    tmp_path: Path,
    recovery: RecoveryPackage,
    role: str,
    deployment_profile: str,
) -> None:
    application = application_artifact(tmp_path, role)
    output = tmp_path / role / "e87canbus-provisioning-v1.zip"

    artifact = build_provisioning_bundle(
        role,  # type: ignore[arg-type]
        recovery=recovery,
        deployment_profile=deployment_profile,  # type: ignore[arg-type]
        image=image_manifest(role),
        application=application,
        output=output,
        created_at=NOW,
    )

    with zipfile.ZipFile(output) as archive:
        assert set(archive.namelist()) == provisioning_entry_names(role)  # type: ignore[arg-type]
        assert archive.namelist()[0] == "manifest.json"
        manifest_text = archive.read("manifest.json").decode()
        device_text = archive.read("configuration/device.json").decode()
        frontend = application.manifest.files["frontend/index.html"]
        assert frontend.size_bytes == len(b"<html>release</html>\n")
        assert json.loads(device_text)["deployment_profile"] == deployment_profile
    for secret in (
        recovery.wifi_password.get_secret_value(),
        recovery.operator_password.get_secret_value(),
        recovery.installation_ca_private_key.get_secret_value(),
        recovery.ssh_private_key.get_secret_value(),
    ):
        assert secret not in manifest_text
        assert secret not in device_text
    assert artifact.configuration.role == role
    assert artifact.configuration.deployment_profile == deployment_profile
    assert artifact.configuration.hostname.startswith(f"e87-{role}-")
    configuration = artifact.configuration.model_dump()
    del configuration["deployment_profile"]
    with pytest.raises(ValidationError):
        type(artifact.configuration).model_validate(configuration)
    configuration["deployment_profile"] = "road"
    with pytest.raises(ValidationError):
        type(artifact.configuration).model_validate(configuration)


def test_provisioning_streams_application_archive(
    tmp_path: Path,
    recovery: RecoveryPackage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = application_artifact(tmp_path, "coordinator")
    real_read_bytes = Path.read_bytes

    def guarded_read_bytes(path: Path) -> bytes:
        if path == application.path:
            raise AssertionError("application archive must be streamed")
        return real_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)
    artifact = build_provisioning_bundle(
        "coordinator",
        recovery=recovery,
        deployment_profile="car",
        image=image_manifest("coordinator"),
        application=application,
        output=tmp_path / "streamed.zip",
        created_at=NOW,
    )
    assert artifact.manifest.application_digest == application.sha256


def test_coordinator_leaf_has_exact_identity_role_and_server_names(
    tmp_path: Path, recovery: RecoveryPackage
) -> None:
    artifact = build_provisioning_bundle(
        "coordinator",
        recovery=recovery,
        deployment_profile="car",
        image=image_manifest("coordinator"),
        application=application_artifact(tmp_path, "coordinator"),
        output=tmp_path / "coordinator.zip",
        created_at=NOW,
    )
    with zipfile.ZipFile(artifact.path) as archive:
        certificate = x509.load_pem_x509_certificate(
            archive.read("identity/server-certificate.pem")
        )
        private_key = serialization.load_pem_private_key(
            archive.read("identity/server-private-key.pem"), password=None
        )
    san = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    expected_uri = (
        f"urn:e87canbus:device:v1:{recovery.installation_id}:coordinator:"
        f"{artifact.configuration.device_id}"
    )
    assert san.get_values_for_type(x509.UniformResourceIdentifier) == [expected_uri]
    assert san.get_values_for_type(x509.IPAddress)[0].compressed == "10.42.0.1"
    assert san.get_values_for_type(x509.DNSName) == [artifact.configuration.hostname]
    assert certificate.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value == (
        x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH])
    )
    assert certificate.not_valid_before_utc == NOW - timedelta(hours=24)
    assert certificate.not_valid_after_utc == NOW.replace(year=NOW.year + 10)
    assert private_key.public_key().public_numbers() == certificate.public_key().public_numbers()


def test_explicit_hostname_is_validated_and_bound_into_certificate(
    tmp_path: Path, recovery: RecoveryPackage
) -> None:
    application = application_artifact(tmp_path, "coordinator")
    image = image_manifest("coordinator")
    artifact = build_provisioning_bundle(
        "coordinator",
        recovery=recovery,
        deployment_profile="car",
        image=image,
        application=application,
        output=tmp_path / "named.zip",
        hostname="garage-coordinator",
        created_at=NOW,
    )
    assert artifact.configuration.hostname == "garage-coordinator"
    with pytest.raises(ProvisioningError):
        build_provisioning_bundle(
            "coordinator",
            recovery=recovery,
            deployment_profile="car",
            image=image,
            application=application,
            output=tmp_path / "invalid-name.zip",
            hostname="invalid hostname",
            created_at=NOW,
        )


def test_console_pkcs12_contains_only_its_client_identity(
    tmp_path: Path, recovery: RecoveryPackage
) -> None:
    artifact = build_provisioning_bundle(
        "console",
        recovery=recovery,
        deployment_profile="car",
        image=image_manifest("console"),
        application=application_artifact(tmp_path, "console"),
        output=tmp_path / "console.zip",
        created_at=NOW,
    )
    with zipfile.ZipFile(artifact.path) as archive:
        password = archive.read("identity/chromium-client-password")
        private_key, certificate, chain = pkcs12.load_key_and_certificates(
            archive.read("identity/chromium-client.p12"), password
        )
    assert private_key is not None and certificate is not None
    assert list(chain or []) == [recovery.authority.certificate]
    assert certificate.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value == (
        x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH])
    )
    san = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert san.get_values_for_type(x509.IPAddress) == []
    assert san.get_values_for_type(x509.DNSName) == []


def _rewrite_zip(
    source: Path,
    target: Path,
    *,
    replace: dict[str, bytes] | None = None,
    extra: tuple[zipfile.ZipInfo | str, bytes] | None = None,
) -> None:
    replacements = replace or {}
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(target, "w") as output:
        for info in original.infolist():
            output.writestr(info, replacements.get(info.filename, original.read(info)))
        if extra is not None:
            output.writestr(extra[0], extra[1])


@pytest.mark.parametrize("extra_name", ["unexpected", "../escape", "/absolute"])
def test_provisioning_archive_rejects_unknown_and_unsafe_entries(
    tmp_path: Path, recovery: RecoveryPackage, extra_name: str
) -> None:
    artifact = build_provisioning_bundle(
        "coordinator",
        recovery=recovery,
        deployment_profile="car",
        image=image_manifest("coordinator"),
        application=application_artifact(tmp_path, "coordinator"),
        output=tmp_path / "valid.zip",
        created_at=NOW,
    )
    malicious = tmp_path / "malicious.zip"
    _rewrite_zip(artifact.path, malicious, extra=(extra_name, b"x"))

    with pytest.raises(ArtifactError, match="invalid provisioning artifact"):
        validate_provisioning_archive(malicious, image=image_manifest("coordinator"))


def test_provisioning_archive_rejects_duplicate_and_link_entries(
    tmp_path: Path, recovery: RecoveryPackage
) -> None:
    artifact = build_provisioning_bundle(
        "console",
        recovery=recovery,
        deployment_profile="car",
        image=image_manifest("console"),
        application=application_artifact(tmp_path, "console"),
        output=tmp_path / "valid.zip",
        created_at=NOW,
    )
    duplicate = tmp_path / "duplicate.zip"
    with pytest.warns(UserWarning, match="Duplicate name"):
        _rewrite_zip(artifact.path, duplicate, extra=("configuration/device.json", b"{}"))
    with pytest.raises(ArtifactError):
        validate_provisioning_archive(duplicate, image=image_manifest("console"))

    link = zipfile.ZipInfo("unexpected-link")
    link.create_system = 3
    link.external_attr = 0o120777 << 16
    linked = tmp_path / "linked.zip"
    _rewrite_zip(artifact.path, linked, extra=(link, b"/etc/passwd"))
    with pytest.raises(ArtifactError):
        validate_provisioning_archive(linked, image=image_manifest("console"))


def test_provisioning_archive_rejects_corruption_and_incompatible_role(
    tmp_path: Path, recovery: RecoveryPackage
) -> None:
    artifact = build_provisioning_bundle(
        "coordinator",
        recovery=recovery,
        deployment_profile="car",
        image=image_manifest("coordinator"),
        application=application_artifact(tmp_path, "coordinator"),
        output=tmp_path / "valid.zip",
        created_at=NOW,
    )
    corrupt = tmp_path / "corrupt.zip"
    _rewrite_zip(
        artifact.path,
        corrupt,
        replace={"identity/ssh-authorized-key": b"corrupt"},
    )
    with pytest.raises(ArtifactError):
        validate_provisioning_archive(corrupt, image=image_manifest("coordinator"))
    with pytest.raises(ArtifactError):
        validate_provisioning_archive(artifact.path, image=image_manifest("console"))


def test_provisioning_archive_enforces_both_free_space_reserves(
    tmp_path: Path, recovery: RecoveryPackage
) -> None:
    artifact = build_provisioning_bundle(
        "coordinator",
        recovery=recovery,
        deployment_profile="car",
        image=image_manifest("coordinator"),
        application=application_artifact(tmp_path, "coordinator"),
        output=tmp_path / "valid.zip",
        created_at=NOW,
    )
    with pytest.raises(ArtifactError):
        validate_provisioning_archive(
            artifact.path,
            image=image_manifest("coordinator"),
            available_boot_bytes=artifact.size_bytes + BOOT_FREE_RESERVE_BYTES - 1,
        )
    uncompressed = sum(item.size_bytes for item in artifact.manifest.entries.values())
    with pytest.raises(ArtifactError):
        validate_provisioning_archive(
            artifact.path,
            image=image_manifest("coordinator"),
            available_root_bytes=uncompressed + ROOT_FREE_RESERVE_BYTES - 1,
        )


def test_semantic_validation_rejects_manifest_configuration_disagreement(
    tmp_path: Path, recovery: RecoveryPackage
) -> None:
    artifact = build_provisioning_bundle(
        "console",
        recovery=recovery,
        deployment_profile="car",
        image=image_manifest("console"),
        application=application_artifact(tmp_path, "console"),
        output=tmp_path / "valid.zip",
        created_at=NOW,
    )
    with zipfile.ZipFile(artifact.path) as archive:
        configuration = json.loads(archive.read("configuration/device.json"))
    configuration["hostname"] = "different-host"
    corrupt = tmp_path / "different.zip"
    _rewrite_zip(
        artifact.path,
        corrupt,
        replace={"configuration/device.json": json.dumps(configuration).encode()},
    )
    with pytest.raises(ProvisioningError):
        validate_provisioning_bundle(corrupt, image=image_manifest("console"))


def test_manifests_never_accept_password_or_private_key_fields(
    tmp_path: Path, recovery: RecoveryPackage
) -> None:
    artifact = build_provisioning_bundle(
        "console",
        recovery=recovery,
        deployment_profile="car",
        image=image_manifest("console"),
        application=application_artifact(tmp_path, "console"),
        output=tmp_path / "valid.zip",
        created_at=NOW,
    )
    document = artifact.manifest.model_dump(mode="json")
    document["password"] = "secret"
    with pytest.raises(ValidationError):
        type(artifact.manifest).model_validate(document)


def test_canonical_json_uses_stable_compact_encoding() -> None:
    model = image_manifest("coordinator")
    encoded = canonical_json(model)
    assert encoded.endswith(b"\n")
    assert b'": "' not in encoded
