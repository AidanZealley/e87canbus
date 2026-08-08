#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPECTED_ROOT="/opt/e87canbus"
CONFIG_FILE=""
CMDLINE_FILE=""
REBOOT_REQUESTED=0
REBOOT_REQUIRED=0
DEPLOYMENT_PROFILE="car"
HOTSPOT_PASSWORD_FILE=""
FLASH_PANEL=0
HOTSPOT_UUID="9ec8d6d7-1c26-46aa-a4c8-7af8a1d0f652"
HOTSPOT_NAME="e87canbus-hotspot"
HOTSPOT_SSID="E87-Coordinator"
HOTSPOT_INTERFACE="wlan0"
HOTSPOT_ADDRESS="192.168.50.1/24"
CAN_INTERFACES=(can0 can1 can2)
CAN_SERVICES=(
    e87canbus-can0.service
    e87canbus-can1.service
    e87canbus-can2.service
)

if [[ "${EUID}" -eq 0 ]]; then
    echo "Run this script as the checkout owner, not as root; it uses sudo for system changes." >&2
    exit 1
fi

if [[ "${REPO_ROOT}" != "${EXPECTED_ROOT}" ]]; then
    echo "This deployment script expects the repository at ${EXPECTED_ROOT}." >&2
    echo "Current checkout: ${REPO_ROOT}" >&2
    exit 1
fi

while [[ "$#" -gt 0 ]]; do
    case "$1" in
        --profile)
            if [[ "$#" -lt 2 ]]; then
                echo "--profile requires car, bench, or simulator" >&2
                exit 2
            fi
            DEPLOYMENT_PROFILE="$2"
            shift 2
            ;;
        --reboot)
            REBOOT_REQUESTED=1
            shift
            ;;
        --hotspot-password-file)
            if [[ "$#" -lt 2 ]]; then
                echo "--hotspot-password-file requires a readable file" >&2
                exit 2
            fi
            HOTSPOT_PASSWORD_FILE="$2"
            shift 2
            ;;
        --flash-panel)
            FLASH_PANEL=1
            shift
            ;;
        *)
            echo "Usage: $0 [--profile car|bench|simulator] [--hotspot-password-file PATH] [--flash-panel] [--reboot]" >&2
            exit 2
            ;;
    esac
done

case "${DEPLOYMENT_PROFILE}" in
    car|bench|simulator) ;;
    *)
        echo "Unsupported deployment profile: ${DEPLOYMENT_PROFILE}" >&2
        exit 2
        ;;
esac
echo "Deployment profile: ${DEPLOYMENT_PROFILE}"

# ---------------------------------------------------------------------------
# Kiosk mode detection
#   desktop — a display manager is installed; use XDG autostart
#   headless — no display manager; use cage as a system service
# ---------------------------------------------------------------------------
KIOSK_MODE="headless"
for dm in lightdm gdm3 gdm sddm lxdm wdm; do
    if dpkg-query -W -f='${Status}' "$dm" 2>/dev/null | grep -q "install ok installed"; then
        KIOSK_MODE="desktop"
        break
    fi
done
echo "Kiosk mode: ${KIOSK_MODE}"

# ---------------------------------------------------------------------------
# Boot config paths
# ---------------------------------------------------------------------------
if [[ -f /boot/firmware/config.txt ]]; then
    CONFIG_FILE=/boot/firmware/config.txt
elif [[ -f /boot/config.txt ]]; then
    CONFIG_FILE=/boot/config.txt
else
    echo "Could not find Raspberry Pi boot config.txt." >&2
    exit 1
fi

if [[ -f /boot/firmware/cmdline.txt ]]; then
    CMDLINE_FILE=/boot/firmware/cmdline.txt
elif [[ -f /boot/cmdline.txt ]]; then
    CMDLINE_FILE=/boot/cmdline.txt
else
    echo "Could not find Raspberry Pi cmdline.txt." >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Package installation
# ---------------------------------------------------------------------------
echo "Installing Pi packages..."
sudo apt-get update

PACKAGES="can-utils build-essential python3 python3-pip python3-venv nodejs npm curl iproute2 network-manager"

