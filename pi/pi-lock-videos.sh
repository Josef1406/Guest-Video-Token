#!/usr/bin/env bash
# Videos schreibschützen. Wirkt nur auf ext4 (chattr +i).
# Auf exFAT sind chmod/chattr wirkungslos -> siehe README (GADGET_RO=1).
set -euo pipefail
ROOT="${1:-/srv/videos}"
if [[ ! -d "$ROOT" ]]; then
  echo "Verzeichnis $ROOT existiert nicht" >&2; exit 1
fi
echo "-> chmod 0444 in $ROOT"
find "$ROOT" -type f -exec chmod 0444 {} +
find "$ROOT" -type d -exec chmod 0555 {} +
echo "-> chattr +i (nur ext4)"
find "$ROOT" -type f -exec chattr +i {} + 2>/dev/null || \
  echo "Hinweis: chattr nicht anwendbar (evtl. exFAT)."
echo "Fertig."
