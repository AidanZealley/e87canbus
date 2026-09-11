from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest

from e87ctl import cli

ROOT = Path(__file__).resolve().parents[2]
BUILD_SCRIPT = ROOT / "e87ctl/scripts/build-pi-image"
BUILDER = ROOT / "images/builder"
COMMON_CONFIG = ROOT / "images/common/image.yaml"
COMMON_LAYER = ROOT / "images/layer/e87-common.yaml"
COORDINATOR = ROOT / "images/coordinator"
COORDINATOR_CONFIG = COORDINATOR / "image.yaml"
COORDINATOR_LAYER = ROOT / "images/layer/e87-coordinator.yaml"
CONSOLE = ROOT / "images/console"
CONSOLE_CONFIG = CONSOLE / "image.yaml"
CONSOLE_LAYER = ROOT / "images/layer/e87-console.yaml"
IMAGE_RUNBOOK = ROOT / "images/README.md"
IMAGE_CHECK = ROOT / "images/e87canbus-image-check"
SNAPSHOT_CHECK = ROOT / "images/post-build.sh"


def read(path: Path) -> str:
    return path.read_text()


def write_executable(path: Path, contents: str) -> None:
    path.write_text(contents)
    path.chmod(0o755)


def make_test_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    shutil.copytree(BUILDER, repo / "images/builder")
    shutil.copytree(COMMON_CONFIG.parent, repo / "images/common")
    shutil.copytree(COORDINATOR, repo / "images/coordinator")
    shutil.copytree(CONSOLE, repo / "images/console")
    (repo / "e87ctl/scripts").mkdir(parents=True)
    shutil.copy2(BUILD_SCRIPT, repo / "e87ctl/scripts/build-pi-image")
    return repo


def arm64_tools(tmp_path: Path, docker: str) -> Path:
    tools = tmp_path / "tools"
    tools.mkdir()
    write_executable(tools / "uname", "#!/bin/sh\necho arm64\n")
    write_executable(tools / "docker", docker)
    return tools


def successful_docker(
    *, container_architecture: str = "aarch64", arguments_log: Path | None = None
) -> str:
    record_arguments = (
        f"printf '%s\\n' \"$@\" >{shlex.quote(str(arguments_log))}"
        if arguments_log is not None
        else ":"
    )
    return f"""#!/bin/sh
case "$1" in
    info | build) exit 0 ;;
    run)
        case " $* " in
            *" --entrypoint uname "*) echo {container_architecture}; exit 0 ;;
        esac
        {record_arguments}
        for argument in "$@"; do
            case "$argument" in
                type=bind,src=*,dst=/output)
                    output=${{argument#type=bind,src=}}
                    output=${{output%,dst=/output}}
                    case " $* " in
                        *" IGconf_image_name=e87-console "*) role=console ;;
                        *) role=coordinator ;;
                    esac
                    printf 'fake image bytes' >"$output/e87-$role.img"
                    exit 0
                    ;;
            esac
        done
        exit 1
        ;;
esac
"""


@pytest.mark.parametrize("role", ["coordinator", "console"])
def test_cli_builds_each_public_image_role(monkeypatch: pytest.MonkeyPatch, role: str) -> None:
    command: list[object] = []

    def run(arguments: list[object], *, check: bool) -> subprocess.CompletedProcess[str]:
        command.extend(arguments)
        assert check is False
        return subprocess.CompletedProcess(arguments, 0)

    monkeypatch.setattr(subprocess, "run", run)

    assert cli.main(["image", "build", role]) == 0
    assert command == [BUILD_SCRIPT, role]


