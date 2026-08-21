from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BUILD_SCRIPT = ROOT / "scripts/build-pi-image"
BUILDER = ROOT / "images/builder"
COMMON_CONFIG = ROOT / "images/common/image.yaml"
COMMON_LAYER = ROOT / "images/layer/e87-common.yaml"
COMMON_OVERLAY = ROOT / "images/layer/e87-common.rootfs-overlay"


def read(path: Path) -> str:
    return path.read_text()


def write_executable(path: Path, contents: str) -> None:
    path.write_text(contents)
    path.chmod(0o755)


def make_test_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    shutil.copytree(BUILDER, repo / "images/builder")
    (repo / "scripts").mkdir()
    shutil.copy2(BUILD_SCRIPT, repo / "scripts/build-pi-image")
    return repo


def arm64_tools(tmp_path: Path, docker: str) -> Path:
    tools = tmp_path / "tools"
    tools.mkdir()
    write_executable(tools / "uname", "#!/bin/sh\necho arm64\n")
    write_executable(tools / "docker", docker)
    return tools


def successful_docker(*, container_architecture: str = "aarch64") -> str:
    return f"""#!/bin/sh
case "$1" in
    info | build) exit 0 ;;
    run)
        case " $* " in
            *" --entrypoint uname "*) echo {container_architecture}; exit 0 ;;
        esac
        for argument in "$@"; do
            case "$argument" in
                type=bind,src=*,dst=/output)
                    output=${{argument#type=bind,src=}}
                    output=${{output%,dst=/output}}
                    printf 'fake image bytes' >"$output/e87-coordinator.img"
                    exit 0
                    ;;
            esac
        done
        exit 1
        ;;
esac
"""


