#!/usr/bin/env bash
# Guest_Video_Token – Boot-Mode-Detection
#
# Liest GPIO 27 (BCM, Pin 13, gegen GND, intern pull-up) beim Boot:
#   GPIO 27 LOW  + WLAN-Client-Config vorhanden
#                -> CLIENT-Modus (Pi verbindet sich mit dem konfigurierten
#                   Heim-WLAN, DHCP; AP/USB-Services bleiben aus).
#   sonst        -> NORMAL-Modus (AP oder USB je nach Schiebeschalter
#                   GPIO 24/25, wie bisher). Der Schreibschutz-Schalter
#                   für den USB-Gadget liegt separat auf GPIO 16 und wird
#                   vom gpio-switch-Daemon zur Laufzeit ausgewertet.
#
# Muss VOR dhcpcd, hostapd, dnsmasq und den video-token-*-Services laufen.
set -euo pipefail

PIN=27
MARKER=/run/video-token-client-mode
CLIENT_CONF=/etc/wpa_supplicant/wpa_supplicant-client.conf
BOOT_CLIENT_CONF=/boot/firmware/wpa_supplicant.conf
[[ -f /boot/wpa_supplicant.conf ]] && BOOT_CLIENT_CONF=/boot/wpa_supplicant.conf
FORCE_CLIENT=/boot/firmware/video-token-client-mode
[[ -f /boot/video-token-client-mode ]] && FORCE_CLIENT=/boot/video-token-client-mode
DHCPCD_CONF=/etc/dhcpcd.conf
NM_UNMANAGED_CONF=/etc/NetworkManager/conf.d/99-video-token-wlan0-unmanaged.conf

write_nm_unmanaged() {
  if [[ -d /etc/NetworkManager/conf.d ]]; then
    cat > "$NM_UNMANAGED_CONF" <<'EOF'
[keyfile]
unmanaged-devices=interface-name:wlan0
EOF
  fi
}

remove_nm_unmanaged() {
  rm -f "$NM_UNMANAGED_CONF"
}

extract_wpa_value() {
  local key="$1"
  local file="$2"
  sed -nE "s/^[[:space:]]*${key}=\"(.*)\"[[:space:]]*$/\1/p" "$file" | head -n1
}

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

ACTIVE_CLIENT_CONF=""
if [[ -f "$CLIENT_CONF" ]]; then
  ACTIVE_CLIENT_CONF="$CLIENT_CONF"
elif [[ -f "$BOOT_CLIENT_CONF" ]]; then
  ACTIVE_CLIENT_CONF="$BOOT_CLIENT_CONF"
fi

FORCE=0
[[ -f "$FORCE_CLIENT" ]] && FORCE=1

if [[ ( "$LEVEL" == "0" || "$FORCE" == "1" ) && -n "$ACTIVE_CLIENT_CONF" ]]; then
  echo "boot-mode: CLIENT (Heim-WLAN)"
  : > "$MARKER"
  remove_nm_unmanaged

  # AP-Static-IP-Block in dhcpcd.conf deaktivieren (Marker #vt-ap#).
  if grep -q '^interface wlan0$' "$DHCPCD_CONF"; then
    sed -i \
      -e 's|^interface wlan0$|#vt-ap# interface wlan0|' \
      -e 's|^    static ip_address=192.168.4.1/24$|#vt-ap#    static ip_address=192.168.4.1/24|' \
      -e 's|^    nohook wpa_supplicant$|#vt-ap#    nohook wpa_supplicant|' \
      "$DHCPCD_CONF"
  fi

  # Client-Config aktivieren. Unterstützt sowohl die installierte Config
  # als auch eine per Windows auf bootfs abgelegte wpa_supplicant.conf.
  install -d -m 0755 /etc/wpa_supplicant
  install -m 0600 "$ACTIVE_CLIENT_CONF" /etc/wpa_supplicant/wpa_supplicant.conf

  # Raspberry Pi OS Bookworm/Trixie nutzt oft NetworkManager. Falls nmcli
  # vorhanden ist, legen wir daraus eine native WLAN-Verbindung an; ältere
  # Systeme nutzen weiter wpa_supplicant + dhcpcd.
  if command -v nmcli >/dev/null 2>&1; then
    SSID="$(extract_wpa_value ssid /etc/wpa_supplicant/wpa_supplicant.conf)"
    PSK="$(extract_wpa_value psk /etc/wpa_supplicant/wpa_supplicant.conf)"
    nmcli radio wifi on 2>/dev/null || true
    nmcli connection delete video-token-client 2>/dev/null || true
    if [[ -n "$SSID" ]]; then
      nmcli connection add type wifi ifname wlan0 con-name video-token-client ssid "$SSID" 2>/dev/null || true
      nmcli connection modify video-token-client ipv4.method auto ipv6.method ignore connection.autoconnect yes 2>/dev/null || true
      if [[ -n "$PSK" ]]; then
        nmcli connection modify video-token-client wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$PSK" 2>/dev/null || true
      fi
      nmcli device set wlan0 managed yes 2>/dev/null || true
    fi
    systemctl disable wpa_supplicant.service 2>/dev/null || true
  else
    systemctl unmask wpa_supplicant.service 2>/dev/null || true
    systemctl enable wpa_supplicant.service 2>/dev/null || true
  fi
else
  echo "boot-mode: NORMAL (AP/USB)"
  write_nm_unmanaged
  # AP-Static-IP-Block wieder aktivieren, falls zuvor deaktiviert.
  sed -i 's|^#vt-ap# ||' "$DHCPCD_CONF" || true
  if command -v nmcli >/dev/null 2>&1; then
    nmcli connection down video-token-client 2>/dev/null || true
    nmcli connection delete video-token-client 2>/dev/null || true
  fi
  systemctl disable wpa_supplicant.service 2>/dev/null || true
fi
