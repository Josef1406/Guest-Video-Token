#!/usr/bin/env bash
# switch-mode.sh ap|usb|toggle|status|reapply
#
# Der USB-Massenspeicher-Modus liest den Schreibschutz aus
# /var/lib/video-token/gadget_ro (0 = beschreibbar, 1 = read-only).
# Dieser Wert wird vom GPIO-Daemon (gpio-switch.py, GPIO 26) gepflegt.
set -euo pipefail

MODE_FILE=/var/lib/video-token/mode
RO_FILE=/var/lib/video-token/gadget_ro
mkdir -p "$(dirname "$MODE_FILE")"
BACKING=/dev/disk/by-label/VIDEOS   # exFAT-Datenpartition

current()    { cat "$MODE_FILE" 2>/dev/null || echo "ap"; }
current_ro() { cat "$RO_FILE"   2>/dev/null || echo "1"; }   # Default: read-only (sicher)

ap_mode() {
  echo "-> AP-Modus"
  modprobe -r g_mass_storage 2>/dev/null || true
  systemctl start hostapd dnsmasq nginx
  echo "ap" > "$MODE_FILE"
}

usb_mode() {
  local ro="${1:-$(current_ro)}"
  echo "-> USB-Massenspeicher-Modus (ro=$ro)"
  systemctl stop hostapd dnsmasq || true
  if [[ ! -b "$BACKING" ]]; then
    echo "FEHLER: $BACKING nicht gefunden. Label 'VIDEOS' auf exFAT-Partition?" >&2
    exit 2
  fi
  umount "$BACKING" 2>/dev/null || true
  modprobe -r g_mass_storage 2>/dev/null || true
  modprobe g_mass_storage file="$BACKING" removable=1 ro="$ro" stall=0 iSerialNumber="videotoken"
  echo "usb" > "$MODE_FILE"
}

# Wird vom GPIO-Daemon bei Änderung von GPIO 26 aufgerufen: nur wenn wir
# gerade im USB-Modus sind, den Gadget mit neuem ro-Wert neu laden.
reapply() {
  if [[ "$(current)" == "usb" ]]; then
    usb_mode "$(current_ro)"
  fi
}

case "${1:-status}" in
  ap)      ap_mode ;;
  usb)     usb_mode "${2:-}" ;;
  toggle)  [[ "$(current)" == "ap" ]] && usb_mode || ap_mode ;;
  reapply) reapply ;;
  status)  echo "mode=$(current) ro=$(current_ro)" ;;
  *)       echo "Usage: $0 {ap|usb [0|1]|toggle|reapply|status}" >&2; exit 1 ;;
esac