if [[ "${KIOSK_MODE}" == "headless" ]]; then
    # Chromium — package name varies by distro
    CHROMIUM_PKG=""
    for cpkg in chromium-browser chromium; do
        if apt-cache show "${cpkg}" >/dev/null 2>&1; then
            CHROMIUM_PKG="${cpkg}"
            break
        fi
    done
    if [[ -n "${CHROMIUM_PKG}" ]]; then
        PACKAGES="${PACKAGES} ${CHROMIUM_PKG}"
    else
        echo "WARNING: No Chromium apt package found; install it manually (e.g. via snap)." >&2
    fi

    PACKAGES="${PACKAGES} cage plymouth"
    if apt-cache show plymouth-themes >/dev/null 2>&1; then
        PACKAGES="${PACKAGES} plymouth-themes"
    fi
fi

# shellcheck disable=SC2086
sudo apt-get install -y ${PACKAGES}

if ! command -v uv >/dev/null 2>&1; then
    echo "Installing uv..."
    sudo python3 -m pip install --break-system-packages uv
fi

if ! command -v pnpm >/dev/null 2>&1; then
    echo "Installing pnpm..."
    sudo npm install --global pnpm@9.15.1
fi

# ---------------------------------------------------------------------------
# SPI and Waveshare MCP2515 overlays
# ---------------------------------------------------------------------------
if [[ "${DEPLOYMENT_PROFILE}" != "simulator" ]]; then
    echo "Configuring SPI and the three-channel Waveshare MCP2515 stack..."
    sudo cp -n "${CONFIG_FILE}" "${CONFIG_FILE}.e87canbus-before-setup" || true

    reconcile_boot_line() {
        local pattern="$1"
        local desired="$2"
        local matching_count
        local exact_count

        matching_count="$(sudo grep -Ec "${pattern}" "${CONFIG_FILE}" || true)"
        exact_count="$(sudo grep -Fxc "${desired}" "${CONFIG_FILE}" || true)"
        if [[ "${matching_count}" -eq 1 && "${exact_count}" -eq 1 ]]; then
            return
        fi

        sudo sed -E -i "/${pattern}/d" "${CONFIG_FILE}"
        echo "${desired}" | sudo tee -a "${CONFIG_FILE}" >/dev/null
        REBOOT_REQUIRED=1
    }

    reconcile_boot_line \
        '^[[:space:]]*dtparam=spi=' \
        'dtparam=spi=on'
    reconcile_boot_line \
        '^[[:space:]]*dtoverlay=i2c0([,[:space:]]|$)' \
        'dtoverlay=i2c0'
    reconcile_boot_line \
        '^[[:space:]]*dtoverlay=spi1-(1|2|3)cs([,[:space:]]|$)' \
        'dtoverlay=spi1-3cs'
    reconcile_boot_line \
        '^[[:space:]]*dtoverlay=(mcp2515-can0([,[:space:]]|$)|mcp2515,.*spi0-0([,[:space:]]|$))' \
        'dtoverlay=mcp2515-can0,oscillator=12000000,interrupt=25,spimaxfrequency=2000000'
    reconcile_boot_line \
        '^[[:space:]]*dtoverlay=mcp2515,.*spi1-1([,[:space:]]|$)' \
        'dtoverlay=mcp2515,spi1-1,oscillator=16000000,interrupt=22,speed=10000000'
    reconcile_boot_line \
        '^[[:space:]]*dtoverlay=mcp2515,.*spi1-2([,[:space:]]|$)' \
        'dtoverlay=mcp2515,spi1-2,oscillator=16000000,interrupt=13,speed=10000000'

    # Keep Pi 4 Bluetooth on its normal controller. enable_uart stabilizes and exposes the
    # primary GPIO UART as /dev/serial0 without applying disable-bt or miniuart-bt overlays.
    reconcile_boot_line \
        '^[[:space:]]*enable_uart=' \
        'enable_uart=1'

    sudo cp -n "${CMDLINE_FILE}" "${CMDLINE_FILE}.e87canbus-before-setup" || true
    CMDLINE_BEFORE="$(sudo cat "${CMDLINE_FILE}")"
    CMDLINE_AFTER="$(printf '%s\n' "${CMDLINE_BEFORE}" | sed -E \
        's/(^|[[:space:]])console=(serial0|ttyAMA0|ttyS0),[^[:space:]]+//g; s/[[:space:]]+/ /g; s/^ //; s/ $//')"
    if [[ "${CMDLINE_AFTER}" != "${CMDLINE_BEFORE}" ]]; then
        printf '%s\n' "${CMDLINE_AFTER}" | sudo tee "${CMDLINE_FILE}" >/dev/null
        REBOOT_REQUIRED=1
    fi
fi

