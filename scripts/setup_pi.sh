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
HOTSPOT_CONNECTION="e87canbus-hotspot"
HOTSPOT_SSID="e87canbus"
CAN_INTERFACES=(kcan ptcan fcan)
CAN_SERVICES=(
    e87canbus-kcan.service
    e87canbus-ptcan.service
    e87canbus-fcan.service
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
        *)
            echo "Usage: $0 [--profile car|bench|simulator] [--hotspot-password-file PATH] [--reboot]" >&2
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
if [[ "${DEPLOYMENT_PROFILE}" == "simulator" && -n "${HOTSPOT_PASSWORD_FILE}" ]]; then
    echo "--hotspot-password-file is only valid for the car and bench profiles" >&2
    exit 2
fi
echo "Deployment profile: ${DEPLOYMENT_PROFILE}"

if [[ "${DEPLOYMENT_PROFILE}" != "simulator" ]]; then
    if [[ ! -r /proc/device-tree/model ]]; then
        echo "Cannot identify the Raspberry Pi model; physical profiles require a Raspberry Pi 4 Model B." >&2
        exit 1
    fi
    PI_MODEL="$(tr -d '\0' < /proc/device-tree/model)"
    if [[ "${PI_MODEL}" != "Raspberry Pi 4 Model B"* ]]; then
        echo "Unsupported physical coordinator: ${PI_MODEL}" >&2
        echo "The car and bench profiles require a Raspberry Pi 4 Model B." >&2
        exit 1
    fi
    echo "Physical coordinator: ${PI_MODEL}"
fi

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

PACKAGES="can-utils build-essential python3 python3-pip python3-venv nodejs npm curl"

if [[ "${DEPLOYMENT_PROFILE}" != "simulator" ]]; then
    # NetworkManager supplies the fixed access point and iw provides the target's station view.
    # pyserial is installed in the application environment by uv.
    PACKAGES="${PACKAGES} network-manager iw"
fi

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
    echo "Configuring SPI, UART, and the three-channel Waveshare MCP2515 stack..."
    sudo cp -n "${CONFIG_FILE}" "${CONFIG_FILE}.e87canbus-before-setup" || true
    sudo cp -n "${CMDLINE_FILE}" "${CMDLINE_FILE}.e87canbus-before-setup" || true

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
    # Waveshare includes i2c0 in its HAT+ example, but CAN uses SPI and does not need it.
    # Exposing i2c0 prevents the BTT TFT50's DSI touch/backlight controller from probing.
    if sudo grep -Eq '^[[:space:]]*dtoverlay=i2c0([,[:space:]]|$)' "${CONFIG_FILE}"; then
        sudo sed -E -i '/^[[:space:]]*dtoverlay=i2c0([,[:space:]]|$)/d' "${CONFIG_FILE}"
        REBOOT_REQUIRED=1
    fi
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
    reconcile_boot_line \
        '^[[:space:]]*enable_uart=' \
        'enable_uart=1'

    if ! sudo cmp -s \
        "${REPO_ROOT}/deploy/udev/70-e87canbus-can.rules" \
        /etc/udev/rules.d/70-e87canbus-can.rules; then
        sudo install -o root -g root -m 0644 \
            "${REPO_ROOT}/deploy/udev/70-e87canbus-can.rules" \
            /etc/udev/rules.d/70-e87canbus-can.rules
        REBOOT_REQUIRED=1
    fi

    if sudo grep -Eq '(^|[[:space:]])console=(serial0|ttyAMA0|ttyS0),' "${CMDLINE_FILE}"; then
        sudo sed -E -i \
            's/(^|[[:space:]])console=(serial0|ttyAMA0|ttyS0),[^[:space:]]+//g; s/[[:space:]]+/ /g; s/^ //; s/ $//' \
            "${CMDLINE_FILE}"
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

    if ! sudo cmp -s \
        "${REPO_ROOT}/deploy/udev/71-e87canbus-kiosk-input.rules" \
        /etc/udev/rules.d/71-e87canbus-kiosk-input.rules; then
        sudo install -o root -g root -m 0644 \
            "${REPO_ROOT}/deploy/udev/71-e87canbus-kiosk-input.rules" \
            /etc/udev/rules.d/71-e87canbus-kiosk-input.rules
        REBOOT_REQUIRED=1
    fi

    for param in quiet splash loglevel=3 logo.nologo vt.global_cursor_default=0; do
        if ! grep -qw "${param}" "${CMDLINE_FILE}"; then
            sudo sed -i "s/$/ ${param}/" "${CMDLINE_FILE}"
            REBOOT_REQUIRED=1
        fi
    done

    splash_setting_count="$(sudo grep -Ec '^[[:space:]]*disable_splash=' "${CONFIG_FILE}" || true)"
    splash_disabled_count="$(sudo grep -Fxc 'disable_splash=1' "${CONFIG_FILE}" || true)"
    if [[ "${splash_setting_count}" -ne 1 || "${splash_disabled_count}" -ne 1 ]]; then
        sudo sed -E -i '/^[[:space:]]*disable_splash=/d' "${CONFIG_FILE}"
        echo 'disable_splash=1' | sudo tee -a "${CONFIG_FILE}" >/dev/null
        REBOOT_REQUIRED=1
    fi

    # Display hardware access takes effect after reboot, so reconcile it before the early gate.
    for display_group in video render input; do
        if ! id -nG "${USER}" | tr ' ' '\n' | grep -Fxq "${display_group}"; then
            sudo usermod -aG video,render,input "${USER}"
            REBOOT_REQUIRED=1
            break
        fi
    done
