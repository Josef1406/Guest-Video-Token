#!/usr/bin/env bash
# Guest_Video_Token – Boot-Mode-Detection
#
# Liest GPIO 27 (BCM, Pin 13, gegen GND, intern pull-up) beim Boot:
#   GPIO 27 LOW  + /etc/wpa_supplicant/wpa_supplicant-client.conf vorhanden
#                -> CLIENT-Modus (Pi verbindet sich mit dem konfigurierten
#                   Heim-WLAN, DHCP; AP/USB-Services bleiben aus).
#   sonst        -> NORMAL-Modus (AP oder USB je nach Schiebeschalter
#                   GPIO 5/6, wie bisher). GPIO 27 dient dann zur Laufzeit
#                   dem gpio-switch-Daemon als Schreibschutz-Schalter für
#                   den USB-Gadget.
#
# Muss VOR dhcpcd, hostapd, dnsmasq und den video-token-*-Services laufen.
set -euo pipefail

PIN=27
MARKER=/run/video-token-client-mode
CLIENT_CONF=/etc/wpa_supplicant/wpa_supplicant-client.conf
DHCPCD_CONF=/etc/dhcpcd.conf

# Pin als Eingang mit Pull-Up konfigurieren und Pegel lesen.
LEVEL=1
if command -v raspi-gpio >/dev/null 2>&1; then
  raspi-gpio set "$PIN" ip pu || true
  sleep 0.1
  LEVEL=$(raspi-gpio get "$PIN" | grep -oE "level=[01]" | head -n1 | cut -d= -f2)
elif command -v pinctrl >/dev/null 2>&1; then
  pinctrl set "$PIN" ip pu || true
  sleep 0.1
  LEVEL=$(pinctrl get "$PIN" | grep -oE "\| (hi|lo)" | head -n1 | awk '{print ($2=="hi")?1:0}')
  [[ -z "$LEVEL" ]] && LEVEL=1
fi
echo "boot-mode: GPIO $PIN level=$LEVEL"

rm -f "$MARKER"

if [[ "$LEVEL" == "0" && -f "$CLIENT_CONF" ]]; then
  echo "boot-mode: CLIENT (Heim-WLAN)"
  : > "$MARKER"

  # AP-Static-IP-Block in dhcpcd.conf deaktivieren (Marker #vt-ap#).
  if grep -q '^interface wlan0$' "$DHCPCD_CONF"; then
    sed -i \
      -e 's|^interface wlan0$|#vt-ap# interface wlan0|' \
      -e 's|^    static ip_address=192.168.4.1/24$|#vt-ap#    static ip_address=192.168.4.1/24|' \
      -e 's|^    nohook wpa_supplicant$|#vt-ap#    nohook wpa_supplicant|' \
      "$DHCPCD_CONF"
  fi

  # wpa_supplicant mit Client-Config aktivieren
  install -m 0600 "$CLIENT_CONF" /etc/wpa_supplicant/wpa_supplicant.conf
  systemctl unmask wpa_supplicant.service 2>/dev/null || true
  systemctl enable wpa_supplicant.service 2>/dev/null || true
else
  echo "boot-mode: NORMAL (AP/USB)"
  # AP-Static-IP-Block wieder aktivieren, falls zuvor deaktiviert.
  sed -i 's|^#vt-ap# ||' "$DHCPCD_CONF" || true
  systemctl disable wpa_supplicant.service 2>/dev/null || true
fi