# ---------------------------------------------------------------------------
# Quiet boot (headless only)
#   Suppresses kernel messages and the Pi logo so nothing appears on screen
#   until cage takes over.
# ---------------------------------------------------------------------------
if [[ "${KIOSK_MODE}" == "headless" ]]; then
    echo "Configuring quiet boot..."
    for param in quiet splash loglevel=3 logo.nologo vt.global_cursor_default=0; do
        if ! grep -qw "${param}" "${CMDLINE_FILE}"; then
            sudo sed -i "s/$/ ${param}/" "${CMDLINE_FILE}"
            REBOOT_REQUIRED=1
        fi
    done
fi

# ---------------------------------------------------------------------------
# Python dependencies and frontend build
# ---------------------------------------------------------------------------
echo "Synchronizing Python dependencies..."
# Use the system interpreter so the systemd service account does not depend on a Python
# installation inside the invoking user's home directory.
uv sync --frozen --python /usr/bin/python3

echo "Building the frontend..."
(
    cd "${REPO_ROOT}/frontend"
    pnpm install --frozen-lockfile
    pnpm build
)

# ---------------------------------------------------------------------------
# Service account and controller systemd units
# ---------------------------------------------------------------------------
echo "Installing the e87canbus service account and deployment files..."
if ! getent group e87canbus >/dev/null; then
    sudo groupadd --system e87canbus
fi
if ! id e87canbus >/dev/null 2>&1; then
    sudo useradd --system --gid e87canbus --home-dir /var/lib/e87canbus \
        --create-home --shell /usr/sbin/nologin e87canbus
fi
if [[ "${DEPLOYMENT_PROFILE}" != "simulator" ]]; then
    sudo usermod -aG dialout e87canbus
fi

# The checkout and its uv environment are built as the invoking user, while systemd runs the
# service as e87canbus. Keep ownership with the checkout owner but grant the service group access.
sudo chgrp -R e87canbus "${REPO_ROOT}"
sudo chmod -R g+rX "${REPO_ROOT}"
# Stop the controller before repairing the database set so SQLite cannot be writing its WAL or
# shared-memory file while their ownership is changed. This also repairs databases created by an
# older deployment that ran the application as the checkout user.
sudo systemctl stop e87canbus-controller.service 2>/dev/null || true
sudo install -d -o e87canbus -g e87canbus -m 0750 /var/lib/e87canbus /etc/e87canbus
for database_file in \
    /var/lib/e87canbus/application.sqlite3 \
    /var/lib/e87canbus/application.sqlite3-wal \
    /var/lib/e87canbus/application.sqlite3-shm; do
    if [[ -e "${database_file}" ]]; then
        sudo chown e87canbus:e87canbus "${database_file}"
        sudo chmod 0640 "${database_file}"
    fi
done
for can_service in "${CAN_SERVICES[@]}"; do
    sudo install -o root -g root -m 0644 \
        "${REPO_ROOT}/deploy/systemd/${can_service}" \
        "/etc/systemd/system/${can_service}"
done
sudo install -o root -g root -m 0644 \
    "${REPO_ROOT}/deploy/systemd/e87canbus-controller.service" \
    /etc/systemd/system/e87canbus-controller.service
sudo install -o root -g e87canbus -m 0640 \
    "${REPO_ROOT}/deploy/systemd/controller.env.example" \
    /etc/e87canbus/controller.env
sudo sed -i \
    "s/^E87CANBUS_PROFILE=.*/E87CANBUS_PROFILE=${DEPLOYMENT_PROFILE}/" \
    /etc/e87canbus/controller.env

