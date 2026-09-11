from __future__ import annotations

import hashlib
import json
import plistlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from e87ctl.application import ApplicationArtifact, package_application
from e87ctl.artifacts import ImageFile, ImageManifest, canonical_json, digest_file
from e87ctl.cli import main
from e87ctl.macos import (
    DiskError,
    Diskutil,
    SystemDiskutil,
    discover_eligible_disks,
    inspect_target,
    recheck_target,
    write_card,
)
from e87ctl.provision import confirmation_value, describe_disk, provision_card
from e87ctl.provisioning import ProvisioningArtifact, build_provisioning_bundle
from e87ctl.recovery import create_recovery_package, write_recovery_package

FIXTURES = Path(__file__).with_name("fixtures") / "diskutil"
NOW = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)


def _plist(name: str) -> dict[str, Any]:
    document = plistlib.loads((FIXTURES / name).read_bytes())
    assert isinstance(document, dict)
    return document


class FixtureDiskutil:
    def __init__(
        self,
        *,
        mount_point: Path | None = None,
        automount_boot: bool = False,
        unexpected_mount: bool = False,
    ) -> None:
        self.external_info = _plist("external-info.plist")
        self.mount_point = mount_point
        self.written = False
        self.boot_mounted = automount_boot
        self.unexpected_mount = unexpected_mount
        self.calls: list[tuple[str, ...]] = []

    def plist(self, *arguments: str) -> dict[str, Any]:
        self.calls.append(arguments)
        if arguments == ("info", "/"):
            return _plist("root-info.plist")
        if arguments == ("apfs", "list"):
            return _plist("apfs-list.plist")
        if arguments == ("info", "disk0"):
            return _plist("internal-info.plist")
        if arguments == ("info", "disk3"):
            return _plist("synthesized-info.plist")
        if arguments == ("info", "disk4"):
            return self.external_info
        if arguments == ("info", "disk4s1") and self.mount_point is not None:
            result: dict[str, Any] = {"DeviceIdentifier": "disk4s1"}
            if self.boot_mounted:
                result["MountPoint"] = str(self.mount_point)
            return result
        if arguments in {("list",), ("list", "disk0"), ("list", "disk3"), ("list", "disk4")}:
            if arguments == ("list", "disk4") and self.written:
                partitions = [
                    {
                        "DeviceIdentifier": "disk4s1",
                        "VolumeName": "bootfs",
                        **(
                            {"MountPoint": str(self.mount_point)}
                            if self.boot_mounted and self.mount_point is not None
                            else {}
                        ),
                    }
                ]
                if self.unexpected_mount:
                    partitions.append(
                        {
                            "DeviceIdentifier": "disk4s2",
                            "VolumeName": "rootfs",
                            "MountPoint": "/Volumes/rootfs",
                        }
                    )
                return {
                    "AllDisksAndPartitions": [
                        {
                            "DeviceIdentifier": "disk4",
                            "Partitions": partitions,
                        }
                    ]
                }
            return _plist("list.plist")
        raise AssertionError(f"unexpected diskutil call: {arguments}")

    def run(self, *arguments: str) -> None:
        self.calls.append(arguments)
        if arguments == ("mount", "disk4s1"):
            self.boot_mounted = True


def _image(tmp_path: Path, role: str = "coordinator") -> tuple[ImageManifest, Path, Path]:
    image_path = tmp_path / f"e87-{role}.img"
    image_path.write_bytes(b"reusable image")
    manifest = ImageManifest(
        format_version=1,
        role=role,  # type: ignore[arg-type]
        raspberry_pi_model="Raspberry Pi 4 Model B",
        os_release="Raspberry Pi OS Lite Trixie",
        architecture="arm64",
        builder_revision="1" * 40,
        built_at=NOW,
        git_commit="2" * 40,
        git_dirty=False,
        provisioning_interface_version=1,
        boot_partition_size_bytes=512 * 1024 * 1024,
        root_filesystem_size_bytes=4 * 1024 * 1024 * 1024,
        image=ImageFile(
            filename=image_path.name,
            size_bytes=image_path.stat().st_size,
            sha256=digest_file(image_path, max_bytes=image_path.stat().st_size),
        ),
    )
    manifest_path = image_path.with_suffix(".json")
    manifest_path.write_bytes(canonical_json(manifest))
    return manifest, image_path, manifest_path