elif [[ -e /etc/udev/rules.d/71-e87canbus-kiosk-input.rules ]]; then
    sudo rm /etc/udev/rules.d/71-e87canbus-kiosk-input.rules
    REBOOT_REQUIRED=1
fi

# ---------------------------------------------------------------------------
# Reboot gate — apply boot config and stable interface naming before doing the
# expensive application sync and frontend build.
# ---------------------------------------------------------------------------
if [[ "${REBOOT_REQUIRED}" -eq 1 ]]; then
    echo
    echo "Boot configuration changed; reboot is required before physical I/O is ready."
    if [[ "${REBOOT_REQUESTED}" -eq 1 ]]; then
        sudo reboot
    else
        echo "Reboot, then run this script again to build and install the application:"
        echo "  sudo reboot"
        echo "  cd ${REPO_ROOT} && ./scripts/setup_pi.sh --profile ${DEPLOYMENT_PROFILE}"
        if [[ -n "${HOTSPOT_PASSWORD_FILE}" ]]; then
            echo "  Include --hotspot-password-file again on that post-reboot run."
        fi
    fi
    exit 0
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

if [[ "${DEPLOYMENT_PROFILE}" != "simulator" ]] \
    && ! id -nG e87canbus | tr ' ' '\n' | grep -Fxq dialout; then
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
for obsolete_can_service in \
    e87canbus-can0.service \
    e87canbus-can1.service \
    e87canbus-can2.service; do
    sudo systemctl disable --now "${obsolete_can_service}" 2>/dev/null || true
    sudo rm -f "/etc/systemd/system/${obsolete_can_service}"
done
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

