#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPECTED_ROOT="/opt/e87canbus"
CONFIG_FILE=""
REBOOT_REQUESTED=0
REBOOT_REQUIRED=0

if [[ "${EUID}" -eq 0 ]]; then
    echo "Run this script as the checkout owner, not as root; it uses sudo for system changes." >&2
    exit 1
fi

if [[ "${REPO_ROOT}" != "${EXPECTED_ROOT}" ]]; then
    echo "This deployment script expects the repository at ${EXPECTED_ROOT}." >&2
    echo "Current checkout: ${REPO_ROOT}" >&2
    exit 1
fi

for argument in "$@"; do
    case "${argument}" in
        --reboot) REBOOT_REQUESTED=1 ;;
        *) echo "Usage: $0 [--reboot]" >&2; exit 2 ;;
    esac
done

if [[ -f /boot/firmware/config.txt ]]; then
    CONFIG_FILE=/boot/firmware/config.txt
elif [[ -f /boot/config.txt ]]; then
    CONFIG_FILE=/boot/config.txt
else
    echo "Could not find Raspberry Pi boot config.txt." >&2
    exit 1
fi

echo "Installing Pi packages..."
sudo apt-get update
sudo apt-get install -y can-utils build-essential python3 python3-pip python3-venv nodejs npm

if ! command -v uv >/dev/null 2>&1; then
    echo "Installing uv..."
    sudo python3 -m pip install --break-system-packages uv
fi

if ! command -v pnpm >/dev/null 2>&1; then
    echo "Installing pnpm..."
    sudo npm install --global pnpm@9.15.1
fi

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
sudo install -d -o e87canbus -g e87canbus -m 0750 /var/lib/e87canbus /etc/e87canbus
sudo install -o root -g root -m 0644 \
    "${REPO_ROOT}/deploy/systemd/e87canbus-can0.service" \
    /etc/systemd/system/e87canbus-can0.service
sudo install -o root -g root -m 0644 \
    "${REPO_ROOT}/deploy/systemd/e87canbus-controller.service" \
    /etc/systemd/system/e87canbus-controller.service
KIOSK_USER="${USER}"
KIOSK_HOME="$(getent passwd "${KIOSK_USER}" | cut -d: -f6)"
sed \
    -e "s|User=pi|User=${KIOSK_USER}|g" \
    -e "s|/home/pi/.Xauthority|${KIOSK_HOME}/.Xauthority|g" \
    "${REPO_ROOT}/deploy/systemd/e87canbus-kiosk.service" \
    | sudo tee /etc/systemd/system/e87canbus-kiosk.service >/dev/null
sudo chmod 0644 /etc/systemd/system/e87canbus-kiosk.service
sudo chown root:root /etc/systemd/system/e87canbus-kiosk.service
sudo install -o root -g e87canbus -m 0640 \
    "${REPO_ROOT}/deploy/systemd/controller.env.example" \
    /etc/e87canbus/controller.env
sudo systemctl daemon-reload
sudo systemctl enable e87canbus-can0.service
sudo systemctl enable e87canbus-controller.service
sudo systemctl enable e87canbus-kiosk.service

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

if ! ip link show can0 >/dev/null 2>&1; then
    echo "can0 is not available; leaving the service stopped." >&2
    echo "Check the HAT wiring/overlay, then reboot if the boot config changed." >&2
    exit 1
fi

echo "Starting the boot-managed can0 service..."
sudo systemctl start e87canbus-can0.service
sudo systemctl restart e87canbus-controller.service

echo
echo "Pi setup complete. Check:"
echo "  systemctl status e87canbus-controller.service"
echo "  journalctl -u e87canbus-controller.service -f"
echo "  candump can0"
echo
echo "Kiosk: e87canbus-kiosk.service installed for user '${KIOSK_USER}'."
echo "  It starts automatically after the controller on next graphical boot."