def _application(tmp_path: Path, role: str = "coordinator") -> ApplicationArtifact:
    payload = tmp_path / "payload"
    (payload / "venv/bin").mkdir(parents=True)
    (payload / "venv/bin/e87canbus").write_bytes(b"#!/bin/sh\n")
    (payload / "frontend").mkdir()
    (payload / "frontend/index.html").write_bytes(b"app\n")
    path = tmp_path / "application.tar.gz"
    manifest = package_application(
        payload,
        path,
        role=role,  # type: ignore[arg-type]
        built_at=NOW,
        git_commit=None,
        git_dirty=True,
    )
    return ApplicationArtifact(
        path=path,
        manifest=manifest,
        size_bytes=path.stat().st_size,
        sha256=digest_file(path, max_bytes=path.stat().st_size),
    )


def _bundle(
    tmp_path: Path, image: ImageManifest, application: ApplicationArtifact
) -> ProvisioningArtifact:
    return build_provisioning_bundle(
        "coordinator",
        recovery=create_recovery_package(NOW),
        image=image,
        application=application,
        output=tmp_path / "provisioning.zip",
        deployment_profile="bench",
        created_at=NOW,
    )


def test_discovery_resolves_synthesized_system_store_and_reports_external_mount() -> None:
    disks = discover_eligible_disks(FixtureDiskutil())

    assert [disk.identifier for disk in disks] == ["disk4"]
    assert disks[0].model == "SD Card Reader"
    assert disks[0].serial == "SPARE001"
    assert disks[0].protocol == "USB"
    assert disks[0].mounts == ("/Volumes/OLD",)


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (("info", "/"), ["diskutil", "info", "-plist", "/"]),
        (("list", "disk4"), ["diskutil", "list", "-plist", "disk4"]),
        (("apfs", "list"), ["diskutil", "apfs", "list", "-plist"]),
        (
            ("apfs", "list", "disk3"),
            ["diskutil", "apfs", "list", "-plist", "disk3"],
        ),
    ],
)
def test_system_diskutil_places_plist_after_the_complete_verb(
    arguments: tuple[str, ...],
    expected: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    class Completed:
        stdout = plistlib.dumps({})

    def run(command: list[str], *, check: bool, capture_output: bool) -> Completed:
        assert check is True
        assert capture_output is True
        calls.append(command)
        return Completed()

    monkeypatch.setattr("e87ctl.macos.subprocess.run", run)

    assert SystemDiskutil().plist(*arguments) == {}
    assert calls == [expected]


def test_builtin_sd_reader_media_is_eligible() -> None:
    diskutil = FixtureDiskutil()
    diskutil.external_info = _plist("builtin-sd-info.plist")

    disks = discover_eligible_disks(diskutil)

    assert [disk.identifier for disk in disks] == ["disk4"]
    assert disks[0].internal is True
    assert disks[0].protocol == "Secure Digital"
    assert disks[0].removable is True
    assert disks[0].removable_media is True
    assert disks[0].ejectable is True
    assert "built-in removable media" in describe_disk(disks[0])


def test_builtin_sd_reader_identity_change_prevents_validated_target() -> None:
    diskutil = FixtureDiskutil()
    diskutil.external_info = _plist("builtin-sd-info.plist")
    expected = inspect_target(diskutil, "disk4")
    diskutil.external_info = dict(diskutil.external_info)
    diskutil.external_info["TotalSize"] = expected.capacity_bytes + 512

    with pytest.raises(DiskError, match="changed after confirmation"):
        recheck_target(diskutil, expected)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("BusProtocol", "USB"),
        ("Removable", False),
        ("RemovableMedia", False),
        ("Ejectable", False),
    ],
)
def test_internal_media_must_match_every_builtin_sd_reader_property(
    field: str, value: str | bool
) -> None:
    diskutil = FixtureDiskutil()
    diskutil.external_info = _plist("builtin-sd-info.plist")
    diskutil.external_info[field] = value

    assert discover_eligible_disks(diskutil) == []
    with pytest.raises(DiskError, match="internal disk"):
        inspect_target(diskutil, "disk4")