# ---------------------------------------------------------------------------
# Coordinator-panel hotspot (physical profiles only)
# ---------------------------------------------------------------------------
if [[ "${DEPLOYMENT_PROFILE}" != "simulator" ]]; then
    echo "Configuring the coordinator-panel hotspot..."

    HOTSPOT_EXISTS=0
    if sudo nmcli --get-values connection.uuid connection show id "${HOTSPOT_CONNECTION}" >/dev/null 2>&1; then
        HOTSPOT_EXISTS=1
    fi

    HOTSPOT_PASSWORD=""
    REPLACE_HOTSPOT_PASSWORD=0
    if [[ -n "${HOTSPOT_PASSWORD_FILE}" ]]; then
        if [[ ! -f "${HOTSPOT_PASSWORD_FILE}" || ! -r "${HOTSPOT_PASSWORD_FILE}" ]]; then
            echo "Hotspot password file is not a readable regular file: ${HOTSPOT_PASSWORD_FILE}" >&2
            exit 2
        fi
        HOTSPOT_PASSWORD="$(< "${HOTSPOT_PASSWORD_FILE}")"
        REPLACE_HOTSPOT_PASSWORD=1
    elif [[ "${HOTSPOT_EXISTS}" -eq 0 ]] || ! sudo nmcli --show-secrets \
        --get-values 802-11-wireless-security.psk \
        connection show id "${HOTSPOT_CONNECTION}" 2>/dev/null | grep -q .; then
        read -r -s -p "Hotspot WPA password: " HOTSPOT_PASSWORD
        echo
        read -r -s -p "Confirm hotspot WPA password: " HOTSPOT_PASSWORD_CONFIRM
        echo
        if [[ "${HOTSPOT_PASSWORD}" != "${HOTSPOT_PASSWORD_CONFIRM}" ]]; then
            echo "Hotspot passwords do not match" >&2
            exit 2
        fi
        unset HOTSPOT_PASSWORD_CONFIRM
        REPLACE_HOTSPOT_PASSWORD=1
    fi

    if [[ "${REPLACE_HOTSPOT_PASSWORD}" -eq 1 ]]; then
        if [[ "${HOTSPOT_PASSWORD}" == *$'\n'* ]]; then
            echo "Hotspot password must be a single line" >&2
            exit 2
        fi
        HOTSPOT_PASSWORD_LENGTH="${#HOTSPOT_PASSWORD}"
        if (( HOTSPOT_PASSWORD_LENGTH < 8 || HOTSPOT_PASSWORD_LENGTH > 63 )); then
            if (( HOTSPOT_PASSWORD_LENGTH != 64 )) \
                || [[ ! "${HOTSPOT_PASSWORD}" =~ ^[[:xdigit:]]{64}$ ]]; then
                echo "Hotspot password must be 8-63 characters or exactly 64 hexadecimal digits" >&2
                exit 2
            fi
        fi
    fi

    if [[ "${HOTSPOT_EXISTS}" -eq 0 ]]; then
        sudo nmcli connection add \
            type wifi ifname wlan0 con-name "${HOTSPOT_CONNECTION}" ssid "${HOTSPOT_SSID}" \
            >/dev/null
    fi

    # The shared method provides addressing and DHCP. Policy routing blackholes forwarded client
    # traffic, so the access point cannot use an Ethernet default route as an internet uplink.
    sudo nmcli connection modify id "${HOTSPOT_CONNECTION}" \
        connection.interface-name wlan0 \
        connection.autoconnect no \
        connection.permissions "" \
        802-11-wireless.mode ap \
        802-11-wireless.ssid "${HOTSPOT_SSID}" \
        802-11-wireless-security.key-mgmt wpa-psk \
        ipv4.method shared \
        ipv4.never-default yes \
        ipv4.routes "0.0.0.0/0 type=blackhole table=500" \
        ipv4.routing-rules "priority 100 iif wlan0 table 500" \
        ipv6.method disabled

    if [[ "${REPLACE_HOTSPOT_PASSWORD}" -eq 1 ]]; then
        # Feed the secret to nmcli's editor over stdin and disable its command-history file. The
        # secret never appears in argv, the environment, setup output, or a repository file.
        printf 'set 802-11-wireless-security.psk\n%s\nsave\nquit\n' "${HOTSPOT_PASSWORD}" \
            | sudo env XDG_CACHE_HOME=/dev/null \
                nmcli connection edit id "${HOTSPOT_CONNECTION}" >/dev/null
        HOTSPOT_PASSWORD=""
        unset HOTSPOT_PASSWORD

        # The editor exits successfully even when it rejects the property, so confirm the
        # secret landed rather than reporting a hotspot that cannot authenticate anyone.
        if ! sudo nmcli --show-secrets --get-values 802-11-wireless-security.psk \
            connection show id "${HOTSPOT_CONNECTION}" | grep -q .; then
            echo "Failed to store the hotspot WPA password" >&2
            exit 1
        fi
    fi

    # The runtime gets only four exact root operations. Both sudoers and the helper reject extra
    # arguments; the helper contains no caller-controlled command, connection, or interface.
    sudo /usr/sbin/visudo -cf "${REPO_ROOT}/deploy/sudoers/e87canbus-hotspot" >/dev/null
    sudo install -d -o root -g root -m 0755 /usr/local/libexec
    sudo install -o root -g root -m 0755 \
        "${REPO_ROOT}/deploy/bin/e87canbus-hotspot" \
        /usr/local/libexec/e87canbus-hotspot
    sudo install -o root -g root -m 0440 \
        "${REPO_ROOT}/deploy/sudoers/e87canbus-hotspot" \
        /etc/sudoers.d/e87canbus-hotspot

    HOTSPOT_UUID="$(sudo nmcli --get-values connection.uuid connection show id "${HOTSPOT_CONNECTION}")"
    if sudo nmcli --terse --fields UUID connection show --active | grep -Fxq "${HOTSPOT_UUID}"; then
        sudo nmcli connection down id "${HOTSPOT_CONNECTION}" >/dev/null
    fi
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
    sudo systemctl enable --now e87canbus-kiosk.service
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
fi

if [[ "${DEPLOYMENT_PROFILE}" != "simulator" ]]; then
    echo "Starting the boot-managed kcan, ptcan, and fcan services..."
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
    echo "  ip -details link show kcan"
    echo "  ip -details link show ptcan"
    echo "  ip -details link show fcan"
    echo "  candump kcan"
    echo "  candump ptcan"
    echo "  candump fcan"
    echo "  test -e /dev/serial0 && id e87canbus"
    echo "  sudo -u e87canbus sudo -n /usr/local/libexec/e87canbus-hotspot state"
fi
echo
if [[ "${KIOSK_MODE}" == "desktop" ]]; then
    echo "Kiosk: autostart installed for '${USER}'. Chromium opens at /car on next desktop login."
else
    echo "Kiosk: cage service installed for '${USER}'. Chromium opens at /car on next boot."
fi
