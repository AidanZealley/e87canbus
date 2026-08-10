#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/setup_host_common.sh
source "${REPO_ROOT}/scripts/setup_host_common.sh"

CONFIG_FILE=""
CMDLINE_FILE=""
REBOOT_REQUESTED=0
REBOOT_REQUIRED=0
DEPLOYMENT_PROFILE="car"
HOTSPOT_PASSWORD_FILE=""
HOTSPOT_CONNECTION="e87canbus-hotspot"
HOTSPOT_ADDRESS="10.42.0.1/24"
HOTSPOT_HOSTNAME="e87"
CAN_INTERFACES=(kcan ptcan fcan)
CAN_SERVICES=(e87canbus-kcan.service e87canbus-ptcan.service e87canbus-fcan.service)

require_deployment_checkout "${REPO_ROOT}"

while [[ "$#" -gt 0 ]]; do
    case "$1" in
        --profile)
            [[ "$#" -ge 2 ]] || { echo "--profile requires car, bench, or simulator" >&2; exit 2; }
            DEPLOYMENT_PROFILE="$2"
            shift 2
            ;;
        --hotspot-password-file)
            [[ "$#" -ge 2 ]] || { echo "--hotspot-password-file requires a readable file" >&2; exit 2; }
            HOTSPOT_PASSWORD_FILE="$2"
            shift 2
            ;;
        --reboot)
            REBOOT_REQUESTED=1
            shift
            ;;
        *)
            echo "Usage: $0 [--profile car|bench|simulator] [--hotspot-password-file PATH] [--reboot]" >&2
            exit 2
            ;;
    esac
done

case "${DEPLOYMENT_PROFILE}" in car|bench|simulator) ;; *)
    echo "Unsupported deployment profile: ${DEPLOYMENT_PROFILE}" >&2
    exit 2
esac
if [[ "${DEPLOYMENT_PROFILE}" == "simulator" && -n "${HOTSPOT_PASSWORD_FILE}" ]]; then
    echo "--hotspot-password-file is only valid for car and bench" >&2
    exit 2
fi
echo "Coordinator controller profile: ${DEPLOYMENT_PROFILE}"

if [[ "${DEPLOYMENT_PROFILE}" != "simulator" ]]; then
    require_pi_4 "physical coordinator"
    find_boot_files
    sudo cp -n "${CONFIG_FILE}" "${CONFIG_FILE}.e87canbus-before-setup" || true
    sudo cp -n "${CMDLINE_FILE}" "${CMDLINE_FILE}.e87canbus-before-setup" || true

    echo "Configuring the coordinator three-CAN stack and panel UART..."
    reconcile_boot_line '^[[:space:]]*dtparam=spi=' 'dtparam=spi=on'
    reconcile_boot_line '^[[:space:]]*dtoverlay=uart3([,[:space:]]|$)' 'dtoverlay=uart3'
    reconcile_boot_line '^[[:space:]]*dtoverlay=spi1-(1|2|3)cs([,[:space:]]|$)' 'dtoverlay=spi1-3cs'
    reconcile_boot_line \
        '^[[:space:]]*dtoverlay=(mcp2515-can0([,[:space:]]|$)|mcp2515,.*spi0-0([,[:space:]]|$))' \
        'dtoverlay=mcp2515-can0,oscillator=12000000,interrupt=25,spimaxfrequency=2000000'
    reconcile_boot_line \
        '^[[:space:]]*dtoverlay=mcp2515,.*spi1-1([,[:space:]]|$)' \
        'dtoverlay=mcp2515,spi1-1,oscillator=16000000,interrupt=22,speed=10000000'
    reconcile_boot_line \
        '^[[:space:]]*dtoverlay=mcp2515,.*spi1-2([,[:space:]]|$)' \
        'dtoverlay=mcp2515,spi1-2,oscillator=16000000,interrupt=13,speed=10000000'
    reconcile_boot_line '^[[:space:]]*enable_uart=' 'enable_uart=1'

    if sudo grep -Eq '^[[:space:]]*dtoverlay=i2c0([,[:space:]]|$)' "${CONFIG_FILE}"; then
        sudo sed -E -i '/^[[:space:]]*dtoverlay=i2c0([,[:space:]]|$)/d' "${CONFIG_FILE}"
        REBOOT_REQUIRED=1
    fi
    if sudo grep -Eq '(^|[[:space:]])console=(serial0|ttyAMA0|ttyS0),' "${CMDLINE_FILE}"; then
        sudo sed -E -i \
            's/(^|[[:space:]])console=(serial0|ttyAMA0|ttyS0),[^[:space:]]+//g; s/[[:space:]]+/ /g; s/^ //; s/ $//' \
            "${CMDLINE_FILE}"
        REBOOT_REQUIRED=1
    fi

    if ! sudo cmp -s "${REPO_ROOT}/deploy/udev/70-e87canbus-coordinator-can.rules" \
        /etc/udev/rules.d/70-e87canbus-coordinator-can.rules; then
        sudo install -o root -g root -m 0644 \
            "${REPO_ROOT}/deploy/udev/70-e87canbus-coordinator-can.rules" \
            /etc/udev/rules.d/70-e87canbus-coordinator-can.rules
        REBOOT_REQUIRED=1
    fi
    sudo rm -f /etc/udev/rules.d/70-e87canbus-can.rules \
        /etc/udev/rules.d/70-e87canbus-console-can.rules

    if [[ "${REBOOT_REQUIRED}" -eq 1 ]]; then
        echo "Boot configuration changed; reboot, then rerun setup before services are installed."
        if [[ "${REBOOT_REQUESTED}" -eq 1 ]]; then
            sudo reboot
        else
            echo "  sudo reboot"
            echo "  cd ${REPO_ROOT} && ./scripts/setup_coordinator.sh --profile ${DEPLOYMENT_PROFILE}"
        fi
        exit 0
    fi

    [[ -e /dev/ttyAMA3 ]] || {
        echo "Panel UART /dev/ttyAMA3 is unavailable; leaving the controller uninstalled." >&2
        exit 1
    }
