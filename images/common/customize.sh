#!/bin/sh

set -eu

target=$1
deploy=$2

install -d -m 0755 \
    "${target}/etc/ssh/sshd_config.d" \
    "${target}/etc/systemd/system" \
    "${target}/usr/local/libexec"
install -m 0755 "${deploy}/bin/e87canbus-provision" \
    "${target}/usr/local/libexec/e87canbus-provision"
install -m 0644 "${deploy}/systemd/e87canbus-provision.service" \
    "${target}/etc/systemd/system/e87canbus-provision.service"
install -m 0644 "${deploy}/systemd/e87canbus-role.target" \
    "${target}/etc/systemd/system/e87canbus-role.target"
install -m 0644 "${deploy}/ssh/90-e87canbus.conf" \
    "${target}/etc/ssh/sshd_config.d/90-e87canbus.conf"

# An absent machine-id makes systemd create a unique persistent ID on the first boot.
rm -f "${target}/etc/machine-id" "${target}/var/lib/dbus/machine-id"
rm -f "${target}"/etc/ssh/ssh_host_*
rm -f "${target}/etc/hostname"
sed -i '/^[^#]*[[:space:]]127[.]0[.]1[.]1[[:space:]]/d' "${target}/etc/hosts"
