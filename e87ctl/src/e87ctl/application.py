from __future__ import annotations

import gzip
import hashlib
import io
import os
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from e87ctl.artifacts import (
    APPLICATION_FORMAT_VERSION,
    MAX_APPLICATION_ARCHIVE_BYTES,
    MAX_APPLICATION_CONTENT_BYTES,
    PROVISIONING_INTERFACE_VERSION,
    ApplicationManifest,
    FileRecord,
    Role,
    canonical_json,
    digest_file,
    validate_application_archive,
)

APPLICATION_BUILDER_BASE = (
    "debian:trixie-slim@sha256:"
    "c94f5ddd41327aa2d4a7cfba7889056c02936182fd76a513fec6160c97181fc0"
)


class ApplicationBuildError(Exception):
    """A safe-to-display application build error."""


@dataclass(frozen=True, slots=True)
class ApplicationArtifact:
    path: Path
    manifest: ApplicationManifest
    size_bytes: int
    sha256: str


def build_application(role: Role, *, repository: Path | None = None) -> ApplicationArtifact:
    repository = repository or Path(__file__).resolve().parents[3]
    output = repository / "artifacts" / "applications" / role / "application-v1.tar.gz"
    built_at = datetime.now(UTC).replace(microsecond=0)
    git_commit, git_dirty = _git_context(repository)
    builder = repository / "e87ctl" / "application-builder"

    try:
        with tempfile.TemporaryDirectory(prefix="e87-application-") as temporary:
            payload = Path(temporary) / "payload"
            payload.mkdir()
            locked = Path(temporary) / "locked"
            locked.mkdir()
            _export_locked_requirements(repository, locked)
            builder_revision = _builder_revision(builder)
            image_tag = f"e87canbus/application-builder:{builder_revision[:12]}"
            _run(["docker", "build", "--platform", "linux/arm64", "--tag", image_tag, str(builder)])
            architecture = _run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--platform",
                    "linux/arm64",
                    "--entrypoint",
                    "uname",
                    image_tag,
                    "-m",
                ],
                capture=True,
            ).strip()
            if architecture not in {"arm64", "aarch64"}:
                raise ApplicationBuildError("application builder is not running as ARM64")
            _run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--platform",
                    "linux/arm64",
                    "--mount",
                    f"type=bind,src={repository},dst=/source,readonly",
                    "--mount",
                    f"type=bind,src={payload},dst=/output",
                    "--mount",
                    f"type=bind,src={locked},dst=/locked,readonly",
                    image_tag,
                    role,
                ]
            )
            manifest = package_application(
                payload,
                output,
                role=role,
                built_at=built_at,
                git_commit=git_commit,
                git_dirty=git_dirty,
                builder_revision=builder_revision,
                python_lock_sha256=_input_digest(repository / "uv.lock"),
                frontend_lock_sha256=_input_digest(repository / "frontend/pnpm-lock.yaml"),
            )
        validate_application_archive(output, expected_role=role)
        return ApplicationArtifact(
            path=output,
            manifest=manifest,
            size_bytes=output.stat().st_size,
            sha256=digest_file(output, max_bytes=MAX_APPLICATION_ARCHIVE_BYTES),
        )
    except ApplicationBuildError:
        raise
    except Exception:
        raise ApplicationBuildError("could not build application artifact") from None