fi

sudo systemctl stop e87canbus-controller.service 2>/dev/null || true
install_host_build_tools
sync_host_application "${REPO_ROOT}"
echo "Building only the coordinator frontend..."
(cd "${REPO_ROOT}/frontend" && pnpm --filter ./apps/coordinator build)
install_service_account "${REPO_ROOT}"
if [[ "${DEPLOYMENT_PROFILE}" != "simulator" ]] \
    && ! id -nG e87canbus | tr ' ' '\n' | grep -Fxq dialout; then
    sudo usermod -aG dialout e87canbus
fi

echo "Removing obsolete combined and console deployment files..."
remove_units \
    e87canbus-can0.service e87canbus-can1.service e87canbus-can2.service \
    e87canbus-kiosk.service e87canbus-console.service e87canbus-console-kcan.service \
    e87canbus-web-proxy.service e87canbus-web-proxy.socket
sudo rm -f /usr/local/bin/e87canbus-kiosk /usr/local/bin/e87canbus-console-kiosk \
    /etc/udev/rules.d/71-e87canbus-kiosk-input.rules /etc/e87canbus/console.env
rm -f "${HOME}/.config/autostart/e87canbus-kiosk.desktop" \
    "${HOME}/.config/autostart/e87canbus-console-kiosk.desktop"

sudo install -o root -g root -m 0644 \
    "${REPO_ROOT}/deploy/systemd/e87canbus-controller.service" \
    /etc/systemd/system/e87canbus-controller.service
sudo install -o root -g e87canbus -m 0640 \
    "${REPO_ROOT}/deploy/systemd/controller.env.example" /etc/e87canbus/controller.env
sudo sed -i "s/^E87CANBUS_PROFILE=.*/E87CANBUS_PROFILE=${DEPLOYMENT_PROFILE}/" \
    /etc/e87canbus/controller.env

for database_file in /var/lib/e87canbus/application.sqlite3 \
    /var/lib/e87canbus/application.sqlite3-wal /var/lib/e87canbus/application.sqlite3-shm; do
    if [[ -e "${database_file}" ]]; then
        sudo chown e87canbus:e87canbus "${database_file}"
        sudo chmod 0640 "${database_file}"
    fi
done

