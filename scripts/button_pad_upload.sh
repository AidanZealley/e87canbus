#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UPLOAD_PORT="${UPLOAD_PORT:-}"

cd "${REPO_ROOT}/devices/button-pad"
UPLOAD_ARGS=(--target upload)
if [[ -n "${UPLOAD_PORT}" ]]; then
    UPLOAD_ARGS+=(--upload-port "${UPLOAD_PORT}")
fi

pio run "${UPLOAD_ARGS[@]}"
