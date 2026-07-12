#!/usr/bin/env bash
set -euo pipefail

CAN_INTERFACE="${CAN_INTERFACE:-vcan0}"

sudo ip link set "${CAN_INTERFACE}" down || true
sudo ip link delete "${CAN_INTERFACE}" type vcan || true