if [[ "${DEPLOYMENT_PROFILE}" != "simulator" ]]; then
    echo "Provisioning the fixed coordinator hotspot boundary..."
    sudo install -d -o root -g root -m 0755 /usr/local/libexec
    sudo install -o root -g root -m 0755 \
        "${REPO_ROOT}/deploy/hotspot/e87canbus-hotspot" \
        /usr/local/libexec/e87canbus-hotspot
    sudo install -o root -g root -m 0440 \
        "${REPO_ROOT}/deploy/hotspot/e87canbus-hotspot.sudoers" \
        /etc/sudoers.d/e87canbus-hotspot
    sudo visudo -cf /etc/sudoers.d/e87canbus-hotspot >/dev/null

    if sudo nmcli --terse --get-values connection.uuid connection show uuid \
        "${HOTSPOT_UUID}" >/dev/null 2>&1; then
        EXISTING_HOTSPOT_TYPE="$(sudo nmcli --terse --get-values connection.type \
            connection show uuid "${HOTSPOT_UUID}")"
        if [[ "${EXISTING_HOTSPOT_TYPE}" != "802-11-wireless" ]]; then
            echo "The managed hotspot UUID belongs to a non-Wi-Fi profile; refusing to modify it." >&2
            exit 1
        fi
        sudo nmcli connection modify uuid "${HOTSPOT_UUID}" \
            connection.id "${HOTSPOT_NAME}" \
            connection.interface-name "${HOTSPOT_INTERFACE}" \
            connection.autoconnect no \
            802-11-wireless.mode ap \
            802-11-wireless.ssid "${HOTSPOT_SSID}" \
            wifi-sec.key-mgmt wpa-psk \
            ipv4.method shared \
            ipv4.addresses "${HOTSPOT_ADDRESS}" \
            ipv6.method disabled >/dev/null
    else
        if [[ -z "${HOTSPOT_PASSWORD_FILE}" || ! -r "${HOTSPOT_PASSWORD_FILE}" ]]; then
            echo "The managed hotspot does not exist. Pass --hotspot-password-file with an out-of-repository WPA password file." >&2
            exit 1
        fi
        if [[ "$(stat -c '%u:%a' "${HOTSPOT_PASSWORD_FILE}")" != "${EUID}:600" ]]; then
            echo "The hotspot password file must be owned by the invoking user with mode 0600." >&2
            exit 1
        fi
        HOTSPOT_PASSWORD="$(<"${HOTSPOT_PASSWORD_FILE}")"
        if [[ "${#HOTSPOT_PASSWORD}" -lt 8 || "${#HOTSPOT_PASSWORD}" -gt 63 ]]; then
            echo "The hotspot password must contain 8 to 63 characters." >&2
            exit 1
        fi
        if ! sudo nmcli connection add type wifi ifname "${HOTSPOT_INTERFACE}" \
                con-name "${HOTSPOT_NAME}" ssid "${HOTSPOT_SSID}" \
                connection.uuid "${HOTSPOT_UUID}" \
                connection.autoconnect no \
                802-11-wireless.mode ap \
                wifi-sec.key-mgmt wpa-psk \
                wifi-sec.psk "${HOTSPOT_PASSWORD}" \
                ipv4.method shared \
                ipv4.addresses "${HOTSPOT_ADDRESS}" \
                ipv6.method disabled >/dev/null 2>&1; then
            unset HOTSPOT_PASSWORD
            echo "NetworkManager rejected the managed hotspot profile." >&2
            exit 1
        fi
        unset HOTSPOT_PASSWORD
    fi
    sudo nmcli connection down uuid "${HOTSPOT_UUID}" >/dev/null 2>&1 || true
fi

if [[ "${FLASH_PANEL}" -eq 1 ]]; then
    echo "Building and flashing the coordinator panel firmware..."
    (
        cd "${REPO_ROOT}/devices/coordinator-panel"
        uv tool run --from platformio==6.1.18 pio run -e qtpy_rp2040 -t upload
    )
    PANEL_FIRMWARE_HASH="$(sha256sum \
        "${REPO_ROOT}/devices/coordinator-panel/.pio/build/qtpy_rp2040/firmware.uf2" \
        | cut -d ' ' -f 1)"
    PANEL_SOURCE_REVISION="$(git -C "${REPO_ROOT}" rev-parse HEAD)"
    printf 'source_revision=%s\nfirmware_sha256=%s\n' \
        "${PANEL_SOURCE_REVISION}" "${PANEL_FIRMWARE_HASH}" \
        | sudo tee /var/lib/e87canbus/coordinator-panel-firmware-version >/dev/null
fi

# ---------------------------------------------------------------------------
# Kiosk startup script (shared by desktop and headless environments)
# ---------------------------------------------------------------------------
echo "Installing kiosk startup script..."
sudo install -o root -g root -m 0755 \
    "${REPO_ROOT}/deploy/kiosk/start-kiosk.sh" \
    /usr/local/bin/e87canbus-kiosk

