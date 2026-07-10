#!/usr/bin/env bash
# test-usb.sh — USB-Massenspeicher-Modus im Wartungsmodus testen
#
# Nutzung (per SSH auf dem Pi):
#   sudo bash pi/test-usb.sh rw        # USB-Modus, beschreibbar (Admin)
#   sudo bash pi/test-usb.sh ro        # USB-Modus, read-only (Kunde)
#   sudo bash pi/test-usb.sh gpio      # aktuellen GPIO 16 Zustand anzeigen
#   sudo bash pi/test-usb.sh back      # zurück in AP-Modus
#   sudo bash pi/test-usb.sh status    # aktueller Modus / ro-Flag
#
# Funktioniert auch im Wartungsmodus, weil switch-mode.sh keine
# ConditionPathExists-Sperre hat. Der GPIO-Daemon ist im Wartungsmodus
# deaktiviert, daher setzen wir das ro-Flag hier manuell.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Bitte mit sudo ausführen." >&2
  exit 1
fi

SWITCH="${SWITCH:-/usr/local/sbin/switch-mode}"
RO_FILE=/var/lib/video-token/gadget_ro
mkdir -p "$(dirname "$RO_FILE")"

read_gpio16() {
  if command -v pinctrl >/dev/null 2>&1; then
    pinctrl get 16 | awk '{print $0}'
  else
    echo "pinctrl nicht installiert"
  fi
}

case "${1:-status}" in
  rw)
    echo "0" > "$RO_FILE"
    "$SWITCH" usb 0
    echo "USB aktiv (beschreibbar). Am PC das Laufwerk 'VIDEOS' mounten."
    ;;
  ro)
    echo "1" > "$RO_FILE"
    "$SWITCH" usb 1
    echo "USB aktiv (read-only). Am PC das Laufwerk 'VIDEOS' mounten."
    ;;
  back|ap)
    "$SWITCH" ap
    echo "Zurück im AP-Modus."
    ;;
  gpio)
    echo "GPIO 16: $(read_gpio16)"
    echo "(lo = gegen GND = Admin/rw,  hi = offen = Kunde/ro)"
    ;;
  status)
    "$SWITCH" status
    echo "GPIO 16: $(read_gpio16)"
    ;;
  *)
    echo "Usage: sudo bash pi/test-usb.sh {rw|ro|back|gpio|status}" >&2
    exit 1
    ;;
esac
