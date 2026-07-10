#!/usr/bin/env bash
# Guest_Video_Token – Installer für Raspberry Pi Zero W (Raspberry Pi OS Lite)
# Idempotent: kann mehrfach ausgeführt werden.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Bitte als root ausführen: sudo bash install.sh" >&2
  exit 1
fi

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
BOOT_CONFIG="/boot/config.txt"
[[ -f /boot/firmware/config.txt ]] && BOOT_CONFIG="/boot/firmware/config.txt"

echo "==> Pakete installieren"
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  hostapd dnsmasq nginx-light \
  exfat-fuse exfatprogs \
  python3-gpiozero python3-rpi.gpio \
  iw rfkill wpasupplicant

# raspi-gpio bzw. pinctrl (je nach OS-Version) für Boot-Mode-Detection
if ! DEBIAN_FRONTEND=noninteractive apt-get install -y raspi-gpio 2>/dev/null; then
  echo "   raspi-gpio nicht verfügbar, versuche pinctrl (RaspiOS Bookworm/Trixie)"
  DEBIAN_FRONTEND=noninteractive apt-get install -y pinctrl || true
fi

echo "==> Services stoppen für Config-Rollout"
systemctl stop hostapd dnsmasq nginx || true
systemctl unmask hostapd || true

echo "==> Configs kopieren"
install -m 0644 "$REPO_DIR/config/hostapd.conf" /etc/hostapd/hostapd.conf
sed -i 's|^#\?DAEMON_CONF=.*|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd

install -m 0644 "$REPO_DIR/config/dnsmasq.conf" /etc/dnsmasq.d/video-token.conf
# stock dnsmasq.conf nicht anfassen, wir nutzen /etc/dnsmasq.d/

install -m 0644 "$REPO_DIR/config/nginx.conf" /etc/nginx/sites-available/video-token
ln -sf /etc/nginx/sites-available/video-token /etc/nginx/sites-enabled/video-token
rm -f /etc/nginx/sites-enabled/default

echo "==> dhcpcd static IP für wlan0"
if ! grep -q "# video-token" /etc/dhcpcd.conf 2>/dev/null; then
  cat "$REPO_DIR/config/dhcpcd.conf.append" >> /etc/dhcpcd.conf
fi

echo "==> wpa_supplicant deaktivieren (AP-only)"
systemctl disable --now wpa_supplicant.service 2>/dev/null || true
rfkill unblock wlan || true

echo "==> USB-Gadget Overlay in $BOOT_CONFIG"
if ! grep -q "^dtoverlay=dwc2" "$BOOT_CONFIG"; then
  echo "" >> "$BOOT_CONFIG"
  cat "$REPO_DIR/config/boot-config.append" >> "$BOOT_CONFIG"
fi
if ! grep -q "^dwc2$" /etc/modules; then
  cat "$REPO_DIR/config/modules.append" >> /etc/modules
fi

echo "==> Webroot & Video-Verzeichnis"
mkdir -p /srv/videos
mkdir -p /var/www/video-token
cp -r "$REPO_DIR/../web/." /var/www/video-token/
chown -R www-data:www-data /var/www/video-token

echo "==> Skripte nach /usr/local/sbin"
install -m 0755 "$REPO_DIR/switch-mode.sh"       /usr/local/sbin/switch-mode
install -m 0755 "$REPO_DIR/pi-lock-videos.sh"    /usr/local/sbin/pi-lock-videos
install -m 0755 "$REPO_DIR/pi-unlock-videos.sh"  /usr/local/sbin/pi-unlock-videos
install -m 0755 "$REPO_DIR/gpio-switch.py"       /usr/local/sbin/gpio-switch.py
install -m 0755 "$REPO_DIR/admin-server.py"      /usr/local/sbin/admin-server.py
install -m 0755 "$REPO_DIR/boot-mode.sh"         /usr/local/sbin/video-token-bootmode

mkdir -p /var/lib/video-token
echo "ap" > /var/lib/video-token/mode

echo "==> Admin-PIN (Default 1234, falls noch nicht gesetzt)"
mkdir -p /etc/video-token
if [[ ! -f /etc/video-token/admin.pin ]]; then
  echo "1234" > /etc/video-token/admin.pin
  chmod 0600 /etc/video-token/admin.pin
  echo "   -> Default-PIN: 1234  (ändern: sudo nano /etc/video-token/admin.pin && sudo systemctl restart video-token-admin)"
fi

echo "==> WLAN-Client-Konfiguration (Vorlage)"
# Vorlage nach /etc/wpa_supplicant/ kopieren, damit sie leicht editierbar ist.
# Der Client-Modus (GPIO 27 beim Boot LOW) aktiviert sich nur, wenn die
# Datei /etc/wpa_supplicant/wpa_supplicant-client.conf existiert.
install -d -m 0755 /etc/wpa_supplicant
if [[ ! -f /etc/wpa_supplicant/wpa_supplicant-client.conf.example ]]; then
  install -m 0600 "$REPO_DIR/config/wpa_supplicant-client.conf.example" \
    /etc/wpa_supplicant/wpa_supplicant-client.conf.example
  echo "   -> Für Client-Modus: sudo cp /etc/wpa_supplicant/wpa_supplicant-client.conf.example \\"
  echo "                              /etc/wpa_supplicant/wpa_supplicant-client.conf"
  echo "      und SSID/PSK anpassen, dann GPIO 27 beim Boot gegen GND."
fi

echo "==> systemd-Units"
install -m 0644 "$REPO_DIR/systemd/video-token-bootmode.service" /etc/systemd/system/
install -m 0644 "$REPO_DIR/systemd/video-token-ap.service"       /etc/systemd/system/
install -m 0644 "$REPO_DIR/systemd/video-token-gpio.service"     /etc/systemd/system/
install -m 0644 "$REPO_DIR/systemd/video-token-admin.service"    /etc/systemd/system/
systemctl daemon-reload
systemctl enable video-token-bootmode.service
systemctl enable video-token-ap.service
systemctl enable video-token-gpio.service  || true
systemctl enable video-token-admin.service

echo
echo "Fertig. Bitte neu starten:  sudo reboot"
echo "SSID nach Reboot: Video_GB   |   http://192.168.4.1/"
