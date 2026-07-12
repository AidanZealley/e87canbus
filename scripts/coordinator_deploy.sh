#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET=""
TAIL_LOGS=0

usage() {
  echo "usage: $0 <user@host> [--tail-logs]" >&2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tail-logs)
      TAIL_LOGS=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [[ -n "${TARGET}" ]]; then
        usage
        exit 2
      fi
      TARGET="$1"
      shift
      ;;
  esac
done

if [[ -z "${TARGET}" ]]; then
  usage
  exit 2
fi

cd "${REPO_ROOT}"
uv run pytest
uv run ruff check .
uv run mypy coordinator/src/e87canbus

ssh "${TARGET}" "sudo mkdir -p /opt/e87canbus && sudo chown \$(id -un):\$(id -gn) /opt/e87canbus"
rsync -az --delete \
  --exclude ".git/" \
  --exclude ".mypy_cache/" \
  --exclude ".pytest_cache/" \
  --exclude ".ruff_cache/" \
  --exclude ".venv/" \
  --exclude ".pio/" \
  --exclude "__pycache__/" \
  "${REPO_ROOT}/" "${TARGET}:/opt/e87canbus/"

ssh "${TARGET}" "cd /opt/e87canbus && uv sync && sudo systemctl restart e87canbus.service && sudo systemctl status e87canbus.service --no-pager"

if [[ "${TAIL_LOGS}" -eq 1 ]]; then
  ssh -t "${TARGET}" "journalctl -u e87canbus.service -f"
fi
