from __future__ import annotations

import hashlib
import os
import plistlib
import re
import shutil
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from e87ctl.artifacts import ImageManifest, digest_file
from e87ctl.provisioning import ProvisioningArtifact, validate_provisioning_bundle

_DISK_IDENTIFIER = re.compile(r"disk[0-9]+")
_PARTITION_IDENTIFIER = re.compile(r"disk[0-9]+s[0-9]+(?:s[0-9]+)?")
_COPY_CHUNK_BYTES = 1024 * 1024


class DiskError(Exception):
    """A safe-to-display removable-disk error."""


@dataclass(frozen=True, slots=True)
class DiskIdentity:
    identifier: str
    device_node: str
    raw_device_node: str
    model: str
    capacity_bytes: int
    serial: str | None
    protocol: str
    internal: bool
    mounts: tuple[str, ...]
    device_tree_path: str | None
    media_uuid: str | None


class Diskutil(Protocol):
    def plist(self, *arguments: str) -> dict[str, Any]: ...

    def run(self, *arguments: str) -> None: ...


class SystemDiskutil:
    def plist(self, *arguments: str) -> dict[str, Any]:
        try:
            completed = subprocess.run(
                ["diskutil", *arguments, "-plist"], check=True, capture_output=True
            )
            document = plistlib.loads(completed.stdout)
            if not isinstance(document, dict):
                raise ValueError("property list root is not a dictionary")
            return document
        except Exception:
            raise DiskError("diskutil could not inspect disks") from None

    def run(self, *arguments: str) -> None:
        try:
            subprocess.run(["diskutil", *arguments], check=True)
        except Exception:
            raise DiskError("diskutil could not update disk mounts") from None


@dataclass(frozen=True, slots=True)
class _ValidatedTarget:
    identity: DiskIdentity


def discover_eligible_disks(diskutil: Diskutil) -> list[DiskIdentity]:
    protected = _system_physical_stores(diskutil)
    identities: list[DiskIdentity] = []
    for identifier in _whole_disk_identifiers(diskutil.plist("list")):
        try:
            identity = _read_whole_disk(diskutil, identifier)
        except DiskError:
            continue
        if _eligible(identity, protected):
            identities.append(identity)
    return sorted(identities, key=lambda item: item.identifier)


def inspect_target(diskutil: Diskutil, selector: str) -> DiskIdentity:
    identifier = _parse_selector(selector)
    if _PARTITION_IDENTIFIER.fullmatch(identifier):
        raise DiskError("the selected target is a partition, not a whole disk")
    identity = _read_whole_disk(diskutil, identifier)
    if not _eligible(identity, _system_physical_stores(diskutil)):
        raise DiskError("the selected disk is internal or backs the running system")
    return identity


def recheck_target(diskutil: Diskutil, expected: DiskIdentity) -> _ValidatedTarget:
    current = inspect_target(diskutil, expected.identifier)
    if current != expected:
        raise DiskError("the selected disk changed after confirmation")
    return _ValidatedTarget(current)


def write_card(
    diskutil: Diskutil,
    target: _ValidatedTarget,
    *,
    image_path: Path,
    image: ImageManifest,
    provisioning: ProvisioningArtifact,
) -> None:
    if not isinstance(target, _ValidatedTarget):
        raise TypeError("writer requires a validated target")
    try:
        if target.identity.capacity_bytes < image.image.size_bytes:
            raise DiskError("the selected disk is too small for the image")
        if digest_file(image_path, max_bytes=image.image.size_bytes) != image.image.sha256:
            raise DiskError("the image changed after validation")
        validate_provisioning_bundle(provisioning.path, image=image)
    except DiskError:
        raise
    except Exception:
        raise DiskError("provisioning artifacts changed after validation") from None

    wrote_image = False
    try:
        diskutil.run("unmountDisk", target.identity.device_node)
        wrote_image = True
        _run_privileged(
            [
                "dd",
                f"if={image_path}",
                f"of={target.identity.raw_device_node}",
                "bs=4m",
            ]
        )
        written_digest = _readback_digest(
            target.identity.raw_device_node, image.image.size_bytes
        )
        if written_digest != image.image.sha256:
            raise DiskError("written image failed readback verification")

        boot_identifier = _boot_partition(diskutil, target.identity.identifier)
        boot_info = diskutil.plist("info", boot_identifier)
        mount_point = boot_info.get("MountPoint")
        if mount_point is None:
            diskutil.run("mount", boot_identifier)
            boot_info = diskutil.plist("info", boot_identifier)
            mount_point = boot_info.get("MountPoint")
        if not isinstance(mount_point, str) or not mount_point:
            raise DiskError("the boot partition did not mount")
        mounted = _mounted_partitions(diskutil, target.identity.identifier)
        if mounted != {boot_identifier: mount_point}:
            raise DiskError("a partition other than bootfs is mounted")
        destination = Path(mount_point) / "e87canbus-provisioning-v1.zip"
        available = shutil.disk_usage(mount_point).free
        validate_provisioning_bundle(
            provisioning.path, image=image, available_boot_bytes=available
        )
        _copy_and_sync(provisioning.path, destination)
        if digest_file(destination, max_bytes=provisioning.size_bytes) != provisioning.sha256:
            raise DiskError("provisioning bundle failed readback verification")
    except DiskError:
        raise
    except Exception:
        raise DiskError("could not write the selected disk") from None
    finally:
        if wrote_image:
            try:
                diskutil.run("unmountDisk", target.identity.device_node)
            except Exception:
                raise DiskError("could not unmount the written disk") from None