def test_system_backing_disk_is_rejected_even_if_it_matches_builtin_sd_reader() -> None:
    diskutil = FixtureDiskutil()
    internal_sd = _plist("builtin-sd-info.plist")
    internal_sd.update(
        {
            "DeviceIdentifier": "disk0",
            "DeviceNode": "/dev/disk0",
        }
    )
    original_plist = diskutil.plist

    def plist(*arguments: str) -> dict[str, Any]:
        if arguments == ("info", "disk0"):
            return internal_sd
        return original_plist(*arguments)

    diskutil.plist = plist  # type: ignore[method-assign]
    with pytest.raises(DiskError, match="backs the running system"):
        inspect_target(diskutil, "disk0")


def test_system_backing_disk_is_rejected_even_when_reported_external() -> None:
    diskutil = FixtureDiskutil()
    diskutil_document = _plist("internal-info.plist")
    diskutil_document["Internal"] = False

    original_plist = diskutil.plist

    def plist(*arguments: str) -> dict[str, Any]:
        if arguments == ("info", "disk0"):
            return diskutil_document
        return original_plist(*arguments)

    diskutil.plist = plist  # type: ignore[method-assign]
    with pytest.raises(DiskError, match="backs the running system"):
        inspect_target(diskutil, "/dev/disk0")


def test_internal_disk_is_rejected_when_it_does_not_back_system() -> None:
    diskutil = FixtureDiskutil()
    internal = _plist("internal-info.plist")
    internal.update(
        {
            "DeviceIdentifier": "disk5",
            "DeviceNode": "/dev/disk5",
            "SerialNumber": "OTHER-INTERNAL",
        }
    )
    original_plist = diskutil.plist

    def plist(*arguments: str) -> dict[str, Any]:
        if arguments == ("info", "disk5"):
            return internal
        if arguments == ("list", "disk5"):
            return {"AllDisksAndPartitions": []}
        return original_plist(*arguments)

    diskutil.plist = plist  # type: ignore[method-assign]
    with pytest.raises(DiskError, match="internal disk"):
        inspect_target(diskutil, "disk5")


@pytest.mark.parametrize(
    ("selector", "message"),
    [
        ("disk4s1", "partition"),
        ("/dev/disk*", "exact"),
        ("SD Card Reader", "exact"),
        ("/dev/disk4/../disk0", "exact"),
    ],
)
def test_partition_glob_alias_and_unresolved_path_are_rejected(
    selector: str, message: str
) -> None:
    with pytest.raises(DiskError, match=message):
        inspect_target(FixtureDiskutil(), selector)


def test_identity_change_prevents_validated_target() -> None:
    diskutil = FixtureDiskutil()
    expected = inspect_target(diskutil, "disk4")
    diskutil.external_info = _plist("external-replaced-info.plist")

    with pytest.raises(DiskError, match="changed after confirmation"):
        recheck_target(diskutil, expected)


def test_writer_requires_validated_target() -> None:
    with pytest.raises(TypeError, match="validated target"):
        write_card(  # type: ignore[arg-type]
            FixtureDiskutil(),
            object(),
            image_path=Path("missing"),
            image=None,  # type: ignore[arg-type]
            provisioning=None,  # type: ignore[arg-type]
        )


