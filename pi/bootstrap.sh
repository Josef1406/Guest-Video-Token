#!/usr/bin/env bash
# Guest_Video_Token – One-Liner Bootstrap
# Aufruf am frisch geflashten Pi (via SSH, mit Internet):
#   curl -fsSL https://raw.githubusercontent.com/Josef1406/Guest-Video-Token/main/pi/bootstrap.sh | sudo bash
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/Josef1406/Guest-Video-Token.git}"
TARGET_DIR="${TARGET_DIR:-/opt/guest-video-token}"

if [[ $EUID -ne 0 ]]; then
  echo "Bitte mit sudo ausführen." >&2
  exit 1
fi

echo "==> git installieren (falls nötig)"
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y git ca-certificates

echo "==> Repo nach $TARGET_DIR klonen/aktualisieren"
if [[ -d "$TARGET_DIR/.git" ]]; then
  git -C "$TARGET_DIR" pull --ff-only
else
  git clone --depth 1 "$REPO_URL" "$TARGET_DIR"
fi

echo "==> Wartungs-WLAN-Config aus aktueller Pi-Konfiguration übernehmen (für spätere Wartung)"
# Wenn per Raspberry Pi Imager ein WLAN vorkonfiguriert wurde, liegt es in
# /etc/wpa_supplicant/wpa_supplicant.conf. Als Wartungs-Vorlage kopieren.
if [[ -s /etc/wpa_supplicant/wpa_supplicant.conf ]] && \
   [[ ! -f /etc/wpa_supplicant/wpa_supplicant-client.conf ]]; then
  install -m 0600 /etc/wpa_supplicant/wpa_supplicant.conf \
    /etc/wpa_supplicant/wpa_supplicant-client.conf
  echo "   -> Heim-WLAN aus Imager-Setup als Wartungs-Config übernommen."
fi

echo "==> Installer starten"
bash "$TARGET_DIR/pi/install.sh"

echo
echo "Fertig. Neustart empfohlen: sudo reboot"
echo "Danach: WLAN 'Video_GB' → http://192.168.4.1/"
