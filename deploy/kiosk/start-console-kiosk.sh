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

# The unit's RuntimeDirectory provides this tmpfs path. The installation CA stays in the
# kiosk user's ~/.pki/nssdb, which Chromium reads regardless of --user-data-dir.
exec "${CHROMIUM}" \
    --kiosk \
    --user-data-dir=/run/e87canbus-kiosk/profile \
    --disk-cache-dir=/run/e87canbus-kiosk/cache \
    --disk-cache-size=33554432 \
    --noerrdialogs \
    --disable-infobars \
    --no-first-run \
    --disable-translate \
    --disable-features=TranslateUI \
    --ozone-platform-hint=auto \
    http://127.0.0.1:8000/