def _eligible(identity: DiskIdentity, protected: set[str]) -> bool:
    return identity.identifier not in protected and not identity.internal


def _parse_selector(selector: str) -> str:
    value = selector.removeprefix("/dev/r").removeprefix("/dev/")
    if not (_DISK_IDENTIFIER.fullmatch(value) or _PARTITION_IDENTIFIER.fullmatch(value)):
        raise DiskError("disk must be an exact diskutil device identifier")
    return value


def _read_whole_disk(diskutil: Diskutil, identifier: str) -> DiskIdentity:
    info = diskutil.plist("info", identifier)
    if info.get("Whole") is not True or info.get("DeviceIdentifier") != identifier:
        raise DiskError("the selected target is not a whole disk")
    if info.get("VirtualOrPhysical") != "Physical":
        raise DiskError("the selected target is not a physical disk")
    internal = info.get("Internal")
    if not isinstance(internal, bool):
        raise DiskError("diskutil did not report whether the disk is internal")
    protocol = _required_string(info, "BusProtocol")
    device_node = _required_string(info, "DeviceNode")
    if device_node != f"/dev/{identifier}":
        raise DiskError("diskutil returned an unexpected device node")
    capacity = info.get("TotalSize")
    if not isinstance(capacity, int) or isinstance(capacity, bool) or capacity <= 0:
        raise DiskError("diskutil returned an invalid disk capacity")
    serial = info.get("SerialNumber")
    if serial is not None and not isinstance(serial, str):
        raise DiskError("diskutil returned an invalid disk serial")
    tree_path = info.get("DeviceTreePath") or info.get("IORegistryEntryPath")
    if tree_path is not None and not isinstance(tree_path, str):
        raise DiskError("diskutil returned an invalid device path")
    media_uuid = info.get("DiskUUID") or info.get("MediaUUID")
    if media_uuid is not None and not isinstance(media_uuid, str):
        raise DiskError("diskutil returned an invalid media UUID")
    mounts = tuple(sorted(set(_mounts(info)) | set(_disk_mounts(diskutil, identifier))))
    model = info.get("MediaName") or info.get("IORegistryEntryName")
    if not isinstance(model, str) or not model:
        raise DiskError("diskutil did not report the disk model")
    return DiskIdentity(
        identifier=identifier,
        device_node=device_node,
        raw_device_node=f"/dev/r{identifier}",
        model=model,
        capacity_bytes=capacity,
        serial=serial,
        protocol=protocol,
        internal=internal,
        mounts=mounts,
        device_tree_path=tree_path,
        media_uuid=media_uuid,
    )


def _system_physical_stores(diskutil: Diskutil) -> set[str]:
    root = diskutil.plist("info", "/")
    identifier = root.get("DeviceIdentifier")
    if not isinstance(identifier, str):
        raise DiskError("could not resolve the running system disk")
    apfs = diskutil.plist("apfs", "list")
    mappings = _apfs_physical_store_mappings(apfs)
    resolved = _resolve_stores(identifier, mappings)
    parent = root.get("ParentWholeDisk")
    if isinstance(parent, str):
        resolved |= _resolve_stores(parent, mappings)
    if not resolved:
        if isinstance(parent, str):
            resolved = {_whole_identifier(parent)}
        elif _DISK_IDENTIFIER.fullmatch(identifier):
            resolved = {identifier}
    if not resolved:
        raise DiskError("could not resolve the running system disk")
    return resolved


def _apfs_physical_store_mappings(document: dict[str, Any]) -> dict[str, set[str]]:
    mappings: dict[str, set[str]] = {}
    containers = document.get("Containers", [])
    if not isinstance(containers, list):
        raise DiskError("diskutil returned an invalid APFS property list")
    for container in containers:
        if not isinstance(container, dict):
            continue
        reference = container.get("ContainerReference")
        stores = {
            value
            for item in container.get("PhysicalStores", [])
            if isinstance(item, dict)
            if isinstance((value := item.get("DeviceIdentifier")), str)
        }
        if isinstance(reference, str) and stores:
            mappings[reference] = stores
        for volume in container.get("Volumes", []):
            if isinstance(volume, dict) and isinstance(
                volume_identifier := volume.get("DeviceIdentifier"), str
            ):
                mappings[volume_identifier] = stores
    return mappings


