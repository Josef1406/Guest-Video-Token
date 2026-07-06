#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/srv/videos}"
if [[ ! -d "$ROOT" ]]; then
  echo "Verzeichnis $ROOT existiert nicht" >&2; exit 1
fi
echo "-> chattr -i in $ROOT"
find "$ROOT" -type f -exec chattr -i {} + 2>/dev/null || true
echo "-> chmod 0644 / 0755"
find "$ROOT" -type d -exec chmod 0755 {} +
find "$ROOT" -type f -exec chmod 0644 {} +
echo "Fertig."
