#!/usr/bin/env bash
set -euo pipefail

CAN_INTERFACE="${CAN_INTERFACE:-can0}"

sudo ip link set "${CAN_INTERFACE}" down
