#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UPLOAD_PORT="${UPLOAD_PORT:-}"

cd "${REPO_ROOT}/devices/coordinator-panel"
UPLOAD_ARGS=(-e qtpy_rp2040 --target upload)
if [[ -n "${UPLOAD_PORT}" ]]; then
    UPLOAD_ARGS+=(--upload-port "${UPLOAD_PORT}")
fi

pio run "${UPLOAD_ARGS[@]}"
