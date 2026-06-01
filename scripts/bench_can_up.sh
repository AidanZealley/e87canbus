#!/usr/bin/env bash
set -euo pipefail

CAN_INTERFACE="${CAN_INTERFACE:-can0}"
BITRATE="${BITRATE:-500000}"

sudo ip link set "${CAN_INTERFACE}" down || true
sudo ip link set "${CAN_INTERFACE}" type can bitrate "${BITRATE}" restart-ms 100
sudo ip link set "${CAN_INTERFACE}" up
ip -details link show "${CAN_INTERFACE}"
