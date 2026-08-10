#!/usr/bin/env bash
set -euo pipefail

CHROMIUM=""
for binary in chromium-browser chromium /snap/bin/chromium; do
    if command -v "${binary}" >/dev/null 2>&1; then
        CHROMIUM="${binary}"
        break
    fi
done
if [[ -z "${CHROMIUM}" ]]; then
    echo "e87canbus-console-kiosk: chromium not found" >&2
    exit 1
fi

until curl -sf http://127.0.0.1:8000/health/live >/dev/null 2>&1; do
    sleep 1
done

exec "${CHROMIUM}" \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --no-first-run \
    --disable-translate \
    --disable-features=TranslateUI \
    --ozone-platform-hint=auto \
    http://127.0.0.1:8000/