if [[ "${DEPLOYMENT_PROFILE}" == "simulator" ]]; then
    remove_units "${CAN_SERVICES[@]}" \
        e87canbus-coordinator-hotspot-proxy.service e87canbus-coordinator-hotspot-proxy.socket \
        e87canbus-coordinator-console-proxy.service e87canbus-coordinator-console-proxy.socket
else
    echo "Configuring the fixed coordinator-to-console Ethernet link..."
    configure_console_link "10.43.0.1/30" 101

    echo "Installing coordinator CAN and constrained proxy units..."
    for unit in "${CAN_SERVICES[@]}" \
        e87canbus-coordinator-hotspot-proxy.service \
        e87canbus-coordinator-hotspot-proxy.socket \
        e87canbus-coordinator-console-proxy.service \
        e87canbus-coordinator-console-proxy.socket; do
        sudo install -o root -g root -m 0644 "${REPO_ROOT}/deploy/systemd/${unit}" \
            "/etc/systemd/system/${unit}"
    done

    echo "Configuring the coordinator-panel hotspot..."
    sudo apt-get install -y avahi-daemon iw
    HOTSPOT_EXISTS=0
    if sudo nmcli --get-values connection.uuid connection show id "${HOTSPOT_CONNECTION}" >/dev/null 2>&1; then
        HOTSPOT_EXISTS=1
    fi
    HOTSPOT_PASSWORD=""
    REPLACE_HOTSPOT_PASSWORD=0
    if [[ -n "${HOTSPOT_PASSWORD_FILE}" ]]; then
        [[ -f "${HOTSPOT_PASSWORD_FILE}" && -r "${HOTSPOT_PASSWORD_FILE}" ]] || {
            echo "Hotspot password file is not a readable regular file: ${HOTSPOT_PASSWORD_FILE}" >&2
            exit 2
        }
        HOTSPOT_PASSWORD="$(< "${HOTSPOT_PASSWORD_FILE}")"
        REPLACE_HOTSPOT_PASSWORD=1
    elif [[ "${HOTSPOT_EXISTS}" -eq 0 ]] || ! sudo nmcli --show-secrets \
        --get-values 802-11-wireless-security.psk connection show id "${HOTSPOT_CONNECTION}" \
        2>/dev/null | grep -q .; then
        read -r -s -p "Hotspot WPA password: " HOTSPOT_PASSWORD
        echo
        read -r -s -p "Confirm hotspot WPA password: " HOTSPOT_PASSWORD_CONFIRM
        echo
        [[ "${HOTSPOT_PASSWORD}" == "${HOTSPOT_PASSWORD_CONFIRM}" ]] || {
            echo "Hotspot passwords do not match" >&2; exit 2;
        }
        unset HOTSPOT_PASSWORD_CONFIRM
        REPLACE_HOTSPOT_PASSWORD=1
    fi
    if [[ "${REPLACE_HOTSPOT_PASSWORD}" -eq 1 ]]; then
        [[ "${HOTSPOT_PASSWORD}" != *$'\n'* ]] || { echo "Hotspot password must be a single line" >&2; exit 2; }
        HOTSPOT_PASSWORD_LENGTH="${#HOTSPOT_PASSWORD}"
        if (( HOTSPOT_PASSWORD_LENGTH < 8 || HOTSPOT_PASSWORD_LENGTH > 63 )) \
            && { (( HOTSPOT_PASSWORD_LENGTH != 64 )) || [[ ! "${HOTSPOT_PASSWORD}" =~ ^[[:xdigit:]]{64}$ ]]; }; then
            echo "Hotspot password must be 8-63 characters or exactly 64 hexadecimal digits" >&2
            exit 2
        fi
    fi
    if [[ "${HOTSPOT_EXISTS}" -eq 0 ]]; then
        sudo nmcli connection add type wifi ifname wlan0 con-name "${HOTSPOT_CONNECTION}" \
            ssid e87canbus >/dev/null
    fi
    sudo nmcli connection modify id "${HOTSPOT_CONNECTION}" \
        connection.interface-name wlan0 connection.autoconnect no connection.permissions "" \
        802-11-wireless.mode ap 802-11-wireless.ssid e87canbus \
        802-11-wireless-security.key-mgmt wpa-psk ipv4.method shared \
        ipv4.addresses "${HOTSPOT_ADDRESS}" ipv4.never-default yes \
        ipv4.routes "0.0.0.0/0 type=blackhole table=500" \
        ipv4.routing-rules "priority 100 iif wlan0 table 500" ipv6.method disabled
    if sudo grep -Eq '^[#[:space:]]*host-name=' /etc/avahi/avahi-daemon.conf; then
        sudo sed -E -i \
            "0,/^[#[:space:]]*host-name=.*/s//host-name=${HOTSPOT_HOSTNAME}/" \
            /etc/avahi/avahi-daemon.conf
    else
        sudo sed -i "/^\[server\]$/a host-name=${HOTSPOT_HOSTNAME}" \
            /etc/avahi/avahi-daemon.conf
    fi
    sudo systemctl restart avahi-daemon.service
    if [[ "${REPLACE_HOTSPOT_PASSWORD}" -eq 1 ]]; then
        printf 'set 802-11-wireless-security.psk\n%s\nsave\nquit\n' "${HOTSPOT_PASSWORD}" \
            | sudo env XDG_CACHE_HOME=/dev/null nmcli connection edit id "${HOTSPOT_CONNECTION}" >/dev/null
        HOTSPOT_PASSWORD=""
        unset HOTSPOT_PASSWORD
        sudo nmcli --show-secrets --get-values 802-11-wireless-security.psk \
            connection show id "${HOTSPOT_CONNECTION}" | grep -q . || {
            echo "Failed to store the hotspot WPA password" >&2; exit 1;
        }
    fi
    sudo /usr/sbin/visudo -cf "${REPO_ROOT}/deploy/sudoers/e87canbus-hotspot" >/dev/null
    sudo install -d -o root -g root -m 0755 /usr/local/libexec
    sudo install -o root -g root -m 0755 "${REPO_ROOT}/deploy/bin/e87canbus-hotspot" \
        /usr/local/libexec/e87canbus-hotspot
    sudo install -o root -g root -m 0440 "${REPO_ROOT}/deploy/sudoers/e87canbus-hotspot" \
        /etc/sudoers.d/e87canbus-hotspot
    HOTSPOT_UUID="$(sudo nmcli --get-values connection.uuid connection show id "${HOTSPOT_CONNECTION}")"
    if sudo nmcli --terse --fields UUID connection show --active | grep -Fxq "${HOTSPOT_UUID}"; then
        sudo nmcli connection down id "${HOTSPOT_CONNECTION}" >/dev/null
    fi

    EXPECTED_SPI_PARENTS=(spi0.0 spi1.1 spi1.2)
    for index in "${!CAN_INTERFACES[@]}"; do
        interface="${CAN_INTERFACES[${index}]}"
        ip link show "${interface}" >/dev/null 2>&1 || {
            echo "${interface} is unavailable; leaving the controller stopped." >&2; exit 1;
        }
        device_path="$(readlink -f "/sys/class/net/${interface}/device" || true)"
        actual_spi_parent="${device_path##*/}"
        expected_spi_parent="${EXPECTED_SPI_PARENTS[${index}]}"
        [[ "${actual_spi_parent}" == "${expected_spi_parent}" ]] || {
            echo "${interface} maps to ${actual_spi_parent:-unknown}, expected ${expected_spi_parent}; leaving the controller stopped." >&2
            exit 1
        }
    done
fi

sudo systemctl daemon-reload
if [[ "${DEPLOYMENT_PROFILE}" != "simulator" ]]; then
    sudo systemctl enable "${CAN_SERVICES[@]}"
    sudo systemctl start "${CAN_SERVICES[@]}"
    sudo systemctl enable --now e87canbus-coordinator-hotspot-proxy.socket \
        e87canbus-coordinator-console-proxy.socket
fi
sudo systemctl enable e87canbus-controller.service
sudo systemctl restart e87canbus-controller.service

echo "Coordinator setup complete (${DEPLOYMENT_PROFILE})."
echo "  systemctl status e87canbus-controller.service"
echo "  coordinator app: http://127.0.0.1:8000/"
if [[ "${DEPLOYMENT_PROFILE}" != "simulator" ]]; then
    echo "  console-link proxy: http://10.43.0.1/"
    echo "  hotspot proxy: http://10.42.0.1/"
fi