def package_application(
    payload: Path,
    output: Path,
    *,
    role: Role,
    built_at: datetime,
    git_commit: str | None,
    git_dirty: bool,
    builder_revision: str | None = None,
    python_lock_sha256: str | None = None,
    frontend_lock_sha256: str | None = None,
) -> ApplicationManifest:
    repository = Path(__file__).resolve().parents[3]
    records: dict[str, FileRecord] = {}
    files: list[tuple[str, Path]] = []
    total_size = 0
    for root_name in ("venv", "frontend"):
        root = payload / root_name
        if not root.is_dir():
            raise ApplicationBuildError(f"application {root_name} output is missing")
        for path in sorted(root.rglob("*")):
            if path.is_symlink() or not path.is_file():
                if path.is_dir():
                    continue
                raise ApplicationBuildError("application output contains a non-regular file")
            name = path.relative_to(payload).as_posix()
            size = path.stat().st_size
            total_size += size
            if total_size > MAX_APPLICATION_CONTENT_BYTES:
                raise ApplicationBuildError("application output is oversized")
            records[name] = FileRecord(
                size_bytes=size,
                sha256=digest_file(path, max_bytes=size),
            )
            files.append((name, path))
    manifest = ApplicationManifest(
        format_version=APPLICATION_FORMAT_VERSION,
        role=role,
        architecture="linux-aarch64",
        python_version="3.13",
        provisioning_interface_version=PROVISIONING_INTERFACE_VERSION,
        built_at=built_at,
        git_commit=git_commit,
        git_dirty=git_dirty,
        builder_image=APPLICATION_BUILDER_BASE,
        builder_revision=builder_revision
        or _builder_revision(Path(__file__).resolve().parents[2] / "application-builder"),
        python_lock_sha256=python_lock_sha256 or _input_digest(repository / "uv.lock"),
        frontend_lock_sha256=frontend_lock_sha256
        or _input_digest(repository / "frontend/pnpm-lock.yaml"),
        files=records,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".application-", dir=output.parent)
    try:
        with (
            os.fdopen(descriptor, "wb") as raw_output,
            gzip.GzipFile(filename="", mode="wb", fileobj=raw_output, mtime=0) as compressed,
            tarfile.open(fileobj=compressed, mode="w|") as archive,
        ):
            _add_bytes(archive, "manifest.json", canonical_json(manifest), 0o644)
            for name, path in files:
                _add_file(archive, name, path)
            raw_output.flush()
            os.fsync(raw_output.fileno())
        os.replace(temporary_name, output)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise
    return manifest


def _add_bytes(archive: tarfile.TarFile, name: str, contents: bytes, mode: int) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(contents)
    info.mode = mode
    info.mtime = 0
    info.uid = info.gid = 0
    info.uname = info.gname = "root"
    archive.addfile(info, io.BytesIO(contents))


def _add_file(archive: tarfile.TarFile, name: str, path: Path) -> None:
    info = tarfile.TarInfo(name)
    info.size = path.stat().st_size
    info.mode = path.stat().st_mode & 0o777
    info.mtime = 0
    info.uid = info.gid = 0
    info.uname = info.gname = "root"
    with path.open("rb") as contents:
        archive.addfile(info, contents)


def _builder_revision(builder: Path) -> str:
    digest = hashlib.sha256()
    found_input = False
    for path in sorted(builder.rglob("*")):
        if path.is_file():
            found_input = True
            digest.update(path.relative_to(builder).as_posix().encode())
            digest.update(path.read_bytes())
    if not found_input:
        raise ApplicationBuildError("application builder inputs are missing")
    return digest.hexdigest()


def _input_digest(path: Path) -> str:
    try:
        return digest_file(path, max_bytes=path.stat().st_size)
    except OSError:
        raise ApplicationBuildError(f"application builder input {path.name} is missing") from None


def _git_context(repository: Path) -> tuple[str | None, bool]:
    commit = subprocess.run(
        ["git", "-C", repository, "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    status = subprocess.run(
        ["git", "-C", repository, "status", "--porcelain", "--untracked-files=normal"],
        text=True,
        capture_output=True,
        check=False,
    )
    return (commit.stdout.strip() if commit.returncode == 0 else None, bool(status.stdout.strip()))


def _export_locked_requirements(repository: Path, output: Path) -> None:
    common = [
        "uv",
        "export",
        "--locked",
        "--no-emit-project",
        "--format",
        "requirements-txt",
    ]
    _run(
        [*common, "--no-dev", "--output-file", output / "runtime.txt"],
        cwd=repository,
    )
    _run(
        [
            *common,
            "--only-group",
            "application-build",
            "--output-file",
            output / "build.txt",
        ],
        cwd=repository,
    )


def _run(
    arguments: list[str | Path], *, capture: bool = False, cwd: Path | None = None
) -> str:
    try:
        result = subprocess.run(
            [str(argument) for argument in arguments],
            text=True,
            capture_output=capture,
            check=False,
            cwd=cwd,
        )
    except OSError:
        raise ApplicationBuildError("Docker is required to build applications") from None
    if result.returncode != 0:
        raise ApplicationBuildError("application builder failed")
    return result.stdout if capture else ""
