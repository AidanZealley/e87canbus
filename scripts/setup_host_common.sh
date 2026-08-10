#!/usr/bin/env bash

# Shared mechanics for the two fixed Raspberry Pi host installers. Role policy stays in the
# coordinator and console entry points so their installed surfaces remain easy to audit.

require_deployment_checkout() {
    local repo_root="$1"

    if [[ "${EUID}" -eq 0 ]]; then
        echo "Run this script as the checkout owner, not as root; it uses sudo for system changes." >&2
        exit 1
    fi
    if [[ "${repo_root}" != "/opt/e87canbus" ]]; then
        echo "This deployment script expects the repository at /opt/e87canbus." >&2
        echo "Current checkout: ${repo_root}" >&2
        exit 1
    fi
}

find_boot_files() {
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
}

require_pi_4() {
    local role="$1"
    if [[ ! -r /proc/device-tree/model ]]; then
        echo "Cannot identify the Raspberry Pi model; the ${role} requires a Raspberry Pi 4 Model B." >&2
        exit 1
    fi

    local pi_model
    pi_model="$(tr -d '\0' < /proc/device-tree/model)"
    if [[ "${pi_model}" != "Raspberry Pi 4 Model B"* ]]; then
        echo "Unsupported ${role}: ${pi_model}" >&2
        echo "The ${role} requires a Raspberry Pi 4 Model B." >&2
        exit 1
    fi
    echo "Validated ${role}: ${pi_model}"
}

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

install_host_build_tools() {
    echo "Installing host build packages..."
    sudo apt-get update
    sudo apt-get install -y \
        build-essential can-utils curl network-manager nodejs npm python3 python3-pip python3-venv

    if ! command -v uv >/dev/null 2>&1; then
        sudo python3 -m pip install --break-system-packages uv
    fi
    if ! command -v pnpm >/dev/null 2>&1; then
        sudo npm install --global pnpm@9.15.1
    fi
}

sync_host_application() {
    local repo_root="$1"
    echo "Synchronizing Python dependencies..."
    uv sync --frozen --python /usr/bin/python3
    (
        cd "${repo_root}/frontend"
        pnpm install --frozen-lockfile
    )
}

install_service_account() {
    local repo_root="$1"
    if ! getent group e87canbus >/dev/null; then
        sudo groupadd --system e87canbus
    fi
    if ! id e87canbus >/dev/null 2>&1; then
        sudo useradd --system --gid e87canbus --home-dir /var/lib/e87canbus \
            --create-home --shell /usr/sbin/nologin e87canbus
    fi

    sudo chgrp -R e87canbus "${repo_root}"
    sudo chmod -R g+rX "${repo_root}"
    sudo install -d -o e87canbus -g e87canbus -m 0750 /var/lib/e87canbus /etc/e87canbus
}

configure_console_link() {
    local address="$1"
    local rule_priority="$2"
    local connection="e87canbus-console-link"

    if ! ip link show eth0 >/dev/null 2>&1; then
        echo "Ethernet interface eth0 is unavailable; leaving application services stopped." >&2
        exit 1
    fi
    if ! sudo nmcli --get-values connection.uuid connection show id "${connection}" >/dev/null 2>&1; then
        sudo nmcli connection add type ethernet ifname eth0 con-name "${connection}" >/dev/null
    fi
    # The ingress policy blackhole leaves local traffic reachable but prevents this link from
    # forwarding into any other coordinator or console interface.
    sudo nmcli connection modify id "${connection}" \
        connection.interface-name eth0 \
        connection.autoconnect yes \
        ipv4.method manual \
        ipv4.addresses "${address}" \
        ipv4.gateway "" \
        ipv4.dns "" \
        ipv4.ignore-auto-dns yes \
        ipv4.never-default yes \
        ipv4.routes "0.0.0.0/0 type=blackhole table=501" \
        ipv4.routing-rules "priority ${rule_priority} iif eth0 table 501" \
        ipv6.method disabled
    sudo nmcli connection up id "${connection}" >/dev/null
}

remove_units() {
    local unit
    for unit in "$@"; do
        sudo systemctl disable --now "${unit}" 2>/dev/null || true
        sudo rm -f "/etc/systemd/system/${unit}"
    done
}
