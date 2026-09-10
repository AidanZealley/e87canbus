from __future__ import annotations

import hashlib
import json
import re
import tarfile
import zipfile
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal, Protocol, TypeAlias, TypeVar

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

Role: TypeAlias = Literal["coordinator", "console"]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]

PROVISIONING_INTERFACE_VERSION: Literal[1] = 1
APPLICATION_FORMAT_VERSION: Literal[1] = 1
PROVISIONING_FORMAT_VERSION: Literal[1] = 1
BOOT_FREE_RESERVE_BYTES = 64 * 1024 * 1024
ROOT_FREE_RESERVE_BYTES = 256 * 1024 * 1024
MAX_APPLICATION_ARCHIVE_BYTES = 1024 * 1024 * 1024
MAX_APPLICATION_CONTENT_BYTES = 2 * 1024 * 1024 * 1024
MAX_PROVISIONING_ARCHIVE_BYTES = MAX_APPLICATION_ARCHIVE_BYTES + 16 * 1024 * 1024

_GIT_COMMIT = re.compile(r"[0-9a-f]{40}")
_APPLICATION_PATH = re.compile(r"(?:venv|frontend)/[^\x00]+")
_Model = TypeVar("_Model", bound=BaseModel)
_PROVISIONING_ENTRY_LIMITS = {
    "application.tar.gz": MAX_APPLICATION_ARCHIVE_BYTES,
    "identity/installation-ca.pem": 16 * 1024,
    "identity/ssh-authorized-key": 4 * 1024,
    "network/wifi.nmconnection": 64 * 1024,
    "configuration/device.json": 32 * 1024,
    "configuration/operator-password.hash": 4 * 1024,
    "identity/server-certificate.pem": 16 * 1024,
    "identity/server-private-key.pem": 16 * 1024,
    "identity/chromium-client.p12": 64 * 1024,
    "identity/chromium-client-password": 1024,
}


class _Readable(Protocol):
    def read(self, size: int = -1) -> bytes: ...


class ArtifactError(Exception):
    """A safe-to-display artifact validation error."""


class FileRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    size_bytes: Annotated[int, Field(ge=0)]
    sha256: Sha256


class ImageFile(FileRecord):
    filename: str

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        if PurePosixPath(value).name != value or not value.endswith(".img"):
            raise ValueError("invalid image filename")
        return value


class ImageManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    format_version: Literal[1]
    role: Role
    raspberry_pi_model: Literal["Raspberry Pi 4 Model B"]
    os_release: Literal["Raspberry Pi OS Lite Trixie"]
    architecture: Literal["arm64"]
    builder_revision: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{40}$")]
    built_at: AwareDatetime
    git_commit: str | None
    git_dirty: bool
    provisioning_interface_version: Literal[1]
    boot_partition_size_bytes: Annotated[int, Field(gt=BOOT_FREE_RESERVE_BYTES)]
    root_filesystem_size_bytes: Annotated[int, Field(gt=ROOT_FREE_RESERVE_BYTES)]
    image: ImageFile

    @field_validator("built_at")
    @classmethod
    def validate_built_at(cls, value: datetime) -> datetime:
        return _second_precision_utc(value)

    @field_validator("git_commit")
    @classmethod
    def validate_git_commit(cls, value: str | None) -> str | None:
        if value is not None and _GIT_COMMIT.fullmatch(value) is None:
            raise ValueError("invalid Git commit")
        return value


class ApplicationManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    format_version: Literal[1]
    role: Role
    architecture: Literal["linux-aarch64"]
    python_version: Literal["3.13"]
    provisioning_interface_version: Literal[1]
    built_at: AwareDatetime
    git_commit: str | None
    git_dirty: bool
    builder_image: str
    builder_revision: Sha256
    python_lock_sha256: Sha256
    frontend_lock_sha256: Sha256
    files: dict[str, FileRecord]

    @field_validator("built_at")
    @classmethod
    def validate_built_at(cls, value: datetime) -> datetime:
        return _second_precision_utc(value)

    @field_validator("git_commit")
    @classmethod
    def validate_git_commit(cls, value: str | None) -> str | None:
        if value is not None and _GIT_COMMIT.fullmatch(value) is None:
            raise ValueError("invalid Git commit")
        return value

    @field_validator("builder_image")
    @classmethod
    def validate_builder_image(cls, value: str) -> str:
        if "@sha256:" not in value or not value.startswith("debian:trixie-slim"):
            raise ValueError("application builder image must be pinned by digest")
        return value

    @field_validator("files")
    @classmethod
    def validate_files(cls, value: dict[str, FileRecord]) -> dict[str, FileRecord]:
        total_size = sum(item.size_bytes for item in value.values())
        if not value or total_size > MAX_APPLICATION_CONTENT_BYTES:
            raise ValueError("invalid application content size")
        for name in value:
            _validate_archive_path(name)
            if _APPLICATION_PATH.fullmatch(name) is None:
                raise ValueError("application contains a file outside venv or frontend")
        if not any(name.startswith("venv/") for name in value):
            raise ValueError("application virtual environment is missing")
        if not any(name.startswith("frontend/") for name in value):
            raise ValueError("application frontend is missing")
        return value


class ProvisioningManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    format_version: Literal[1]
    created_at: AwareDatetime
    role: Role
    image_format_version: Literal[1]
    application_format_version: Literal[1]
    provisioning_interface_version: Literal[1]
    installation_id: Annotated[str, StringConstraints(pattern=r"^[a-z2-7]{52}$")]
    device_id: Annotated[
        str,
        StringConstraints(
            pattern=(
                r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-"
                r"[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
            )
        ),
    ]
    hostname: Annotated[
        str,
        StringConstraints(
            min_length=1,
            max_length=63,
            pattern=r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$",
        ),
    ]
    application_digest: Sha256
    entries: dict[str, FileRecord]

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        return _second_precision_utc(value)

    @model_validator(mode="after")
    def validate_role_contract(self) -> ProvisioningManifest:
        expected = provisioning_entry_names(self.role) - {"manifest.json"}
        if set(self.entries) != expected:
            raise ValueError("provisioning entries do not match role schema")
        if any(
            record.size_bytes > _PROVISIONING_ENTRY_LIMITS[name]
            for name, record in self.entries.items()
        ):
            raise ValueError("provisioning entry exceeds its fixed limit")
        if self.entries["application.tar.gz"].sha256 != self.application_digest:
            raise ValueError("application digest does not match its entry")
        return self


def provisioning_entry_names(role: Role) -> set[str]:
    common = {
        "manifest.json",
        "application.tar.gz",
        "identity/installation-ca.pem",
        "identity/ssh-authorized-key",
        "network/wifi.nmconnection",
        "configuration/device.json",
    }
    if role == "coordinator":
        return common | {
            "configuration/operator-password.hash",
            "identity/server-certificate.pem",
            "identity/server-private-key.pem",
        }
    return common | {
        "identity/chromium-client.p12",
        "identity/chromium-client-password",
    }


def load_image_manifest(path: Path, *, expected_role: Role | None = None) -> ImageManifest:
    try:
        manifest = _model_from_json_file(path, ImageManifest, max_bytes=32 * 1024)
        if expected_role is not None and manifest.role != expected_role:
            raise ValueError("image role does not match")
        image_path = path.with_name(manifest.image.filename)
        _validate_file(image_path, manifest.image, max_bytes=manifest.image.size_bytes)
        return manifest
    except Exception:
        raise ArtifactError("invalid image artifact") from None


def validate_application_archive(
    path: Path, *, expected_role: Role | None = None
) -> ApplicationManifest:
    try:
        if path.stat().st_size > MAX_APPLICATION_ARCHIVE_BYTES:
            raise ValueError("application archive is oversized")
        with tarfile.open(path, mode="r|gz") as archive:
            first = archive.next()
            if first is None or first.name != "manifest.json" or not first.isfile():
                raise ValueError("application manifest must be the first regular entry")
            if first.size > 1024 * 1024:
                raise ValueError("application manifest is oversized")
            manifest_stream = archive.extractfile(first)
            if manifest_stream is None:
                raise ValueError("application manifest is unreadable")
            manifest = _model_from_json_bytes(
                _read_exact(manifest_stream, first.size), ApplicationManifest
            )
            if expected_role is not None and manifest.role != expected_role:
                raise ValueError("application role does not match")
            seen: set[str] = set()
            while (member := archive.next()) is not None:
                _validate_archive_path(member.name)
                if (
                    not member.isfile()
                    or member.mode & 0o7000
                    or member.name in seen
                    or member.name not in manifest.files
                ):
                    raise ValueError("invalid application archive entry")
                record = manifest.files[member.name]
                if member.size != record.size_bytes:
                    raise ValueError("application entry size does not match")
                stream = archive.extractfile(member)
                if stream is None or _digest_stream(stream, record.size_bytes) != record.sha256:
                    raise ValueError("application entry digest does not match")
                seen.add(member.name)
            if seen != set(manifest.files):
                raise ValueError("application archive is incomplete")
            return manifest
    except Exception:
        raise ArtifactError("invalid application artifact") from None