@pytest.mark.parametrize("arguments", [[], ["base"], ["coordinator", "extra"]])
def test_build_rejects_everything_except_one_public_role(arguments: list[str]) -> None:
    result = subprocess.run(
        ["bash", str(BUILD_SCRIPT), *arguments],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "coordinator|console" in result.stderr


def test_build_reports_missing_docker() -> None:
    result = subprocess.run(
        ["/bin/bash", str(BUILD_SCRIPT), "coordinator"],
        env={"PATH": ""},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "Docker is required" in result.stderr


def test_build_rejects_non_arm64_host(tmp_path: Path) -> None:
    write_executable(tmp_path / "docker", "#!/bin/sh\nexit 0\n")
    write_executable(tmp_path / "uname", "#!/bin/sh\necho x86_64\n")

    result = subprocess.run(
        ["bash", str(BUILD_SCRIPT), "coordinator"],
        env={"PATH": f"{tmp_path}:{os.environ['PATH']}"},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "Host architecture: x86_64" in result.stdout
    assert "native arm64 is required" in result.stderr
    assert "x86 emulation is not supported" in result.stderr


def test_build_reports_unavailable_docker_daemon(tmp_path: Path) -> None:
    write_executable(tmp_path / "docker", "#!/bin/sh\nexit 1\n")

    result = subprocess.run(
        ["bash", str(BUILD_SCRIPT), "coordinator"],
        env={"PATH": f"{tmp_path}:{os.environ['PATH']}"},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "Docker daemon is unavailable" in result.stderr


def test_build_rejects_non_arm64_container(tmp_path: Path) -> None:
    repo = make_test_repo(tmp_path)
    tools = arm64_tools(tmp_path, successful_docker(container_architecture="x86_64"))

    result = subprocess.run(
        ["bash", str(repo / "scripts/build-pi-image"), "coordinator"],
        env={"PATH": f"{tools}:{os.environ['PATH']}"},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "Container architecture: x86_64" in result.stdout
    assert "container architecture is x86_64" in result.stderr
    assert "native arm64 is required" in result.stderr


def test_build_rejects_role_without_an_image_definition(tmp_path: Path) -> None:
    repo = make_test_repo(tmp_path)

    result = subprocess.run(
        ["bash", str(repo / "scripts/build-pi-image"), "console"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "image definition images/console/image.yaml does not exist" in result.stderr
    assert not (repo / "artifacts").exists()


def test_successful_build_places_image_and_verified_manifest(tmp_path: Path) -> None:
    repo = make_test_repo(tmp_path)
    tools = arm64_tools(tmp_path, successful_docker())

    result = subprocess.run(
        ["bash", str(repo / "scripts/build-pi-image"), "coordinator"],
        env={"PATH": f"{tools}:{os.environ['PATH']}"},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    artifact_dir = repo / "artifacts/images/coordinator"
    images = list(artifact_dir.glob("*.img"))
    manifests = list(artifact_dir.glob("*.json"))
    assert len(images) == len(manifests) == 1
    manifest = json.loads(manifests[0].read_text())
    assert manifest == {
        "format_version": 1,
        "role": "coordinator",
        "raspberry_pi_model": "Raspberry Pi 4 Model B",
        "os_release": "Raspberry Pi OS Lite Trixie",
        "architecture": "arm64",
        "builder_revision": "262d4df5a9f9d4133370465399a7958a7c22cdc7",
        "built_at": manifest["built_at"],
        "git_commit": None,
        "git_dirty": False,
        "image": {
            "filename": images[0].name,
            "size_bytes": images[0].stat().st_size,
            "sha256": hashlib.sha256(images[0].read_bytes()).hexdigest(),
        },
    }


def test_build_uses_linux_volumes_for_temporary_state_and_package_cache(tmp_path: Path) -> None:
    repo = make_test_repo(tmp_path)
    tools = arm64_tools(tmp_path, successful_docker())

    result = subprocess.run(
        ["bash", str(repo / "scripts/build-pi-image"), "coordinator"],
        env={"PATH": f"{tools}:{os.environ['PATH']}"},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert not (repo / ".cache").exists()


@pytest.mark.parametrize("failing_move", [2, 3])
def test_publication_failure_leaves_no_partial_artifact_pair(
    tmp_path: Path, failing_move: int
) -> None:
    repo = make_test_repo(tmp_path)
    tools = arm64_tools(tmp_path, successful_docker())
    move_count = tmp_path / "move-count"
    real_mv = shutil.which("mv")
    assert real_mv is not None
    write_executable(
        tools / "mv",
        f"""#!/bin/sh
count=$(cat "{move_count}" 2>/dev/null || echo 0)
count=$((count + 1))
echo "$count" >"{move_count}"
if [ "$count" -eq {failing_move} ]; then
    exit 1
fi
exec "{real_mv}" "$@"
""",
    )

    result = subprocess.run(
        ["bash", str(repo / "scripts/build-pi-image"), "coordinator"],
        env={"PATH": f"{tools}:{os.environ['PATH']}"},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    artifact_dir = repo / "artifacts/images/coordinator"
    assert list(artifact_dir.iterdir()) == []


def test_interrupted_publication_leaves_no_partial_artifact_pair(tmp_path: Path) -> None:
    repo = make_test_repo(tmp_path)
    tools = arm64_tools(tmp_path, successful_docker())
    move_count = tmp_path / "move-count"
    real_mv = shutil.which("mv")
    assert real_mv is not None
    write_executable(
        tools / "mv",
        f"""#!/bin/sh
count=$(cat "{move_count}" 2>/dev/null || echo 0)
count=$((count + 1))
echo "$count" >"{move_count}"
if [ "$count" -eq 3 ]; then
    kill -TERM "$PPID"
    exit 0
fi
exec "{real_mv}" "$@"
""",
    )

    result = subprocess.run(
        ["bash", str(repo / "scripts/build-pi-image"), "coordinator"],
        env={"PATH": f"{tools}:{os.environ['PATH']}"},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    artifact_dir = repo / "artifacts/images/coordinator"
    assert list(artifact_dir.iterdir()) == []


def test_builder_and_package_sources_are_immutable_where_upstream_allows() -> None:
    dockerfile = read(BUILDER / "Dockerfile")
    sources = read(BUILDER / "debian.sources")
    config = read(BUILDER / "base.yaml")
    script = read(BUILD_SCRIPT)

    revision = "262d4df5a9f9d4133370465399a7958a7c22cdc7"
    arm64_image = "sha256:c94f5ddd41327aa2d4a7cfba7889056c02936182fd76a513fec6160c97181fc0"
    assert revision in dockerfile and revision in script
    assert arm64_image in dockerfile
    assert "URIs: http://snapshot.debian.org/archive/debian/20260813T000000Z" in sources
    assert (
        "URIs: http://snapshot.debian.org/archive/debian-security/20260813T000000Z"
        in sources
    )
    assert sources.count("Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg") == 2
    assert sources.count("Check-Valid-Until: no") == 2
    assert "Trusted: yes" not in sources
    assert "debian-trixie-arm64-minbase-snapshot" in config
    assert "rpi-debian-trixie" in config
    assert 'PACKAGE_SNAPSHOT_EPOCH="1786579200"' in script


def test_container_has_only_explicit_writable_build_locations() -> None:
    script = read(BUILD_SCRIPT)

    assert '--platform linux/arm64' in script
    assert '--cap-add SYS_ADMIN' in script
    assert "--privileged" not in script
    assert 'dst=/source,readonly"' in script
    assert "--volume /work" in script
    assert "--volume /tmp" in script
    assert "type=volume,src=${PACKAGE_CACHE_VOLUME},dst=/cache,volume-nocopy" in script
    assert 'dst=/output"' in script
    assert "--tmpfs" not in script


def test_role_artifacts_have_a_verified_manifest() -> None:
    script = read(BUILD_SCRIPT)

    assert 'artifacts/images/${ROLE}' in script
    assert 'readonly IMAGE_PATH="${ARTIFACT_DIR}/${BUILD_ID}.img"' in script
    assert 'readonly MANIFEST_PATH="${ARTIFACT_DIR}/${BUILD_ID}.json"' in script
    for field in (
        "format_version",
        "role",
        "raspberry_pi_model",
        "os_release",
        "architecture",
        "builder_revision",
        "built_at",
        "git_commit",
        "git_dirty",
        "filename",
        "size_bytes",
        "sha256",
    ):
        assert f'"{field}"' in script


def test_generated_image_state_is_ignored() -> None:
    ignored = read(ROOT / ".gitignore")

    assert "/artifacts/images/" in ignored


def test_common_image_exposes_one_role_agnostic_definition() -> None:
    config = read(COMMON_CONFIG)

    assert "layer: rpi4" in config
    assert "e87: e87-common" in config
    assert "pubkey_only: y" in config
    for role_specific_value in (
        "coordinator",
        "console",
        "kcan",
        "ptcan",
        "fcan",
        "uart",
        "chromium",
        "cage",
        "10.42.",
        "10.43.",
    ):
        assert role_specific_value not in config

    for credential_setting in (
        "user1:",
        "user1pass:",
        "user1passhash:",
        "pubkey_user1:",
        "host_keydir:",
    ):
        assert credential_setting not in config


def test_common_layer_contains_runtime_dependencies_without_build_tools() -> None:
    layer = read(COMMON_LAYER)
    config = read(COMMON_CONFIG)

    for package in (
        "ca-certificates",
        "can-utils",
        "curl",
        "iproute2",
        "python3",
    ):
        assert f"    - {package}\n" in layer
    assert "network: network-manager" in config
    assert "wifi_backend: network-manager-iwd" in config
    for prohibited in (
        "apt ",
        "apt-get",
        "build-essential",
        "git",
        "nodejs",
        "npm",
        "pip",
        "pnpm",
        "uv ",
    ):
        assert prohibited not in layer.lower()


def test_common_layer_creates_service_state_and_versioned_provisioning_boundary() -> None:
    layer = read(COMMON_LAYER)
    interface_version = read(
        COMMON_OVERLAY / "usr/share/e87canbus/provisioning-interface"
    )

    assert "groupadd --system e87canbus" in layer
    assert "useradd --system --gid e87canbus" in layer
    assert 'userdel --remove "$IGconf_device_user1"' in layer
    assert 'groupdel "$IGconf_device_user1"' in layer
    assert "--home-dir /var/lib/e87canbus --no-create-home" in layer
    assert "--shell /usr/sbin/nologin e87canbus" in layer
    assert "install -d -o root -g e87canbus -m 0750 /opt/e87canbus" in layer
    assert (
        "install -d -o e87canbus -g e87canbus -m 0750 "
        "/etc/e87canbus /var/lib/e87canbus"
    ) in layer
    assert "install -d -o root -g root -m 0700 /var/lib/e87canbus-provisioning" in layer
    assert "/var/lib/e87canbus-provisioning/unprovisioned" in layer
    assert interface_version == "1\n"


def test_common_overlay_contains_only_the_public_interface_version() -> None:
    overlay_files = {
        path.relative_to(COMMON_OVERLAY).as_posix()
        for path in COMMON_OVERLAY.rglob("*")
        if path.is_file() or path.is_symlink()
    }

    assert overlay_files == {"usr/share/e87canbus/provisioning-interface"}
