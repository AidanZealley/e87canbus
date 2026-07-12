#!/usr/bin/env bash
set -euo pipefail

CAN_INTERFACE="${CAN_INTERFACE:-vcan0}"

sudo modprobe vcan

if ! ip link show "${CAN_INTERFACE}" >/dev/null 2>&1; then
  sudo ip link add dev "${CAN_INTERFACE}" type vcan
fi

sudo ip link set "${CAN_INTERFACE}" up
ip -details link show "${CAN_INTERFACE}"
