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
    [ "${IGconf_image_boot_part_size}" = 2G ]
    [ "${IGconf_image_root_part_size}" = 4G ]
    install -d -m 0755 "${target}/etc/systemd/system" \
        "${target}/etc/systemd/system/e87canbus-controller.service.d" \
        "${target}/etc/udev/rules.d" "${target}/usr/local/libexec" \
        "${target}/etc/sudoers.d" "${target}/etc/e87canbus" \
        "${target}/etc/sysctl.d" "${target}/usr/share/e87canbus"

    for unit in \
        e87canbus-controller.service \
        e87canbus-kcan.service \
        e87canbus-ptcan.service \
        e87canbus-fcan.service \
        e87canbus-firewall.service \
        e87canbus-dnsmasq.service \
        e87canbus-nginx.service
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
    install -m 0755 "${deploy}/bin/e87canbus-firewall" \
        "${target}/usr/local/libexec/e87canbus-firewall"
    install -m 0440 "${deploy}/sudoers/e87canbus-hotspot" \
        "${target}/etc/sudoers.d/e87canbus-hotspot"
    install -m 0640 "${deploy}/systemd/controller.env.example" \
        "${target}/etc/e87canbus/controller.env"
    install -m 0644 "${deploy}/network/dnsmasq.conf" \
        "${target}/etc/e87canbus/dnsmasq.conf"
    install -m 0644 "${deploy}/network/nftables.conf" \
        "${target}/etc/e87canbus/nftables.conf"
    install -m 0644 "${deploy}/network/90-e87canbus-no-forwarding.conf" \
        "${target}/etc/sysctl.d/90-e87canbus-no-forwarding.conf"
    install -m 0644 "${deploy}/nginx/e87canbus.conf" \
        "${target}/etc/e87canbus/nginx.conf"
    cat >"${target}/usr/share/e87canbus/image-contract.json" <<EOF
{"architecture":"arm64","boot_partition_size_bytes":$((2 * 1024 * 1024 * 1024)),"format_version":1,"os_release":"Raspberry Pi OS Lite Trixie","provisioning_interface_version":1,"raspberry_pi_model":"Raspberry Pi 4 Model B","role":"coordinator","root_filesystem_size_bytes":$((4 * 1024 * 1024 * 1024))}
EOF
}

configure_role() {
    chroot "${target}" chown root:e87canbus /etc/e87canbus/controller.env
    chroot "${target}" usermod -aG dialout e87canbus
    chroot "${target}" /usr/sbin/visudo -cf /etc/sudoers.d/e87canbus-hotspot >/dev/null

}

configure_boot
install_runtime_assets
configure_role
