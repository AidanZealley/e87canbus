from __future__ import annotations

import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Literal, TypeVar, cast

from pydantic import BaseModel, ConfigDict

from e87ctl.application import build_application
from e87ctl.artifacts import Role, load_image_manifest
from e87ctl.macos import (
    DiskError,
    DiskIdentity,
    Diskutil,
    SystemDiskutil,
    discover_eligible_disks,
    inspect_target,
    recheck_target,
    write_card,
)
from e87ctl.provisioning import (
    DeploymentProfile,
    build_provisioning_bundle,
)
from e87ctl.recovery import load_recovery_package

_Choice = TypeVar("_Choice")


class ProvisionCommandError(Exception):
    """A safe-to-display complete provisioning error."""


class ProvisionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    format_version: Literal[1] = 1
    result: Literal["card_prepared"] = "card_prepared"
    first_boot: Literal["pending"] = "pending"
    role: Role
    installation_id: str
    device_id: str
    hostname: str
    target_device: str
    target_model: str
    target_capacity_bytes: int
    target_serial: str | None
    target_protocol: str
    target_mounts: tuple[str, ...]
    image_digest: str
    application_digest: str
    provisioning_digest: str


def compatible_image_manifests(repository: Path, role: Role) -> list[Path]:
    directory = repository / "artifacts" / "images" / role
    compatible: list[Path] = []
    for path in sorted(directory.glob("*.json")):
        try:
            load_image_manifest(path, expected_role=role)
        except Exception:
            continue
        compatible.append(path)
    return compatible


def provision_card(
    role: Role,
    *,
    installation_path: Path,
    image_manifest_path: Path,
    expected_target: DiskIdentity,
    deployment_profile: DeploymentProfile,
    confirmation: str,
    hostname: str | None = None,
    repository: Path | None = None,
    diskutil: Diskutil | None = None,
) -> ProvisionResult:
    repository = repository or Path(__file__).resolve().parents[3]
    diskutil = diskutil or SystemDiskutil()
    try:
        recovery = load_recovery_package(installation_path)
        image = load_image_manifest(image_manifest_path, expected_role=role)
        image_path = image_manifest_path.with_name(image.image.filename)
        if expected_target.capacity_bytes < image.image.size_bytes:
            raise ProvisionCommandError("selected disk is too small for the image")
        if confirmation != confirmation_value(expected_target):
            raise ProvisionCommandError("disk confirmation did not match the resolved device")

        application = build_application(role, repository=repository)
        with tempfile.TemporaryDirectory(prefix="e87-provisioning-") as temporary:
            provisioning = build_provisioning_bundle(
                role,
                recovery=recovery,
                image=image,
                application=application,
                output=Path(temporary) / "e87canbus-provisioning-v1.zip",
                deployment_profile=deployment_profile,
                hostname=hostname,
            )
            target = recheck_target(diskutil, expected_target)
            write_card(
                diskutil,
                target,
                image_path=image_path,
                image=image,
                provisioning=provisioning,
            )

        return ProvisionResult(
            role=role,
            installation_id=recovery.installation_id,
            device_id=provisioning.configuration.device_id,
            hostname=provisioning.configuration.hostname,
            target_device=target.identity.device_node,
            target_model=target.identity.model,
            target_capacity_bytes=target.identity.capacity_bytes,
            target_serial=target.identity.serial,
            target_protocol=target.identity.protocol,
            target_mounts=target.identity.mounts,
            image_digest=image.image.sha256,
            application_digest=application.sha256,
            provisioning_digest=provisioning.sha256,
        )
    except ProvisionCommandError:
        raise
    except DiskError as error:
        raise ProvisionCommandError(str(error)) from None
    except Exception:
        raise ProvisionCommandError("could not provision the selected disk") from None


def describe_disk(identity: DiskIdentity) -> str:
    serial = identity.serial or "not reported"
    mounts = ", ".join(identity.mounts) or "none"
    return (
        f"{identity.device_node}: {identity.model}, {identity.capacity_bytes} bytes, "
        f"serial {serial}, {identity.protocol}, mounts {mounts}"
    )


def confirmation_value(identity: DiskIdentity) -> str:
    return f"{identity.identifier} {identity.model} {identity.capacity_bytes}"


def choose_image(repository: Path, role: Role, selection: str | None) -> Path:
    if selection is not None:
        return Path(selection)
    choices = compatible_image_manifests(repository, role)
    if not choices:
        raise ProvisionCommandError("no compatible local image was found")
    return _choose("image", choices, lambda path: str(path))


def choose_disk(diskutil: Diskutil, selection: str | None) -> DiskIdentity:
    try:
        if selection is not None:
            return inspect_target(diskutil, selection)
        choices = discover_eligible_disks(diskutil)
        if not choices:
            raise ProvisionCommandError("no eligible external disk was found")
        return _choose("disk", choices, describe_disk)
    except DiskError as error:
        raise ProvisionCommandError(str(error)) from None


def choose_profile(selection: str | None) -> DeploymentProfile:
    if selection in {"car", "bench"}:
        return cast(DeploymentProfile, selection)
    if selection is not None:
        raise ProvisionCommandError("deployment profile must be car or bench")
    return cast(
        DeploymentProfile,
        _choose("deployment profile", ["car", "bench"], str),
    )


def _choose(
    name: str, choices: Sequence[_Choice], describe: Callable[[_Choice], str]
) -> _Choice:
    print(f"Available {name}s:")
    for index, item in enumerate(choices, start=1):
        print(f"  {index}. {describe(item)}")
    try:
        selected = int(input(f"Select {name}: "))
    except (EOFError, ValueError):
        raise ProvisionCommandError(f"invalid {name} selection") from None
    if selected < 1 or selected > len(choices):
        raise ProvisionCommandError(f"invalid {name} selection")
    return choices[selected - 1]
