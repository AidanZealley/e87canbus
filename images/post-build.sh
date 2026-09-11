#!/bin/sh

set -eu

target=$1
origin="${target}/usr/share/rpi-image-gen/origin"

if [ -z "${SOURCE_DATE_EPOCH:-}" ]; then
    echo "post-build: SOURCE_DATE_EPOCH is absent from the generated build configuration" >&2
    exit 1
fi

if ! grep -Fqx "# SOURCE_DATE_EPOCH: ${SOURCE_DATE_EPOCH}" "${origin}"; then
    echo "post-build: generated package snapshot origin does not match SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH}" >&2
    exit 1
fi