def test_writer_unmounts_writes_raw_verifies_and_mounts_only_boot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    boot = tmp_path / "boot"
    boot.mkdir()
    diskutil = FixtureDiskutil(mount_point=boot)
    target = recheck_target(diskutil, inspect_target(diskutil, "disk4"))
    image, image_path, _ = _image(tmp_path)
    application = _application(tmp_path)
    provisioning = _bundle(tmp_path, image, application)
    privileged: list[list[str]] = []

    def run_privileged(command: list[str]) -> None:
        privileged.append(command)
        diskutil.written = True

    monkeypatch.setattr("e87ctl.macos._run_privileged", run_privileged)
    monkeypatch.setattr(
        "e87ctl.macos._readback_digest",
        lambda device, size: hashlib.sha256(image_path.read_bytes()[:size]).hexdigest(),
    )

    write_card(
        diskutil,
        target,
        image_path=image_path,
        image=image,
        provisioning=provisioning,
    )

    assert privileged == [
        ["dd", f"if={image_path}", "of=/dev/rdisk4", "bs=4m"]
    ]
    assert (boot / "e87canbus-provisioning-v1.zip").read_bytes() == provisioning.path.read_bytes()
    mutations = [call for call in diskutil.calls if call[0] in {"mount", "unmountDisk"}]
    assert mutations == [
        ("unmountDisk", "/dev/disk4"),
        ("mount", "disk4s1"),
        ("unmountDisk", "/dev/disk4"),
    ]


def test_writer_uses_an_already_mounted_boot_partition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    boot = tmp_path / "boot"
    boot.mkdir()
    diskutil = FixtureDiskutil(mount_point=boot, automount_boot=True)
    target = recheck_target(diskutil, inspect_target(diskutil, "disk4"))
    image, image_path, _ = _image(tmp_path)
    provisioning = _bundle(tmp_path, image, _application(tmp_path))
    monkeypatch.setattr(
        "e87ctl.macos._run_privileged",
        lambda command: setattr(diskutil, "written", True),
    )
    monkeypatch.setattr(
        "e87ctl.macos._readback_digest", lambda device, size: image.image.sha256
    )

    write_card(
        diskutil,
        target,
        image_path=image_path,
        image=image,
        provisioning=provisioning,
    )

    assert ("mount", "disk4s1") not in diskutil.calls
    assert (boot / "e87canbus-provisioning-v1.zip").is_file()


def test_writer_rejects_an_unexpected_mounted_partition_before_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    boot = tmp_path / "boot"
    boot.mkdir()
    diskutil = FixtureDiskutil(
        mount_point=boot, automount_boot=True, unexpected_mount=True
    )
    target = recheck_target(diskutil, inspect_target(diskutil, "disk4"))
    image, image_path, _ = _image(tmp_path)
    provisioning = _bundle(tmp_path, image, _application(tmp_path))
    monkeypatch.setattr(
        "e87ctl.macos._run_privileged",
        lambda command: setattr(diskutil, "written", True),
    )
    monkeypatch.setattr(
        "e87ctl.macos._readback_digest", lambda device, size: image.image.sha256
    )

    with pytest.raises(DiskError, match="other than bootfs"):
        write_card(
            diskutil,
            target,
            image_path=image_path,
            image=image,
            provisioning=provisioning,
        )

    assert not (boot / "e87canbus-provisioning-v1.zip").exists()
    assert diskutil.calls[-1] == ("unmountDisk", "/dev/disk4")


def test_readback_failure_still_unmounts_whole_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    diskutil = FixtureDiskutil(mount_point=tmp_path)
    target = recheck_target(diskutil, inspect_target(diskutil, "disk4"))
    image, image_path, _ = _image(tmp_path)
    application = _application(tmp_path)
    provisioning = _bundle(tmp_path, image, application)
    monkeypatch.setattr(
        "e87ctl.macos._run_privileged",
        lambda command: setattr(diskutil, "written", True),
    )
    monkeypatch.setattr("e87ctl.macos._readback_digest", lambda device, size: "0" * 64)

    with pytest.raises(DiskError, match="readback verification"):
        write_card(
            diskutil,
            target,
            image_path=image_path,
            image=image,
            provisioning=provisioning,
        )

    assert diskutil.calls[-1] == ("unmountDisk", "/dev/disk4")