def _resolve_stores(identifier: str, mappings: dict[str, set[str]]) -> set[str]:
    stores = mappings.get(identifier, set())
    return {_whole_identifier(store) for store in stores}


def _whole_identifier(identifier: str) -> str:
    match = re.match(r"^(disk[0-9]+)", identifier)
    if match is None:
        raise DiskError("diskutil returned an invalid physical store")
    return match.group(1)


def _whole_disk_identifiers(document: dict[str, Any]) -> set[str]:
    disks = document.get("AllDisksAndPartitions")
    if not isinstance(disks, list):
        raise DiskError("diskutil returned an invalid disk list")
    return {
        identifier
        for disk in disks
        if isinstance(disk, dict)
        if isinstance((identifier := disk.get("DeviceIdentifier")), str)
        if _DISK_IDENTIFIER.fullmatch(identifier)
    }


def _mounts(info: dict[str, Any]) -> Iterable[str]:
    mount = info.get("MountPoint")
    if isinstance(mount, str) and mount:
        yield mount
    volumes = info.get("MountPoints")
    if isinstance(volumes, list):
        yield from (item for item in volumes if isinstance(item, str) and item)


def _disk_mounts(diskutil: Diskutil, identifier: str) -> Iterable[str]:
    yield from _mounted_partitions(diskutil, identifier).values()


def _mounted_partitions(diskutil: Diskutil, identifier: str) -> dict[str, str]:
    document = diskutil.plist("list", identifier)
    roots = document.get("AllDisksAndPartitions")
    if not isinstance(roots, list):
        raise DiskError("diskutil returned an invalid partition list")
    mounted: dict[str, str] = {}
    for root in roots:
        if not isinstance(root, dict) or root.get("DeviceIdentifier") != identifier:
            continue
        partitions = root.get("Partitions", [])
        if not isinstance(partitions, list):
            raise DiskError("diskutil returned an invalid partition list")
        for partition in partitions:
            if not isinstance(partition, dict):
                continue
            partition_identifier = partition.get("DeviceIdentifier")
            mount_point = partition.get("MountPoint")
            if isinstance(partition_identifier, str) and isinstance(mount_point, str):
                mounted[partition_identifier] = mount_point
    return mounted


def _boot_partition(diskutil: Diskutil, identifier: str) -> str:
    document = diskutil.plist("list", identifier)
    roots = document.get("AllDisksAndPartitions")
    if not isinstance(roots, list) or len(roots) != 1 or not isinstance(roots[0], dict):
        raise DiskError("could not inspect written partitions")
    partitions = roots[0].get("Partitions")
    if not isinstance(partitions, list):
        raise DiskError("written disk has no partition list")
    boot = [
        item.get("DeviceIdentifier")
        for item in partitions
        if isinstance(item, dict) and item.get("VolumeName") == "bootfs"
    ]
    if len(boot) != 1 or not isinstance(boot[0], str):
        raise DiskError("written disk does not have exactly one bootfs partition")
    return boot[0]


def _run_privileged(command: list[str]) -> None:
    subprocess.run(["sudo", *command], check=True)


def _readback_digest(raw_device: str, size_bytes: int) -> str:
    process = subprocess.Popen(
        ["sudo", "dd", f"if={raw_device}", "bs=1m", f"count={(size_bytes + 1048575) // 1048576}"],
        stdout=subprocess.PIPE,
    )
    if process.stdout is None:
        raise DiskError("could not read the written image")
    digest = hashlib.sha256()
    remaining = size_bytes
    while remaining:
        chunk = process.stdout.read(min(_COPY_CHUNK_BYTES, remaining))
        if not chunk:
            process.kill()
            raise DiskError("written image readback was incomplete")
        digest.update(chunk)
        remaining -= len(chunk)
    process.stdout.read()
    if process.wait() != 0:
        raise DiskError("could not read the written image")
    return digest.hexdigest()


def _copy_and_sync(source: Path, destination: Path) -> None:
    temporary = destination.with_name(f".{destination.name}.tmp")
    try:
        with source.open("rb") as input_file, temporary.open("xb") as output_file:
            shutil.copyfileobj(input_file, output_file, length=_COPY_CHUNK_BYTES)
            output_file.flush()
            os.fsync(output_file.fileno())
        os.replace(temporary, destination)
        os.sync()
    finally:
        temporary.unlink(missing_ok=True)


def _required_string(document: dict[str, Any], name: str) -> str:
    value = document.get(name)
    if not isinstance(value, str) or not value:
        raise DiskError(f"diskutil did not report {name}")
    return value