# ---------------------------------------------------------------------------
# Kiosk launch — environment-specific
# ---------------------------------------------------------------------------
if [[ "${KIOSK_MODE}" == "desktop" ]]; then
    echo "Configuring desktop autostart for user '${USER}'..."
    mkdir -p "${HOME}/.config/autostart"
    cp "${REPO_ROOT}/deploy/kiosk/e87canbus-kiosk.desktop" \
        "${HOME}/.config/autostart/e87canbus-kiosk.desktop"

    # Remove cage service if re-running after switching from headless
    if [[ -f /etc/systemd/system/e87canbus-kiosk.service ]]; then
        sudo systemctl disable e87canbus-kiosk.service 2>/dev/null || true
        sudo rm -f /etc/systemd/system/e87canbus-kiosk.service
    fi
else
    echo "Configuring headless kiosk (cage) for user '${USER}'..."

    # Display hardware access — takes effect after reboot
    DISPLAY_GROUP_CHANGE_REQUIRED=0
    for display_group in video render input; do
        if ! id -nG "${USER}" | tr ' ' '\n' | grep -Fxq "${display_group}"; then
            DISPLAY_GROUP_CHANGE_REQUIRED=1
            break
        fi
    done
    if [[ "${DISPLAY_GROUP_CHANGE_REQUIRED}" -eq 1 ]]; then
        sudo usermod -aG video,render,input "${USER}"
        REBOOT_REQUIRED=1
    fi

    # Plymouth splash — keeps the screen non-blank until cage takes over.
    # Tries themes in preference order; falls back gracefully if unavailable.
    if command -v plymouth-set-default-theme >/dev/null 2>&1; then
        echo "Configuring Plymouth splash theme..."
        PLYMOUTH_THEME=""
        for theme in spinner fade-in solar bgrt; do
            if sudo plymouth-set-default-theme "${theme}" 2>/dev/null; then
                PLYMOUTH_THEME="${theme}"
                break
            fi
        done
        if [[ -n "${PLYMOUTH_THEME}" ]]; then
            echo "Plymouth theme set to '${PLYMOUTH_THEME}'; updating initramfs (may take a minute)..."
            sudo update-initramfs -u
        else
            echo "No preferred Plymouth theme available; boot screen may show text."
        fi
    fi

    # cage systemd service — templates the invoking user into the unit file
    sed "s|KIOSK_USER_PLACEHOLDER|${USER}|g" \
        "${REPO_ROOT}/deploy/systemd/e87canbus-kiosk.service" \
        | sudo tee /etc/systemd/system/e87canbus-kiosk.service >/dev/null
    sudo chmod 0644 /etc/systemd/system/e87canbus-kiosk.service
    sudo chown root:root /etc/systemd/system/e87canbus-kiosk.service

    # Remove XDG autostart if re-running after switching from desktop
    rm -f "${HOME}/.config/autostart/e87canbus-kiosk.desktop"
fi

# ---------------------------------------------------------------------------
# Enable services
# ---------------------------------------------------------------------------
sudo systemctl daemon-reload
if [[ "${DEPLOYMENT_PROFILE}" == "simulator" ]]; then
    sudo systemctl disable --now "${CAN_SERVICES[@]}" 2>/dev/null || true
else
    sudo systemctl enable "${CAN_SERVICES[@]}"
    # Do not allow the application to start at boot until the post-reboot run
    # has proved that Linux assigned each CAN name to the expected SPI device.
    sudo systemctl disable e87canbus-controller.service 2>/dev/null || true
fi
if [[ "${KIOSK_MODE}" == "headless" ]]; then
    sudo systemctl enable e87canbus-kiosk.service
fi

# ---------------------------------------------------------------------------
# Reboot gate — boot config or group changes require a reboot before services
# can be started. Services are already enabled above; they start on next boot.
# ---------------------------------------------------------------------------
if [[ "${REBOOT_REQUIRED}" -eq 1 ]]; then
    echo
    echo "Boot configuration changed; reboot is required before can0, can1, and can2 can appear."
    if [[ "${REBOOT_REQUESTED}" -eq 1 ]]; then
        sudo reboot
    else
        echo "Reboot, then run this script again to validate the CAN stack and start the services:"
        echo "  sudo reboot"
        echo "  cd ${REPO_ROOT} && ./scripts/setup_pi.sh --profile ${DEPLOYMENT_PROFILE}"
    fi
    exit 0
fi

