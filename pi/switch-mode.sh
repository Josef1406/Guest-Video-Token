#!/usr/bin/env bash
# switch-mode.sh ap|usb|status|toggle
set -euo pipefail

MODE_FILE=/var/lib/video-token/mode
mkdir -p "$(dirname "$MODE_FILE")"
BACKING=/dev/disk/by-label/VIDEOS   # exFAT-Datenpartition
GADGET_RO=0                          # 1 = Windows sieht Laufwerk read-only

current() { cat "$MODE_FILE" 2>/dev/null || echo "ap"; }

ap_mode() {
  echo "-> AP-Modus"
  modprobe -r g_mass_storage 2>/dev/null || true
  systemctl start hostapd dnsmasq nginx
  echo "ap" > "$MODE_FILE"
}

usb_mode() {
  echo "-> USB-Massenspeicher-Modus"
  systemctl stop hostapd dnsmasq || true
  # nginx darf laufen bleiben; ohne wlan aber egal
  if [[ ! -b "$BACKING" ]]; then
    echo "FEHLER: $BACKING nicht gefunden. Label 'VIDEOS' auf exFAT-Partition?" >&2
    exit 2
  fi
  # Falls die Partition gemountet ist: unmounten, sonst sieht Windows keine Änderungen konsistent
  umount "$BACKING" 2>/dev/null || true
  modprobe g_mass_storage file="$BACKING" removable=1 ro="$GADGET_RO" stall=0 iSerialNumber="videotoken"
  echo "usb" > "$MODE_FILE"
}

case "${1:-status}" in
  ap)      ap_mode ;;
  usb)     usb_mode ;;
  toggle)  [[ "$(current)" == "ap" ]] && usb_mode || ap_mode ;;
  status)  echo "mode=$(current)" ;;
  *)       echo "Usage: $0 {ap|usb|toggle|status}" >&2; exit 1 ;;
esac
