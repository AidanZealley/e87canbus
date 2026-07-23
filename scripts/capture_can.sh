#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CAN_INTERFACE="${CAN_INTERFACE:-can0}"
EXPECTED_BITRATE="${EXPECTED_BITRATE:-100000}"
CAPTURE_ROOT="${CAPTURE_ROOT:-${HOME}/e87canbus-captures}"
CONTROLLER_SERVICE="e87canbus-controller.service"
CAN_SERVICE="e87canbus-can0.service"
SESSION_LABEL="${1:-capture}"

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

command -v candump >/dev/null 2>&1 ||
    fail "candump is not installed. Run scripts/setup_pi.sh to install can-utils."
command -v ip >/dev/null 2>&1 || fail "the ip command is not installed."
command -v systemctl >/dev/null 2>&1 || fail "systemd is required."
command -v sudo >/dev/null 2>&1 || fail "sudo is required."

if [[ ! "${SESSION_LABEL}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
    fail "the optional label may contain only letters, numbers, dots, underscores, and hyphens."
fi

echo "Preparing a read-only CAN capture on ${CAN_INTERFACE}."
echo "The coordinator will be stopped temporarily; Ctrl-C will end the capture and restore it."
sudo -v

CONTROLLER_WAS_ACTIVE=0
CAN_SERVICE_WAS_ACTIVE=0
CAPTURE_STARTED=0

if systemctl is-active --quiet "${CONTROLLER_SERVICE}"; then
    CONTROLLER_WAS_ACTIVE=1
fi
if systemctl is-active --quiet "${CAN_SERVICE}"; then
    CAN_SERVICE_WAS_ACTIVE=1
fi

restore_state() {
    local exit_status=$?
    trap - EXIT INT TERM

    if [[ "${CAPTURE_STARTED}" -eq 1 ]]; then
        ip -details -statistics link show dev "${CAN_INTERFACE}" \
            >"${SESSION_DIR}/interface-after.txt" 2>&1 || true
        date --iso-8601=seconds >"${SESSION_DIR}/finished-at.txt" 2>/dev/null ||
            date >"${SESSION_DIR}/finished-at.txt"
    fi

    echo
    echo "Restoring the previous service state..."
    if [[ "${CONTROLLER_WAS_ACTIVE}" -eq 1 ]]; then
        if ! sudo systemctl start "${CONTROLLER_SERVICE}"; then
            echo "WARNING: could not restart ${CONTROLLER_SERVICE}; check it with:" >&2
            echo "  sudo systemctl status ${CONTROLLER_SERVICE}" >&2
            exit_status=1
        fi
    fi
    if [[ "${CAN_SERVICE_WAS_ACTIVE}" -eq 0 ]] &&
       systemctl is-active --quiet "${CAN_SERVICE}"; then
        if ! sudo systemctl stop "${CAN_SERVICE}"; then
            echo "WARNING: could not restore ${CAN_SERVICE} to its previous stopped state." >&2
            exit_status=1
        fi
    fi

    if [[ "${CAPTURE_STARTED}" -eq 1 ]]; then
        echo "Capture saved at:"
        echo "  ${SESSION_DIR}"
    fi
    exit "${exit_status}"
}
trap restore_state EXIT INT TERM

if [[ "${CONTROLLER_WAS_ACTIVE}" -eq 1 ]]; then
    echo "Stopping ${CONTROLLER_SERVICE} to prevent application CAN transmissions..."
    sudo systemctl stop "${CONTROLLER_SERVICE}"
fi

if ! ip link show dev "${CAN_INTERFACE}" >/dev/null 2>&1 ||
   ! ip link show dev "${CAN_INTERFACE}" | grep -qE '[<,]UP[,>]'; then
    echo "Starting ${CAN_SERVICE}..."
    sudo systemctl start "${CAN_SERVICE}"
fi

INTERFACE_DETAILS="$(ip -details link show dev "${CAN_INTERFACE}" 2>/dev/null)" ||
    fail "${CAN_INTERFACE} does not exist after starting ${CAN_SERVICE}."
grep -qE '[<,]UP[,>]' <<<"${INTERFACE_DETAILS}" ||
    fail "${CAN_INTERFACE} is not up."
grep -q "bitrate ${EXPECTED_BITRATE}" <<<"${INTERFACE_DETAILS}" ||
    fail "${CAN_INTERFACE} is not configured at the expected ${EXPECTED_BITRATE} bit/s."
if grep -q "listen-only on" <<<"${INTERFACE_DETAILS}"; then
    fail "${CAN_INTERFACE} is in listen-only mode and cannot ACK the device's frames."
fi

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
install -d -m 0750 "${CAPTURE_ROOT}"
SESSION_DIR="${CAPTURE_ROOT}/${TIMESTAMP}-${SESSION_LABEL}"
install -d -m 0750 "${SESSION_DIR}"
CAPTURE_STARTED=1

{
    echo "label=${SESSION_LABEL}"
    echo "interface=${CAN_INTERFACE}"
    echo "expected_bitrate=${EXPECTED_BITRATE}"
    echo "hostname=$(hostname)"
    echo "repository=${REPO_ROOT}"
    echo "controller_service_was_active=${CONTROLLER_WAS_ACTIVE}"
    echo "can_service_was_active=${CAN_SERVICE_WAS_ACTIVE}"
    echo "started_at=$(date --iso-8601=seconds 2>/dev/null || date)"
    if [[ -r /etc/e87canbus/controller.env ]]; then
        grep '^E87CANBUS_PROFILE=' /etc/e87canbus/controller.env || true
    fi
} >"${SESSION_DIR}/session.txt"

ip -details -statistics link show dev "${CAN_INTERFACE}" \
    >"${SESSION_DIR}/interface-before.txt"

echo
echo "Ready. The interface is UP at ${EXPECTED_BITRATE} bit/s in normal ACK-capable mode."
echo "Power or operate the connected device now."
echo "Press Ctrl-C once when finished."
echo
echo "Writing raw frames to:"
echo "  ${SESSION_DIR}/candump.log"
echo

# -L gives absolute timestamps in the standard candump log format accepted by canplayer.
candump -L "${CAN_INTERFACE}" | tee "${SESSION_DIR}/candump.log"