def validate_provisioning_archive(
    path: Path,
    *,
    image: ImageManifest,
    available_boot_bytes: int | None = None,
    available_root_bytes: int | None = None,
) -> ProvisioningManifest:
    try:
        archive_size = path.stat().st_size
        boot_bytes = (
            image.boot_partition_size_bytes
            if available_boot_bytes is None
            else available_boot_bytes
        )
        root_bytes = (
            image.root_filesystem_size_bytes
            if available_root_bytes is None
            else available_root_bytes
        )
        if (
            archive_size > MAX_PROVISIONING_ARCHIVE_BYTES
            or archive_size + BOOT_FREE_RESERVE_BYTES > boot_bytes
        ):
            raise ValueError("provisioning bundle does not fit the boot partition")
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)) or not names or names[0] != "manifest.json":
                raise ValueError("invalid provisioning entry order")
            for info in infos:
                _validate_zip_entry(info)
            manifest_info = infos[0]
            if manifest_info.file_size > 1024 * 1024:
                raise ValueError("provisioning manifest is oversized")
            with archive.open(manifest_info) as stream:
                manifest = _model_from_json_bytes(
                    _read_exact(stream, manifest_info.file_size), ProvisioningManifest
                )
            if manifest.role != image.role:
                raise ValueError("provisioning role does not match image")
            if manifest.image_format_version != image.format_version or (
                manifest.provisioning_interface_version != image.provisioning_interface_version
            ):
                raise ValueError("provisioning contract does not match image")
            if set(names) != provisioning_entry_names(manifest.role):
                raise ValueError("provisioning entries do not match role schema")
            for info in infos[1:]:
                record = manifest.entries[info.filename]
                if info.file_size != record.size_bytes:
                    raise ValueError("provisioning entry size does not match")
                with archive.open(info) as stream:
                    if _digest_stream(stream, record.size_bytes) != record.sha256:
                        raise ValueError("provisioning entry digest does not match")
            root_content = sum(record.size_bytes for record in manifest.entries.values())
            if root_content + ROOT_FREE_RESERVE_BYTES > root_bytes:
                raise ValueError("provisioning content does not fit the root filesystem")
            return manifest
    except Exception:
        raise ArtifactError("invalid provisioning artifact") from None


def file_record(contents: bytes) -> FileRecord:
    return FileRecord(size_bytes=len(contents), sha256=hashlib.sha256(contents).hexdigest())


def canonical_json(model: BaseModel) -> bytes:
    document = json.dumps(model.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return (document + "\n").encode()


def parse_json_model(contents: bytes, model: type[_Model]) -> _Model:
    json.loads(contents, object_pairs_hook=_reject_duplicate_fields)
    return model.model_validate_json(contents)


def digest_file(path: Path, *, max_bytes: int) -> str:
    with path.open("rb") as stream:
        return _digest_stream(stream, path.stat().st_size, max_bytes=max_bytes)


def _validate_file(path: Path, expected: FileRecord, *, max_bytes: int) -> None:
    if (
        path.stat().st_size != expected.size_bytes
        or digest_file(path, max_bytes=max_bytes) != expected.sha256
    ):
        raise ValueError("file does not match manifest")


def _digest_stream(stream: _Readable, declared_size: int, *, max_bytes: int | None = None) -> str:
    if declared_size < 0 or declared_size > (max_bytes if max_bytes is not None else declared_size):
        raise ValueError("declared size exceeds limit")
    digest = hashlib.sha256()
    remaining = declared_size
    while remaining:
        chunk = stream.read(min(1024 * 1024, remaining))
        if not chunk:
            raise ValueError("entry ended before its declared size")
        digest.update(chunk)
        remaining -= len(chunk)
    if stream.read(1):
        raise ValueError("entry exceeds its declared size")
    return digest.hexdigest()


def _read_exact(stream: _Readable, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = stream.read(min(64 * 1024, remaining))
        if not chunk:
            raise ValueError("entry ended before its declared size")
        chunks.append(chunk)
        remaining -= len(chunk)
    if stream.read(1):
        raise ValueError("entry exceeds its declared size")
    return b"".join(chunks)


def _model_from_json_file(path: Path, model: type[_Model], *, max_bytes: int) -> _Model:
    size = path.stat().st_size
    if size > max_bytes:
        raise ValueError("JSON document is oversized")
    return _model_from_json_bytes(path.read_bytes(), model)


def _model_from_json_bytes(contents: bytes, model: type[_Model]) -> _Model:
    return parse_json_model(contents, model)


def _reject_duplicate_fields(pairs: Iterable[tuple[str, object]]) -> dict[str, object]:
    document: dict[str, object] = {}
    for key, value in pairs:
        if key in document:
            raise ValueError("duplicate JSON field")
        document[key] = value
    return document


def _validate_archive_path(name: str) -> None:
    path = PurePosixPath(name)
    if not name or name.startswith("/") or "\\" in name or ".." in path.parts or str(path) != name:
        raise ValueError("unsafe archive path")


def _validate_zip_entry(info: zipfile.ZipInfo) -> None:
    _validate_archive_path(info.filename)
    mode = info.external_attr >> 16
    file_type = mode & 0o170000
    if info.is_dir() or file_type not in (0, 0o100000):
        raise ValueError("provisioning entries must be regular files")
    if info.flag_bits & 0x1:
        raise ValueError("encrypted provisioning entries are unsupported")


def _second_precision_utc(value: datetime) -> datetime:
    if value.utcoffset() != timedelta(0) or value.microsecond != 0:
        raise ValueError("timestamp must use second-precision UTC")
    return value.astimezone(UTC)
