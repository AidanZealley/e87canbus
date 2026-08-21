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
        -e '/^[[:space:]]*disable_splash=/d' \
        "${target}/boot/firmware/config.txt"
    cat >>"${target}/boot/firmware/config.txt" <<'EOF'

# E87 console hardware is fixed to the first controller on the Raspberry Pi 4 CAN HAT+.
[pi4]
dtparam=spi=on
dtoverlay=spi1-3cs
dtoverlay=mcp2515,spi1-1,oscillator=16000000,interrupt=22,speed=10000000
disable_splash=1

[all]
EOF

    for parameter in quiet splash loglevel=3 logo.nologo vt.global_cursor_default=0
    do
        if ! grep -qw "${parameter}" "${target}/boot/firmware/cmdline.txt"; then
            sed -i "s/$/ ${parameter}/" "${target}/boot/firmware/cmdline.txt"
        fi
    done
}

install_runtime_assets() {
    install -d -m 0755 \
        "${target}/etc/systemd/system" \
        "${target}/etc/systemd/system/e87canbus-console.service.d" \
        "${target}/etc/systemd/system/e87canbus-console-kiosk.service.d" \
        "${target}/etc/udev/rules.d" \
        "${target}/usr/local/bin"

    for unit in \
        e87canbus-console-kcan.service \
        e87canbus-console.service \
        e87canbus-console-kiosk.service
    do
        install -m 0644 "${deploy}/systemd/${unit}" \
            "${target}/etc/systemd/system/${unit}"
    done

    install -m 0644 "${role_dir}/e87canbus-console-provisioning.conf" \
        "${target}/etc/systemd/system/e87canbus-console.service.d/provisioning.conf"
    install -m 0644 "${role_dir}/e87canbus-console-kiosk-provisioning.conf" \
        "${target}/etc/systemd/system/e87canbus-console-kiosk.service.d/provisioning.conf"
    install -m 0644 "${deploy}/udev/70-e87canbus-console-can.rules" \
        "${target}/etc/udev/rules.d/70-e87canbus-console-can.rules"
    install -m 0644 "${deploy}/udev/71-e87canbus-kiosk-input.rules" \
        "${target}/etc/udev/rules.d/71-e87canbus-kiosk-input.rules"
    install -m 0755 "${deploy}/kiosk/start-console-kiosk.sh" \
        "${target}/usr/local/bin/e87canbus-console-kiosk"
    install -m 0640 "${deploy}/systemd/console.env.example" \
        "${target}/etc/e87canbus/console.env"
    chroot "${target}" chown root:e87canbus /etc/e87canbus/console.env
}

configure_boot
install_runtime_assets
