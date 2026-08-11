#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/setup_host_common.sh
source "${REPO_ROOT}/scripts/setup_host_common.sh"

CONFIG_FILE=""
CMDLINE_FILE=""
REBOOT_REQUESTED=0
REBOOT_REQUIRED=0
KIOSK_MODE="headless"
DEPLOYMENT_PROFILE="car"
CONSOLE_CAN_LISTEN_ONLY="on"

require_deployment_checkout "${REPO_ROOT}"
while [[ "$#" -gt 0 ]]; do
    case "$1" in
        --profile)
            [[ "$#" -ge 2 ]] || { echo "--profile requires car or bench" >&2; exit 2; }
            DEPLOYMENT_PROFILE="$2"
            shift 2
            ;;
        --reboot) REBOOT_REQUESTED=1; shift ;;
        *) echo "Usage: $0 [--profile car|bench] [--reboot]" >&2; exit 2 ;;
    esac
done
case "${DEPLOYMENT_PROFILE}" in
    car) ;;
    bench) CONSOLE_CAN_LISTEN_ONLY="off" ;;
    *) echo "Unsupported console profile: ${DEPLOYMENT_PROFILE}" >&2; exit 2 ;;
esac
echo "Console CAN profile: ${DEPLOYMENT_PROFILE} (listen-only ${CONSOLE_CAN_LISTEN_ONLY})"
require_pi_4 "console"
find_boot_files

for dm in lightdm gdm3 gdm sddm lxdm wdm; do
    if dpkg-query -W -f='${Status}' "${dm}" 2>/dev/null | grep -q "install ok installed"; then
        KIOSK_MODE="desktop"
        break
    fi
done
echo "Console kiosk mode: ${KIOSK_MODE}"

sudo cp -n "${CONFIG_FILE}" "${CONFIG_FILE}.e87canbus-before-setup" || true
sudo cp -n "${CMDLINE_FILE}" "${CMDLINE_FILE}.e87canbus-before-setup" || true
echo "Configuring only the first 2-CH CAN HAT+ controller..."
reconcile_boot_line '^[[:space:]]*dtparam=spi=' 'dtparam=spi=on'
reconcile_boot_line '^[[:space:]]*dtoverlay=spi1-(1|2|3)cs([,[:space:]]|$)' 'dtoverlay=spi1-3cs'
reconcile_boot_line \
    '^[[:space:]]*dtoverlay=mcp2515,.*spi1-1([,[:space:]]|$)' \
    'dtoverlay=mcp2515,spi1-1,oscillator=16000000,interrupt=22,speed=10000000'

# Remove coordinator-only controllers and UART. The HAT+'s spi1.2 channel deliberately has no
# overlay, stable name or service, so it cannot be opened accidentally by this deployment.
for pattern in \
    '^[[:space:]]*dtoverlay=(mcp2515-can0([,[:space:]]|$)|mcp2515,.*spi0-0([,[:space:]]|$))' \
    '^[[:space:]]*dtoverlay=mcp2515,.*spi1-2([,[:space:]]|$)' \
    '^[[:space:]]*dtoverlay=i2c0([,[:space:]]|$)' \
    '^[[:space:]]*dtoverlay=uart3([,[:space:]]|$)' \
    '^[[:space:]]*enable_uart='; do
    if sudo grep -Eq "${pattern}" "${CONFIG_FILE}"; then
        sudo sed -E -i "/${pattern}/d" "${CONFIG_FILE}"
        REBOOT_REQUIRED=1
    fi
done

if ! sudo cmp -s "${REPO_ROOT}/deploy/udev/70-e87canbus-console-can.rules" \
    /etc/udev/rules.d/70-e87canbus-console-can.rules; then
    sudo install -o root -g root -m 0644 \
        "${REPO_ROOT}/deploy/udev/70-e87canbus-console-can.rules" \
        /etc/udev/rules.d/70-e87canbus-console-can.rules
    REBOOT_REQUIRED=1
fi
sudo rm -f /etc/udev/rules.d/70-e87canbus-can.rules \
    /etc/udev/rules.d/70-e87canbus-coordinator-can.rules

if ! sudo cmp -s "${REPO_ROOT}/deploy/udev/71-e87canbus-kiosk-input.rules" \
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
reconcile_boot_line '^[[:space:]]*disable_splash=' 'disable_splash=1'
for display_group in video render input; do
    if ! id -nG "${USER}" | tr ' ' '\n' | grep -Fxq "${display_group}"; then
        sudo usermod -aG video,render,input "${USER}"
        REBOOT_REQUIRED=1
        break
    fi
done

if [[ "${REBOOT_REQUIRED}" -eq 1 ]]; then
    echo "Boot configuration changed; reboot, then rerun setup before services are installed."
    if [[ "${REBOOT_REQUESTED}" -eq 1 ]]; then
        sudo reboot
    else
        echo "  sudo reboot"
        echo "  cd ${REPO_ROOT} && ./scripts/setup_console.sh --profile ${DEPLOYMENT_PROFILE}"
    fi
    exit 0
fi