if [[ "${DEPLOYMENT_PROFILE}" != "simulator" ]]; then
    EXPECTED_SPI_PARENTS=(spi0.0 spi1.1 spi1.2)
    for index in "${!CAN_INTERFACES[@]}"; do
        interface="${CAN_INTERFACES[${index}]}"
        if ! ip link show "${interface}" >/dev/null 2>&1; then
            echo "${interface} is not available; leaving the controller stopped." >&2
            echo "Check the three-channel CAN hardware and boot overlays, then rerun setup." >&2
            sudo systemctl disable --now e87canbus-controller.service 2>/dev/null || true
            sudo systemctl stop "${CAN_SERVICES[@]}" 2>/dev/null || true
            exit 1
        fi

        device_path="$(readlink -f "/sys/class/net/${interface}/device" || true)"
        actual_spi_parent="${device_path##*/}"
        expected_spi_parent="${EXPECTED_SPI_PARENTS[${index}]}"
        if [[ "${actual_spi_parent}" != "${expected_spi_parent}" ]]; then
            echo "${interface} maps to ${actual_spi_parent:-an unknown device}, expected ${expected_spi_parent}; leaving the controller stopped." >&2
            echo "Check the HAT chip-select configuration and boot overlays, then rerun setup." >&2
            sudo systemctl disable --now e87canbus-controller.service 2>/dev/null || true
            sudo systemctl stop "${CAN_SERVICES[@]}" 2>/dev/null || true
            exit 1
        fi
        echo "Validated ${interface} -> ${actual_spi_parent}"
    done

    if [[ ! -c "$(readlink -f /dev/serial0)" ]]; then
        echo "/dev/serial0 does not resolve to a character device; leaving the controller stopped." >&2
        sudo systemctl disable --now e87canbus-controller.service 2>/dev/null || true
        exit 1
    fi
    if ! sudo -u e87canbus test -r /dev/serial0 || ! sudo -u e87canbus test -w /dev/serial0; then
        echo "The e87canbus account cannot read and write /dev/serial0." >&2
        exit 1
    fi
    echo "Validated /dev/serial0 -> $(readlink -f /dev/serial0)"

    HOTSPOT_SETTINGS="$(sudo nmcli --terse --get-values \
        connection.uuid,connection.type,connection.interface-name,connection.autoconnect,802-11-wireless.mode,802-11-wireless.ssid,802-11-wireless-security.key-mgmt,ipv4.method,ipv4.addresses,ipv6.method \
        connection show uuid "${HOTSPOT_UUID}")"
    EXPECTED_HOTSPOT_SETTINGS="${HOTSPOT_UUID}:802-11-wireless:${HOTSPOT_INTERFACE}:no:ap:${HOTSPOT_SSID}:wpa-psk:shared:${HOTSPOT_ADDRESS}:disabled"
    if [[ "${HOTSPOT_SETTINGS}" != "${EXPECTED_HOTSPOT_SETTINGS}" ]]; then
        echo "The managed hotspot settings failed validation; leaving the controller stopped." >&2
        exit 1
    fi
    sudo -u e87canbus sudo -n /usr/local/libexec/e87canbus-hotspot \
        --terse --get-values GENERAL.STATE connection show uuid "${HOTSPOT_UUID}" >/dev/null
    if sudo -u e87canbus sudo -n /usr/local/libexec/e87canbus-hotspot \
        --terse --get-values GENERAL.STATE connection show uuid \
        00000000-0000-0000-0000-000000000000 >/dev/null 2>&1; then
        echo "The hotspot helper unexpectedly accepted an unrelated connection UUID." >&2
        exit 1
    fi
    echo "Validated managed hotspot ${HOTSPOT_UUID} and its narrow service-account helper"
fi

if [[ "${DEPLOYMENT_PROFILE}" != "simulator" ]]; then
    echo "Starting the boot-managed can0, can1, and can2 services..."
    sudo systemctl start "${CAN_SERVICES[@]}"
fi
sudo systemctl enable e87canbus-controller.service
sudo systemctl restart e87canbus-controller.service

echo
echo "Pi setup complete. Check:"
echo "  installed profile: ${DEPLOYMENT_PROFILE}"
echo "  systemctl status e87canbus-controller.service"
echo "  journalctl -u e87canbus-controller.service -f"
if [[ "${DEPLOYMENT_PROFILE}" != "simulator" ]]; then
    echo "  ip -details link show can0"
    echo "  ip -details link show can1"
    echo "  ip -details link show can2"
    echo "  candump can0"
    echo "  candump can1"
    echo "  candump can2"
fi
echo
if [[ "${KIOSK_MODE}" == "desktop" ]]; then
    echo "Kiosk: autostart installed for '${USER}'. Chromium opens at /car on next desktop login."
else
    echo "Kiosk: cage service installed for '${USER}'. Chromium opens at /car on next boot."
fi