def test_cli_rejects_an_unknown_image_role(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as error:
        cli.main(["image", "build", "base"])

    assert error.value.code == 2
    assert "invalid choice: 'base'" in capsys.readouterr().err


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
        ["bash", str(repo / "e87ctl/scripts/build-pi-image"), "coordinator"],
        env={"PATH": f"{tools}:{os.environ['PATH']}"},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "Container architecture: x86_64" in result.stdout
    assert "container architecture is x86_64" in result.stderr
    assert "native arm64 is required" in result.stderr


@pytest.mark.parametrize("role", ["coordinator", "console"])
def test_build_rejects_role_without_an_image_definition(tmp_path: Path, role: str) -> None:
    repo = make_test_repo(tmp_path)
    (repo / f"images/{role}/image.yaml").unlink()

    result = subprocess.run(
        ["bash", str(repo / "e87ctl/scripts/build-pi-image"), role],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert f"image definition images/{role}/image.yaml does not exist" in result.stderr
    assert not (repo / "artifacts").exists()


def test_build_rejects_partition_geometry_that_disagrees_with_the_contract(
    tmp_path: Path,
) -> None:
    repo = make_test_repo(tmp_path)
    tools = arm64_tools(tmp_path, successful_docker())
    common = repo / "images/common/image.yaml"
    common.write_text(common.read_text().replace("boot_part_size: 2G", "boot_part_size: 400%"))

    result = subprocess.run(
        ["bash", str(repo / "e87ctl/scripts/build-pi-image"), "coordinator"],
        env={"PATH": f"{tools}:{os.environ['PATH']}"},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "boot partition must match the 2 GiB manifest contract" in result.stderr
    assert not (repo / "artifacts").exists()


def test_successful_build_places_image_and_verified_manifest(tmp_path: Path) -> None:
    repo = make_test_repo(tmp_path)
    tools = arm64_tools(tmp_path, successful_docker())

    result = subprocess.run(
        ["bash", str(repo / "e87ctl/scripts/build-pi-image"), "coordinator"],
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
    assert re.fullmatch(
        r"e87-coordinator_\d{4}-\d{2}-\d{2}_\d{4}Z_nogit\.img",
        images[0].name,
    )
    assert manifests[0].stem == images[0].stem
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
        "provisioning_interface_version": 1,
        "boot_partition_size_bytes": 2 * 1024 * 1024 * 1024,
        "root_filesystem_size_bytes": 4 * 1024 * 1024 * 1024,
        "image": {
            "filename": images[0].name,
            "size_bytes": images[0].stat().st_size,
            "sha256": hashlib.sha256(images[0].read_bytes()).hexdigest(),
        },
    }


def test_console_build_manifest_identifies_only_the_pi4_console_role(tmp_path: Path) -> None:
    repo = make_test_repo(tmp_path)
    tools = arm64_tools(tmp_path, successful_docker())

    result = subprocess.run(
        ["bash", str(repo / "e87ctl/scripts/build-pi-image"), "console"],
        env={"PATH": f"{tools}:{os.environ['PATH']}"},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    manifests = list((repo / "artifacts/images/console").glob("*.json"))
    assert len(manifests) == 1
    manifest = json.loads(manifests[0].read_text())
    assert manifest["role"] == "console"
    assert manifest["raspberry_pi_model"] == "Raspberry Pi 4 Model B"


def test_build_uses_linux_volumes_for_temporary_state_and_package_cache(tmp_path: Path) -> None:
    repo = make_test_repo(tmp_path)
    tools = arm64_tools(tmp_path, successful_docker())

    result = subprocess.run(
        ["bash", str(repo / "e87ctl/scripts/build-pi-image"), "coordinator"],
        env={"PATH": f"{tools}:{os.environ['PATH']}"},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert not (repo / ".cache").exists()


def test_build_passes_snapshot_epoch_as_generated_configuration(tmp_path: Path) -> None:
    repo = make_test_repo(tmp_path)
    arguments_log = tmp_path / "docker-run-arguments"
    tools = arm64_tools(tmp_path, successful_docker(arguments_log=arguments_log))

    result = subprocess.run(
        ["bash", str(repo / "e87ctl/scripts/build-pi-image"), "coordinator"],
        env={"PATH": f"{tools}:{os.environ['PATH']}"},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    arguments = arguments_log.read_text().splitlines()
    separator = arguments.index("--")
    source_path = arguments.index("-S")
    assert arguments[source_path + 1] == "/source/images"
    assert "SOURCE_DATE_EPOCH=1786579200" in arguments[separator + 1 :]
    assert "--env" not in arguments


def test_snapshot_check_accepts_only_the_generated_pinned_origin(tmp_path: Path) -> None:
    assert os.access(SNAPSHOT_CHECK, os.X_OK)
    origin = tmp_path / "usr/share/rpi-image-gen/origin"
    origin.parent.mkdir(parents=True)
    origin.write_text(
        "# Layer: debian-trixie-arm64-minbase-snapshot\n"
        "# Source: trixie-snapshot.sources\n"
        "# Snapshot origin: 20260813T000000Z\n"
        "# SOURCE_DATE_EPOCH: 1786579200\n"
    )
    environment = {**os.environ, "SOURCE_DATE_EPOCH": "1786579200"}

    accepted = subprocess.run(
        ["sh", str(SNAPSHOT_CHECK), str(tmp_path)],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert accepted.returncode == 0, accepted.stderr

    origin.write_text(
        "# Layer: debian-trixie-arm64-minbase-snapshot\n"
        "# Source: trixie-snapshot.sources\n"
        "# Snapshot origin: 20260911T204739Z\n"
    )
    rejected = subprocess.run(
        ["sh", str(SNAPSHOT_CHECK), str(tmp_path)],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert rejected.returncode == 1
    assert "generated package snapshot origin does not match" in rejected.stderr


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
        ["bash", str(repo / "e87ctl/scripts/build-pi-image"), "coordinator"],
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
        ["bash", str(repo / "e87ctl/scripts/build-pi-image"), "coordinator"],
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
    common_config = read(COMMON_CONFIG)
    role_configs = (read(COORDINATOR_CONFIG), read(CONSOLE_CONFIG))
    script = read(BUILD_SCRIPT)

    revision = "262d4df5a9f9d4133370465399a7958a7c22cdc7"
    arm64_image = "sha256:c94f5ddd41327aa2d4a7cfba7889056c02936182fd76a513fec6160c97181fc0"
    assert revision in dockerfile and revision in script
    assert arm64_image in dockerfile
    assert "URIs: http://snapshot.debian.org/archive/debian/20260813T000000Z" in sources
    assert "URIs: http://snapshot.debian.org/archive/debian-security/20260813T000000Z" in sources
    assert sources.count("Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg") == 2
    assert sources.count("Check-Valid-Until: no") == 2
    assert "Trusted: yes" not in sources
    assert "debian-trixie-arm64-minbase-snapshot" in common_config
    assert "rpi-debian-trixie" in common_config
    assert all("file: ../common/image.yaml" in config for config in role_configs)
    assert 'PACKAGE_SNAPSHOT_EPOCH="1786579200"' in script


def test_container_has_only_explicit_writable_build_locations() -> None:
    script = read(BUILD_SCRIPT)

    assert "--platform linux/arm64" in script
    assert "--cap-add SYS_ADMIN" in script
    assert "--privileged" not in script
    assert 'dst=/source,readonly"' in script
    assert "--volume /work" in script
    assert "--volume /tmp" in script
    assert "type=volume,src=${PACKAGE_CACHE_VOLUME},dst=/cache,volume-nocopy" in script
    assert 'dst=/output"' in script
    assert "--tmpfs" not in script


def test_role_artifacts_have_a_verified_manifest() -> None:
    script = read(BUILD_SCRIPT)

    assert "artifacts/images/${ROLE}" in script
    assert 'readonly IMAGE_PATH="${ARTIFACT_DIR}/${BUILD_ID}.img"' in script
    assert 'readonly MANIFEST_PATH="${ARTIFACT_DIR}/${BUILD_ID}.json"' in script
    assert 'BUILD_ID="e87-${ROLE}_${BUILD_DATE}_${BUILD_HHMM}Z_' in script
    assert 'readonly DIRTY_SUFFIX="-dirty"' in script
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
        "provisioning_interface_version",
        "boot_partition_size_bytes",
        "root_filesystem_size_bytes",
        "filename",
        "size_bytes",
        "sha256",
    ):
        assert f'"{field}"' in script


def test_generated_image_state_is_ignored() -> None:
    ignored = read(ROOT / ".gitignore")

    assert "/artifacts/images/" in ignored


def test_hardware_runbook_uses_public_builds_and_test_card_only_access() -> None:
    runbook = read(IMAGE_RUNBOOK)

    assert "uv run e87ctl image build coordinator" in runbook
    assert "uv run e87ctl image build console" in runbook
    assert 'manifest=$(ls -t "artifacts/images/${role}"/*.json | head -n 1)' in runbook
    assert 'test "$actual" = "$expected"' in runbook
    assert "systemd.debug_shell=1" in runbook
    assert "copy `images/e87canbus-image-check`" in runbook
    assert "sh /boot/firmware/e87canbus-image-check coordinator" in runbook
    assert "sh /boot/firmware/e87canbus-image-check console" in runbook
    assert "changes only the flashed" in runbook
    assert "It creates no user or credential" in runbook
    assert "Do not report the images as accepted" in runbook
    assert "source of checkpoint assertions" in runbook


def test_hardware_checkpoint_script_covers_both_roles_and_parses() -> None:
    script = read(IMAGE_CHECK)

    for expected in (
        "coordinator | console",
        'test "$(uname -m)" = aarch64',
        "grep -qx 'VERSION_CODENAME=trixie' /etc/os-release",
        "tr -d '\\\\0' </proc/device-tree/model | grep -q '^Raspberry Pi 4 Model B'",
        "systemctl --failed --no-legend --plain",
        "systemctl is-active --quiet ssh.service",
        "authenticationmethods publickey",
        "! getent passwd 1000 >/dev/null",
        'findmnt -no LABEL /boot/firmware)" = bootfs',
        "test ! -e /var/lib/e87canbus-provisioning/unprovisioned",
        "test -L /opt/e87canbus/current",
        "test -e /dev/ttyAMA3",
        "e87canbus-controller.service e87canbus-firewall.service",
        "readlink -f /sys/class/net/kcan/device | grep -q '/spi0[.]0$'",
        "readlink -f /sys/class/net/ptcan/device | grep -q '/spi1[.]1$'",
        "readlink -f /sys/class/net/fcan/device | grep -q '/spi1[.]2$'",
        "ip -details link show kcan | grep -q 'bitrate 100000'",
        "ip -details link show ptcan | grep -q 'bitrate 500000'",
        "ip -details link show fcan | grep -q 'bitrate 500000'",
        "10.42.0.1/24",
        "e87canbus-coordinator-wifi",
        "net.ipv4.ip_forward",
        "/usr/local/libexec/e87canbus-hotspot $action",
        "e87canbus-console-kcan.service e87canbus-console.service",
        '[ "$interfaces" = kcan ]',
        "readlink -f /sys/class/net/kcan/device | grep -q '/spi1[.]1$'",
        "ip -details link show kcan | grep -Eq 'listen-only on|LISTEN-ONLY'",
        "10.42.0.2/24",
        "e87canbus-console-wifi",
        "/var/lib/e87-kiosk/.pki/nssdb/cert9.db",
        "command -v cage >/dev/null && command -v chromium >/dev/null",
        'find /dev/dri -maxdepth 1 -name "card*"',
        "ID_INPUT_TOUCHSCREEN=1",
        "e87canbus-console-kiosk.service",
    ):
        assert expected in script
    subprocess.run(["sh", "-n", str(IMAGE_CHECK)], check=True)


def test_hardware_runbook_covers_both_role_boundaries() -> None:
    runbook = read(IMAGE_RUNBOOK)

    for expected in (
        "Raspberry Pi 4 Model B",
        "Trixie arm64",
        "panel UART",
        "three CAN",
        "10.42.0.1/24",
        "kcan",
        "listen-only mode",
        "10.42.0.2/24",
        "DRM",
        "touchscreen",
        "strict first-boot consumer",
    ):
        assert expected in runbook

    for boundary in (
        "provisionable Raspberry Pi 4 coordinator and console image candidates",
        "e87canbus-provision.service",
        "unique host state",
        "MacBook, Raspberry",
        "Do not report the images as accepted",
    ):
        assert boundary in runbook
    assert "ft5|goodix" not in runbook
    assert "../images/README.md" in read(ROOT / "docs/setup.md")
    assert "../images/README.md" in read(ROOT / "deploy/README.md")


def test_common_image_exposes_one_role_agnostic_definition() -> None:
    config = read(COMMON_CONFIG)

    assert "layer: rpi4" in config
    assert "e87: e87-common" in config
    assert "pubkey_only: y" in config
    assert "boot_part_size: 2G" in config
    assert "root_part_size: 4G" in config
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

    assert "groupadd --system e87canbus" in layer
    assert "useradd --system --gid e87canbus" in layer
    assert 'userdel --remove "$IGconf_device_user1"' in layer
    assert 'groupdel "$IGconf_device_user1"' in layer
    assert "--home-dir /var/lib/e87canbus --no-create-home" in layer
    assert "--shell /usr/sbin/nologin e87canbus" in layer
    assert "install -d -o root -g e87canbus -m 0750 /opt/e87canbus" in layer
    assert "install -d -o root -g e87canbus -m 0750 /etc/e87canbus" in layer
    assert "install -d -o e87canbus -g e87canbus -m 0750 /var/lib/e87canbus" in layer
    assert "install -d -o root -g e87canbus -m 0750 /var/lib/e87canbus-provisioning" in layer
    assert "/var/lib/e87canbus-provisioning/unprovisioned" in layer
    assert "e87canbus-provision.service" in layer
    customize = read(ROOT / "images/common/customize.sh")
    assert 'rm -f "${target}/etc/machine-id"' in customize
    assert 'rm -f "${target}"/etc/ssh/ssh_host_*' in customize
    assert "e87canbus-provision" in customize
    assert not (ROOT / "images/layer/e87-common.rootfs-overlay").exists()


def test_coordinator_image_extends_common_with_one_role_layer() -> None:
    config = read(COORDINATOR_CONFIG)

    assert "file: ../common/image.yaml" in config
    assert "coordinator: e87-coordinator" in config
    assert "network-manager.cmds" not in config
    for prohibited in ("e87-console", "chromium", "cage", "simulator"):
        assert prohibited not in config


def test_coordinator_boot_configuration_matches_the_pi4_hardware() -> None:
    customize = read(COORDINATOR / "customize.sh")

    expected_lines = (
        "dtparam=spi=on",
        "dtoverlay=uart3",
        "dtoverlay=spi1-3cs",
        "dtoverlay=mcp2515-can0,oscillator=12000000,interrupt=25,spimaxfrequency=2000000",
        "dtoverlay=mcp2515,spi1-1,oscillator=16000000,interrupt=22,speed=10000000",
        "dtoverlay=mcp2515,spi1-2,oscillator=16000000,interrupt=13,speed=10000000",
        "enable_uart=1",
    )
    for line in expected_lines:
        assert customize.count(f"\n{line}\n") == 1
    assert "dtoverlay=i2c0" in customize
    assert "console=(serial0|ttyAMA0|ttyS0)" in customize
    assert customize.index("\n[pi4]\n") < customize.index("\ndtoverlay=uart3\n")


def test_coordinator_layer_installs_only_stable_runtime_packages_and_assets() -> None:
    layer = read(COORDINATOR_LAYER)
    customize = read(COORDINATOR / "customize.sh")

    assert "X-Env-Layer-Requires: e87-common" in layer
    for package in ("dnsmasq-base", "iw", "nftables", "nginx-light"):
        assert f"    - {package}\n" in layer
    for prohibited in ("git", "nodejs", "npm", "pnpm", "uv ", "build-essential"):
        assert prohibited not in layer.lower()

    canonical_assets = (
        "e87canbus-controller.service",
        "e87canbus-kcan.service",
        "e87canbus-ptcan.service",
        "e87canbus-fcan.service",
        "e87canbus-firewall.service",
        "e87canbus-dnsmasq.service",
        "e87canbus-nginx.service",
        "70-e87canbus-coordinator-can.rules",
        "e87canbus-hotspot",
        "controller.env.example",
    )
    for asset in canonical_assets:
        assert asset in customize
    assert '"$SRCROOT/../deploy"' in layer
    assert "usermod -aG dialout e87canbus" in customize
    assert "visudo -cf /etc/sudoers.d/e87canbus-hotspot" in customize
    assert '"${target}/usr/share/e87canbus"' in customize
    assert '"${IGconf_image_boot_part_size}" = 2G' in customize
    assert '"${IGconf_image_root_part_size}" = 4G' in customize


def test_coordinator_network_prerequisites_are_fixed_and_secret_free() -> None:
    assert not (COORDINATOR / "network-manager.cmds").exists()
    dnsmasq = read(ROOT / "deploy/network/dnsmasq.conf")
    firewall = read(ROOT / "deploy/network/nftables.conf")
    nginx = read(ROOT / "deploy/nginx/e87canbus.conf")
    dnsmasq_unit = read(ROOT / "deploy/systemd/e87canbus-dnsmasq.service")
    firewall_unit = read(ROOT / "deploy/systemd/e87canbus-firewall.service")
    firewall_helper = read(ROOT / "deploy/bin/e87canbus-firewall")
    nginx_unit = read(ROOT / "deploy/systemd/e87canbus-nginx.service")

    assert "dhcp-range=10.42.0.100,10.42.0.150" in dnsmasq
    assert "port=0" in dnsmasq
    assert "dhcp-option=3" in dnsmasq and "dhcp-option=6" in dnsmasq
    assert "StateDirectory=e87canbus-dnsmasq" in dnsmasq_unit
    assert "chain forward" in firewall and "policy drop" in firewall
    assert 'iifname "wlan0" tcp dport { 22, 443 } accept' in firewall
    assert "Before=NetworkManager.service" in firewall_unit
    assert "WantedBy=multi-user.target" in firewall_unit
    assert "delete table inet e87canbus" in firewall_helper
    assert "| exec /usr/sbin/nft --file -" in firewall_helper
    assert "listen 10.42.0.1:443 ssl" in nginx
    assert "ssl_verify_client optional" in nginx
    assert "X-E87-Client-Verify $ssl_client_verify" in nginx
    assert "X-E87-Client-Certificate $ssl_client_escaped_cert" in nginx
    assert "X-Forwarded-Host 10.42.0.1" in nginx
    assert "X-Forwarded-Proto https" in nginx
    assert "RuntimeDirectory=e87canbus-nginx" in nginx_unit
    assert "Restart=on-failure" in nginx_unit


def test_coordinator_application_is_gated_until_provisioning_installs_it() -> None:
    condition = read(COORDINATOR / "e87canbus-controller-provisioning.conf")
    layer = read(COORDINATOR_LAYER)

    assert "Requires=dev-ttyAMA3.device" in condition
    assert "After=dev-ttyAMA3.device" in condition
    assert "ConditionPathExists=!/var/lib/e87canbus-provisioning/unprovisioned" in condition
    assert "ConditionFileIsExecutable=/opt/e87canbus/current/venv/bin/e87canbus" in condition
    assert condition.count("--cors-origin") == 1
    assert "--cors-origin ${E87CANBUS_CONSOLE_ORIGIN}" in condition
    enabled = next(line for line in layer.splitlines() if "enable-units" in line)
    assert "e87canbus-controller.service" in enabled
    assert "e87canbus-nginx.service" in enabled
    assert "e87canbus-role.target" not in enabled


def test_coordinator_role_files_do_not_duplicate_deploy_assets() -> None:
    role_files = {
        path.relative_to(COORDINATOR).as_posix()
        for path in COORDINATOR.rglob("*")
        if path.is_file() or path.is_symlink()
    }

    assert role_files == {
        "customize.sh",
        "e87canbus-controller-provisioning.conf",
        "image.yaml",
    }


def test_console_image_extends_common_with_one_role_layer() -> None:
    config = read(CONSOLE_CONFIG)

    assert "file: ../common/image.yaml" in config
    assert "console: e87-console" in config
    assert "network-manager.cmds" not in config
    for prohibited in ("e87-coordinator", "ptcan", "fcan", "simulator", "pi5"):
        assert prohibited not in config


def test_console_boot_configuration_has_only_the_first_hat_controller() -> None:
    customize = read(CONSOLE / "customize.sh")

    expected_lines = (
        "dtparam=spi=on",
        "dtoverlay=spi1-3cs",
        "dtoverlay=mcp2515,spi1-1,oscillator=16000000,interrupt=22,speed=10000000",
        "disable_splash=1",
    )
    for line in expected_lines:
        assert customize.count(f"\n{line}\n") == 1
    assert "dtoverlay=mcp2515,spi1-2" not in customize
    assert "dtoverlay=mcp2515-can0," not in customize
    assert "\ndtoverlay=uart3\n" not in customize
    assert customize.index("\n[pi4]\n") < customize.index("\ndtoverlay=spi1-3cs\n")
    for parameter in ("quiet", "splash", "loglevel=3", "logo.nologo"):
        assert parameter in customize
    assert "vt.global_cursor_default=0" in customize


def test_console_layer_installs_lite_kiosk_packages_and_canonical_assets() -> None:
    layer = read(CONSOLE_LAYER)
    customize = read(CONSOLE / "customize.sh")

    assert "X-Env-Layer-Requires: e87-common" in layer
    for package in (
        "cage",
        "chromium",
        "chromium-sandbox",
        "libnss3-tools",
        "libpam-systemd",
        "plymouth",
    ):
        assert f"    - {package}\n" in layer
    for prohibited in (
        "avahi-daemon",
        "desktop",
        "git",
        "nodejs",
        "npm",
        "pnpm",
        "sudo",
        "uv ",
    ):
        assert prohibited not in layer.lower()

    canonical_assets = (
        "e87canbus-console-kcan.service",
        "e87canbus-console.service",
        "e87canbus-console-kiosk.service",
        "console.env.example",
        "70-e87canbus-console-can.rules",
        "71-e87canbus-kiosk-input.rules",
        "start-console-kiosk.sh",
    )
    for asset in canonical_assets:
        assert asset in customize
    assert '"$SRCROOT/../deploy"' in layer
    assert '"${IGconf_image_boot_part_size}" = 2G' in customize
    assert '"${IGconf_image_root_part_size}" = 4G' in customize
    for coordinator_asset in (
        "e87canbus-controller.service",
        "e87canbus-ptcan.service",
        "e87canbus-fcan.service",
        "e87canbus-hotspot",
    ):
        assert coordinator_asset not in customize


def test_console_network_prerequisite_is_fixed_and_non_routing() -> None:
    assert not (CONSOLE / "network-manager.cmds").exists()
    customize = read(CONSOLE / "customize.sh")
    layer = read(CONSOLE_LAYER)
    assert "libnss3-tools" in layer
    assert '"role":"console"' in customize


def test_console_application_and_kiosk_wait_for_provisioning() -> None:
    application_condition = read(CONSOLE / "e87canbus-console-provisioning.conf")
    kiosk_condition = read(CONSOLE / "e87canbus-console-kiosk-provisioning.conf")
    layer = read(CONSOLE_LAYER)
    enabled_units = next(line for line in layer.splitlines() if "enable-units" in line)

    marker_condition = "ConditionPathExists=!/var/lib/e87canbus-provisioning/unprovisioned"
    assert marker_condition in application_condition
    assert marker_condition in kiosk_condition
    assert (
        "ConditionFileIsExecutable=/opt/e87canbus/current/venv/bin/e87canbus-console"
        in application_condition
    )
    assert "ConditionPathExists=/opt/e87canbus/current/frontend/index.html" in kiosk_condition
    assert "e87canbus-console-kcan.service" in enabled_units
    assert "e87canbus-console.service" in enabled_units
    assert "e87canbus-console-kiosk.service" in enabled_units
    assert "e87canbus-role.target" not in enabled_units


def test_console_role_files_do_not_duplicate_deploy_assets() -> None:
    role_files = {
        path.relative_to(CONSOLE).as_posix()
        for path in CONSOLE.rglob("*")
        if path.is_file() or path.is_symlink()
    }

    assert role_files == {
        "customize.sh",
        "e87canbus-console-kiosk-provisioning.conf",
        "e87canbus-console-provisioning.conf",
        "image.yaml",
    }