def test_changed_image_fails_before_unmount_or_writer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    diskutil = FixtureDiskutil(mount_point=tmp_path)
    target = recheck_target(diskutil, inspect_target(diskutil, "disk4"))
    image, image_path, _ = _image(tmp_path)
    application = _application(tmp_path)
    provisioning = _bundle(tmp_path, image, application)
    image_path.write_bytes(b"replacement")
    monkeypatch.setattr(
        "e87ctl.macos._run_privileged", lambda command: pytest.fail("writer must not run")
    )
    monkeypatch.setattr(
        "e87ctl.macos._readback_digest",
        lambda device, size: pytest.fail("readback must not run"),
    )

    with pytest.raises(DiskError, match="image changed"):
        write_card(
            diskutil,
            target,
            image_path=image_path,
            image=image,
            provisioning=provisioning,
        )

    assert not any(call[0] in {"mount", "unmountDisk"} for call in diskutil.calls)


def test_complete_provision_rechecks_identity_and_returns_secret_free_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    image, _, manifest_path = _image(tmp_path)
    application = _application(tmp_path)
    recovery = create_recovery_package(NOW)
    recovery_path = tmp_path / "installation.json"
    write_recovery_package(recovery_path, recovery)
    diskutil = FixtureDiskutil()
    writes: list[ProvisioningArtifact] = []

    def writer(
        backend: Diskutil,
        target: object,
        *,
        image_path: Path,
        image: ImageManifest,
        provisioning: ProvisioningArtifact,
    ) -> None:
        assert backend is diskutil
        assert image == expected_image
        writes.append(provisioning)

    expected_image = image
    monkeypatch.setattr(
        "e87ctl.provision.build_application", lambda role, repository: application
    )
    monkeypatch.setattr("e87ctl.provision.write_card", writer)

    result = provision_card(
        "coordinator",
        installation_path=recovery_path,
        image_manifest_path=manifest_path,
        expected_target=(target := inspect_target(diskutil, "disk4")),
        deployment_profile="car",
        confirmation=confirmation_value(target),
        hostname="e87-garage-coordinator",
        repository=tmp_path,
        diskutil=diskutil,
    )

    encoded = json.dumps(result.model_dump())
    assert result.result == "card_prepared"
    assert result.first_boot == "pending"
    assert result.hostname == "e87-garage-coordinator"
    assert result.target_device == "/dev/disk4"
    assert result.target_model == "SD Card Reader"
    assert result.target_capacity_bytes == 31914983424
    assert result.target_serial == "SPARE001"
    assert result.target_protocol == "USB"
    assert result.target_mounts == ("/Volumes/OLD",)
    assert result.image_digest == image.image.sha256
    assert writes[0].configuration.deployment_profile == "car"
    for secret in (
        recovery.wifi_password.get_secret_value(),
        recovery.operator_password.get_secret_value(),
        recovery.installation_ca_private_key.get_secret_value(),
    ):
        assert secret not in encoded
    assert diskutil.calls.count(("info", "disk4")) == 2


def test_noninteractive_requires_every_choice_before_disk_access(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("e87ctl.cli.sys.platform", "darwin")
    monkeypatch.setattr(
        "e87ctl.cli.SystemDiskutil",
        lambda: pytest.fail("diskutil must not run for incomplete non-interactive input"),
    )

    result = main(
        [
            "provision",
            "coordinator",
            "--installation",
            str(tmp_path / "installation.json"),
            "--non-interactive",
        ]
    )

    assert result == 1
    assert "requires --image, --disk, --profile, --confirm" in capsys.readouterr().err
