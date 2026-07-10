#!/usr/bin/env bash
# switch-mode.sh – vereinfacht: nur AP-Modus.
# (USB-Massenspeicher-Modus entfernt; Videos werden per Web-Upload verwaltet.)
set -euo pipefail

MODE_FILE=/var/lib/video-token/mode
mkdir -p "$(dirname "$MODE_FILE")"
AP_IP=192.168.4.1/24

prepare_ap_interface() {
  rfkill unblock wlan 2>/dev/null || true
  systemctl stop wpa_supplicant.service wpa_supplicant@wlan0.service 2>/dev/null || true
  if command -v nmcli >/dev/null 2>&1; then
    nmcli connection down video-token-client 2>/dev/null || true
    nmcli device set wlan0 managed no 2>/dev/null || true
  fi
  ip link set wlan0 up 2>/dev/null || true
  ip addr flush dev wlan0 2>/dev/null || true
  ip addr replace "$AP_IP" dev wlan0
}

ap_mode() {
  echo "-> AP-Modus"
  systemctl stop dnsmasq 2>/dev/null || true
  prepare_ap_interface
  systemctl restart hostapd
  ip addr replace "$AP_IP" dev wlan0
  systemctl restart dnsmasq nginx
  echo "ap" > "$MODE_FILE"
}

case "${1:-status}" in
  ap)     ap_mode ;;
  status) echo "mode=$(cat "$MODE_FILE" 2>/dev/null || echo ap)" ;;
  *)      echo "Usage: $0 {ap|status}" >&2; exit 1 ;;
esac
