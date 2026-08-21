#!/bin/sh

set -eu

target=$1
deploy=$2
role_dir=${0%/*}

configure_boot() {
    sed -E -i \
        -e '/^[[:space:]]*dtparam=spi=/d' \
        -e '/^[[:space:]]*dtoverlay=uart3([,[:space:]]|$)/d' \
        -e '/^[[:space:]]*dtoverlay=spi1-(1|2|3)cs([,[:space:]]|$)/d' \
        -e '/^[[:space:]]*dtoverlay=mcp2515-can0([,[:space:]]|$)/d' \
        -e '/^[[:space:]]*dtoverlay=mcp2515,.*spi(0-0|1-1|1-2)([,[:space:]]|$)/d' \
        -e '/^[[:space:]]*dtoverlay=i2c0([,[:space:]]|$)/d' \
        -e '/^[[:space:]]*enable_uart=/d' \
        "${target}/boot/firmware/config.txt"
    cat >>"${target}/boot/firmware/config.txt" <<'EOF'

# E87 coordinator hardware is fixed to the Raspberry Pi 4 three-CAN stack.
[pi4]
dtparam=spi=on
dtoverlay=uart3
dtoverlay=spi1-3cs
dtoverlay=mcp2515-can0,oscillator=12000000,interrupt=25,spimaxfrequency=2000000
dtoverlay=mcp2515,spi1-1,oscillator=16000000,interrupt=22,speed=10000000
dtoverlay=mcp2515,spi1-2,oscillator=16000000,interrupt=13,speed=10000000
enable_uart=1

[all]
EOF
    sed -E -i \
        's/(^|[[:space:]])console=(serial0|ttyAMA0|ttyS0),[^[:space:]]+//g; s/[[:space:]]+/ /g; s/^ //; s/ $//' \
        "${target}/boot/firmware/cmdline.txt"
}

install_runtime_assets() {
    install -d -m 0755 "${target}/etc/systemd/system" \
        "${target}/etc/systemd/system/e87canbus-controller.service.d" \
        "${target}/etc/udev/rules.d" "${target}/usr/local/libexec" \
        "${target}/etc/sudoers.d"

    for unit in \
        e87canbus-controller.service \
        e87canbus-kcan.service \
        e87canbus-ptcan.service \
        e87canbus-fcan.service \
        e87canbus-coordinator-hotspot-proxy.service \
        e87canbus-coordinator-hotspot-proxy.socket \
        e87canbus-coordinator-console-proxy.service \
        e87canbus-coordinator-console-proxy.socket
    do
        install -m 0644 "${deploy}/systemd/${unit}" \
            "${target}/etc/systemd/system/${unit}"
    done

    install -m 0644 "${role_dir}/e87canbus-controller-provisioning.conf" \
        "${target}/etc/systemd/system/e87canbus-controller.service.d/provisioning.conf"
    install -m 0644 "${deploy}/udev/70-e87canbus-coordinator-can.rules" \
        "${target}/etc/udev/rules.d/70-e87canbus-coordinator-can.rules"
    install -m 0755 "${deploy}/bin/e87canbus-hotspot" \
        "${target}/usr/local/libexec/e87canbus-hotspot"
    install -m 0440 "${deploy}/sudoers/e87canbus-hotspot" \
        "${target}/etc/sudoers.d/e87canbus-hotspot"
    install -m 0640 "${deploy}/systemd/controller.env.example" \
        "${target}/etc/e87canbus/controller.env"
}

configure_role() {
    chroot "${target}" chown root:e87canbus /etc/e87canbus/controller.env
    chroot "${target}" usermod -aG dialout e87canbus
    chroot "${target}" /usr/sbin/visudo -cf /etc/sudoers.d/e87canbus-hotspot >/dev/null

    if grep -Eq '^[#[:space:]]*host-name=' "${target}/etc/avahi/avahi-daemon.conf"; then
        sed -E -i '0,/^[#[:space:]]*host-name=.*/s//host-name=e87/' \
            "${target}/etc/avahi/avahi-daemon.conf"
    else
        sed -i '/^\[server\]$/a host-name=e87' "${target}/etc/avahi/avahi-daemon.conf"
    fi
}

configure_boot
install_runtime_assets
configure_role
