#!/usr/bin/env bash
set -euo pipefail

REPO_URL=""
BRANCH="main"
CAN_INTERFACE="can0"
BITRATE="500000"
OSCILLATOR="12000000"
INTERRUPT="25"
SPI_MAX_FREQUENCY="2000000"
REPO_DIR="/opt/e87canbus"
SERVICE_USER="pi"

usage() {
  cat >&2 <<EOF
usage: $0 --repo-url <url> [options]

options:
  --branch <name>                 default: main
  --can-interface <name>          default: can0
  --bitrate <value>               default: 500000
  --oscillator <hz>               default: 12000000
  --interrupt <bcm>               default: 25
  --spi-max-frequency <hz>        default: 2000000
  --repo-dir <path>               default: /opt/e87canbus
  --service-user <user>           default: pi
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-url) REPO_URL="$2"; shift 2 ;;
    --branch) BRANCH="$2"; shift 2 ;;
    --can-interface) CAN_INTERFACE="$2"; shift 2 ;;
    --bitrate) BITRATE="$2"; shift 2 ;;
    --oscillator) OSCILLATOR="$2"; shift 2 ;;
    --interrupt) INTERRUPT="$2"; shift 2 ;;
    --spi-max-frequency) SPI_MAX_FREQUENCY="$2"; shift 2 ;;
    --repo-dir) REPO_DIR="$2"; shift 2 ;;
    --service-user) SERVICE_USER="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
done

if [[ -z "${REPO_URL}" ]]; then
  usage
  exit 2
fi

if [[ "${EUID}" -ne 0 ]]; then
  echo "run this script with sudo" >&2
  exit 1
fi

apt-get update
apt-get install -y git curl ca-certificates python3 python3-venv can-utils rsync

if ! command -v uv >/dev/null 2>&1; then
  sudo -u "${SERVICE_USER}" sh -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
fi

UV_PATH="$(sudo -u "${SERVICE_USER}" sh -lc 'command -v uv')"
CONFIG_TXT="/boot/config.txt"
if [[ -f /boot/firmware/config.txt ]]; then
  CONFIG_TXT="/boot/firmware/config.txt"
fi

ensure_line() {
  local line="$1"
  local file="$2"
  local tmp_file
  tmp_file="$(mktemp)"
  grep -Fxv "${line}" "${file}" > "${tmp_file}" || true
  cat "${tmp_file}" > "${file}"
  rm -f "${tmp_file}"
  printf '%s\n' "${line}" >> "${file}"
}

ensure_line "dtparam=spi=on" "${CONFIG_TXT}"
ensure_line "dtoverlay=mcp2515-${CAN_INTERFACE},oscillator=${OSCILLATOR},interrupt=${INTERRUPT},spimaxfrequency=${SPI_MAX_FREQUENCY}" "${CONFIG_TXT}"

mkdir -p "$(dirname "${REPO_DIR}")"
if [[ -d "${REPO_DIR}/.git" ]]; then
  sudo -u "${SERVICE_USER}" git -C "${REPO_DIR}" fetch origin "${BRANCH}"
  sudo -u "${SERVICE_USER}" git -C "${REPO_DIR}" checkout "${BRANCH}"
  sudo -u "${SERVICE_USER}" git -C "${REPO_DIR}" pull --ff-only origin "${BRANCH}"
else
  rm -rf "${REPO_DIR}"
  sudo -u "${SERVICE_USER}" git clone --branch "${BRANCH}" "${REPO_URL}" "${REPO_DIR}"
fi
chown -R "${SERVICE_USER}:${SERVICE_USER}" "${REPO_DIR}"

sudo -u "${SERVICE_USER}" sh -lc "cd '${REPO_DIR}' && '${UV_PATH}' sync"

cat >/usr/local/bin/e87canbus-can-up <<EOF
#!/usr/bin/env bash
set -euo pipefail
ip link set "${CAN_INTERFACE}" down || true
ip link set "${CAN_INTERFACE}" type can bitrate "${BITRATE}" restart-ms 100
ip link set "${CAN_INTERFACE}" up
ip -details link show "${CAN_INTERFACE}"
EOF
chmod 0755 /usr/local/bin/e87canbus-can-up

install -m 0644 "${REPO_DIR}/deploy/systemd/e87canbus.service" /etc/systemd/system/e87canbus.service
sed -i "s#^User=.*#User=${SERVICE_USER}#" /etc/systemd/system/e87canbus.service
sed -i "s#^WorkingDirectory=.*#WorkingDirectory=${REPO_DIR}#" /etc/systemd/system/e87canbus.service
sed -i "s#^ExecStart=.*#ExecStart=${UV_PATH} run e87canbus-bench-pingpong --interface ${CAN_INTERFACE}#" /etc/systemd/system/e87canbus.service
systemctl daemon-reload
systemctl enable e87canbus.service

echo "Bootstrap complete. Reboot is required before ${CAN_INTERFACE} will use the MCP2515 overlay."