sudo systemctl stop e87canbus-console.service 2>/dev/null || true
install_host_build_tools
if [[ "${KIOSK_MODE}" == "headless" ]]; then
    CHROMIUM_PACKAGE=""
    for candidate in chromium-browser chromium; do
        if apt-cache show "${candidate}" >/dev/null 2>&1; then
            CHROMIUM_PACKAGE="${candidate}"
            break
        fi
    done
    [[ -n "${CHROMIUM_PACKAGE}" ]] || {
        echo "No Chromium apt package is available; leaving the kiosk uninstalled." >&2
        exit 1
    }
    sudo apt-get install -y "${CHROMIUM_PACKAGE}" cage plymouth
fi
sync_host_application "${REPO_ROOT}"
echo "Building only the console frontend for the fixed coordinator origin..."
(cd "${REPO_ROOT}/frontend" && \
    VITE_COORDINATOR_ORIGIN=http://10.43.0.1 pnpm --filter ./apps/console build)
install_service_account "${REPO_ROOT}"

echo "Removing obsolete combined and coordinator deployment files..."
remove_units \
    e87canbus-can0.service e87canbus-can1.service e87canbus-can2.service \
    e87canbus-kcan.service e87canbus-ptcan.service e87canbus-fcan.service \
    e87canbus-controller.service e87canbus-web-proxy.service e87canbus-web-proxy.socket \
    e87canbus-coordinator-hotspot-proxy.service e87canbus-coordinator-hotspot-proxy.socket \
    e87canbus-coordinator-console-proxy.service e87canbus-coordinator-console-proxy.socket
sudo rm -f /usr/local/bin/e87canbus-kiosk /usr/local/libexec/e87canbus-hotspot \
    /etc/sudoers.d/e87canbus-hotspot /etc/e87canbus/controller.env
rm -f "${HOME}/.config/autostart/e87canbus-kiosk.desktop"
if sudo nmcli --get-values connection.uuid connection show id e87canbus-hotspot >/dev/null 2>&1; then
    sudo nmcli connection delete id e87canbus-hotspot >/dev/null
fi

echo "Configuring the fixed console-to-coordinator Ethernet link..."
configure_console_link "10.43.0.2/30" 101

device_path="$(readlink -f /sys/class/net/kcan/device 2>/dev/null || true)"
actual_spi_parent="${device_path##*/}"
if ! ip link show kcan >/dev/null 2>&1 || [[ "${actual_spi_parent}" != "spi1.1" ]]; then
    echo "kcan must map to spi1.1; found ${actual_spi_parent:-no interface}. Leaving console services stopped." >&2
    exit 1
fi

sudo install -o root -g root -m 0644 \
    "${REPO_ROOT}/deploy/systemd/e87canbus-console-kcan.service" \
    /etc/systemd/system/e87canbus-console-kcan.service
sudo install -o root -g root -m 0644 \
    "${REPO_ROOT}/deploy/systemd/e87canbus-console.service" \
    /etc/systemd/system/e87canbus-console.service
sudo install -o root -g e87canbus -m 0640 \
    "${REPO_ROOT}/deploy/systemd/console.env.example" /etc/e87canbus/console.env
sudo sed -i \
    "s/^E87CANBUS_CONSOLE_CAN_LISTEN_ONLY=.*/E87CANBUS_CONSOLE_CAN_LISTEN_ONLY=${CONSOLE_CAN_LISTEN_ONLY}/" \
    /etc/e87canbus/console.env

sudo install -o root -g root -m 0755 "${REPO_ROOT}/deploy/kiosk/start-console-kiosk.sh" \
    /usr/local/bin/e87canbus-console-kiosk
if [[ "${KIOSK_MODE}" == "desktop" ]]; then
    mkdir -p "${HOME}/.config/autostart"
    cp "${REPO_ROOT}/deploy/kiosk/e87canbus-console-kiosk.desktop" \
        "${HOME}/.config/autostart/e87canbus-console-kiosk.desktop"
    remove_units e87canbus-console-kiosk.service
else
    sed "s|KIOSK_USER_PLACEHOLDER|${USER}|g" \
        "${REPO_ROOT}/deploy/systemd/e87canbus-console-kiosk.service" \
        | sudo tee /etc/systemd/system/e87canbus-console-kiosk.service >/dev/null
    sudo chmod 0644 /etc/systemd/system/e87canbus-console-kiosk.service
    sudo chown root:root /etc/systemd/system/e87canbus-console-kiosk.service
    rm -f "${HOME}/.config/autostart/e87canbus-console-kiosk.desktop"
fi

sudo systemctl daemon-reload
sudo systemctl enable e87canbus-console-kcan.service e87canbus-console.service
sudo systemctl restart e87canbus-console-kcan.service
sudo systemctl restart e87canbus-console.service
if [[ "${KIOSK_MODE}" == "headless" ]]; then
    sudo systemctl enable --now e87canbus-console-kiosk.service
fi

echo "Console setup complete (${DEPLOYMENT_PROFILE}; listen-only ${CONSOLE_CAN_LISTEN_ONLY})."
echo "  systemctl status e87canbus-console.service"
echo "  ip -details link show kcan"
echo "  local console: http://127.0.0.1:8000/"
echo "  coordinator link: http://10.43.0.1/"
