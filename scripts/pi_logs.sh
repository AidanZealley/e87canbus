#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-}"

if [[ -z "${TARGET}" ]]; then
  echo "usage: $0 <user@host> [journalctl args...]" >&2
  exit 2
fi

shift
ssh "${TARGET}" journalctl -u e87canbus.service "$@" --no-pager
