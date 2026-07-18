#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPECTED_ROOT="/opt/e87canbus"
CONFIG_FILE=""
CMDLINE_FILE=""
REBOOT_REQUESTED=0
REBOOT_REQUIRED=0
DEPLOYMENT_PROFILE="car"

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
        *) echo "Usage: $0 [--profile car|bench|simulator] [--reboot]" >&2; exit 2 ;;
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

PACKAGES="can-utils build-essential python3 python3-pip python3-venv nodejs npm curl"

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
# SPI and Waveshare MCP2515 overlay
# ---------------------------------------------------------------------------
if [[ "${DEPLOYMENT_PROFILE}" != "simulator" ]]; then
    echo "Configuring SPI and the Waveshare MCP2515 interface..."
    sudo cp -n "${CONFIG_FILE}" "${CONFIG_FILE}.e87canbus-before-setup" || true

    if ! sudo grep -Eq '^[[:space:]]*dtparam=spi=on([[:space:]]|$)' "${CONFIG_FILE}"; then
        echo 'dtparam=spi=on' | sudo tee -a "${CONFIG_FILE}" >/dev/null
        REBOOT_REQUIRED=1
    fi

    OVERLAY='dtoverlay=mcp2515-can0,oscillator=12000000,interrupt=25,spimaxfrequency=2000000'
    if ! sudo grep -Fxq "${OVERLAY}" "${CONFIG_FILE}"; then
        sudo sed -i '/^[[:space:]]*dtoverlay=mcp2515-can0,/d' "${CONFIG_FILE}"
        echo "${OVERLAY}" | sudo tee -a "${CONFIG_FILE}" >/dev/null
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
sudo install -o root -g root -m 0644 \
    "${REPO_ROOT}/deploy/systemd/e87canbus-can0.service" \
    /etc/systemd/system/e87canbus-can0.service
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
    sudo usermod -aG video,render,input "${USER}"
    REBOOT_REQUIRED=1

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
    sudo systemctl disable e87canbus-can0.service 2>/dev/null || true
else
    sudo systemctl enable e87canbus-can0.service
fi
sudo systemctl enable e87canbus-controller.service
if [[ "${KIOSK_MODE}" == "headless" ]]; then
    sudo systemctl enable e87canbus-kiosk.service
fi

# ---------------------------------------------------------------------------
# Reboot gate — boot config or group changes require a reboot before services
# can be started. Services are already enabled above; they start on next boot.
# ---------------------------------------------------------------------------
if [[ "${REBOOT_REQUIRED}" -eq 1 ]]; then
    echo
    echo "Boot configuration changed; reboot is required before can0 can appear."
    if [[ "${REBOOT_REQUESTED}" -eq 1 ]]; then
        sudo reboot
    else
        echo "Reboot, then run this script again to start the service:"
        echo "  sudo reboot"
        echo "  cd ${REPO_ROOT} && ./scripts/setup_pi.sh"
    fi
    exit 0
fi

if [[ "${DEPLOYMENT_PROFILE}" != "simulator" ]]; then
    REQUIRED_CAN_INTERFACES=(can0)
    if [[ "${DEPLOYMENT_PROFILE}" == "car" ]]; then
        REQUIRED_CAN_INTERFACES+=(can1 can2)
    fi
    for interface in "${REQUIRED_CAN_INTERFACES[@]}"; do
        if ! ip link show "${interface}" >/dev/null 2>&1; then
            echo "${interface} is not available; leaving the controller stopped." >&2
            echo "Check the CAN hardware and interface units, then rerun setup." >&2
            sudo systemctl stop e87canbus-controller.service 2>/dev/null || true
            exit 1
        fi
    done
fi

if [[ "${DEPLOYMENT_PROFILE}" != "simulator" ]]; then
    echo "Starting the boot-managed can0 service..."
    sudo systemctl start e87canbus-can0.service
fi
sudo systemctl restart e87canbus-controller.service

echo
echo "Pi setup complete. Check:"
echo "  installed profile: ${DEPLOYMENT_PROFILE}"
echo "  systemctl status e87canbus-controller.service"
echo "  journalctl -u e87canbus-controller.service -f"
echo "  candump can0"
echo
if [[ "${KIOSK_MODE}" == "desktop" ]]; then
    echo "Kiosk: autostart installed for '${USER}'. Chromium opens at /car on next desktop login."
else
    echo "Kiosk: cage service installed for '${USER}'. Chromium opens at /car on next boot."
fi
