#!/usr/bin/env bash
# Guest_Video_Token – Installer für Raspberry Pi Zero W (Raspberry Pi OS Lite)
# Vereinfachte AP-only-Variante mit Web-Upload (kein USB-Gadget).
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Bitte als root ausführen: sudo bash install.sh" >&2
  exit 1
fi

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> Pakete installieren"
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  hostapd dnsmasq nginx-light \
  python3 \
  iw rfkill wpasupplicant

if ! DEBIAN_FRONTEND=noninteractive apt-get install -y raspi-gpio 2>/dev/null; then
  DEBIAN_FRONTEND=noninteractive apt-get install -y pinctrl || true
fi

echo "==> Services stoppen für Config-Rollout"
systemctl stop hostapd dnsmasq nginx || true
systemctl unmask hostapd || true

echo "==> Configs kopieren"
install -m 0644 "$REPO_DIR/config/hostapd.conf" /etc/hostapd/hostapd.conf
sed -i 's|^#\?DAEMON_CONF=.*|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd

install -m 0644 "$REPO_DIR/config/dnsmasq.conf" /etc/dnsmasq.d/video-token.conf

install -m 0644 "$REPO_DIR/config/nginx.conf" /etc/nginx/sites-available/video-token
ln -sf /etc/nginx/sites-available/video-token /etc/nginx/sites-enabled/video-token
rm -f /etc/nginx/sites-enabled/default

echo "==> dhcpcd static IP für wlan0 (nur falls dhcpcd genutzt wird)"
if [[ -f /etc/dhcpcd.conf ]] && ! grep -q "# video-token" /etc/dhcpcd.conf 2>/dev/null; then
  cat "$REPO_DIR/config/dhcpcd.conf.append" >> /etc/dhcpcd.conf
fi

echo "==> NetworkManager: wlan0 im Normalbetrieb für AP freigeben"
if [[ -d /etc/NetworkManager/conf.d ]]; then
  cat > /etc/NetworkManager/conf.d/99-video-token-wlan0-unmanaged.conf <<'EOF'
[keyfile]
unmanaged-devices=interface-name:wlan0
EOF
fi

echo "==> wpa_supplicant deaktivieren (AP-only)"
systemctl disable --now wpa_supplicant.service 2>/dev/null || true
rfkill unblock wlan || true

echo "==> Webroot & Video-Verzeichnis"
mkdir -p /srv/videos
# Gruppe 'videos' anlegen, pi + www-data hinzufügen, damit beide schreiben können
groupadd -f videos
usermod -aG videos www-data || true
if id pi >/dev/null 2>&1; then usermod -aG videos pi || true; fi
chown -R www-data:videos /srv/videos || true
# setgid, damit neue Dateien/Unterordner die Gruppe 'videos' erben
chmod 2775 /srv/videos
find /srv/videos -mindepth 1 -type d -exec chmod 2775 {} + 2>/dev/null || true
find /srv/videos -mindepth 1 -type f -exec chmod 0664 {} + 2>/dev/null || true
mkdir -p /var/www/video-token
cp -r "$REPO_DIR/../web/." /var/www/video-token/
chown -R www-data:www-data /var/www/video-token

echo "==> Skripte nach /usr/local/sbin"
install -m 0755 "$REPO_DIR/switch-mode.sh"       /usr/local/sbin/switch-mode
install -m 0755 "$REPO_DIR/pi-lock-videos.sh"    /usr/local/sbin/pi-lock-videos
install -m 0755 "$REPO_DIR/pi-unlock-videos.sh"  /usr/local/sbin/pi-unlock-videos
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

echo "==> Upload-Secret für /api/upload (Booth / Video-Gästebuch)"
if [[ ! -s /etc/video-token/upload.secret ]]; then
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32 > /etc/video-token/upload.secret
  else
    head -c 48 /dev/urandom | od -An -tx1 | tr -d ' \n' > /etc/video-token/upload.secret
  fi
  echo "   -> neu generiert: sudo cat /etc/video-token/upload.secret"
fi
chown root:www-data /etc/video-token/upload.secret 2>/dev/null || true
chmod 0640 /etc/video-token/upload.secret

# Admin-Server läuft als root (siehe systemd-Unit) und braucht daher kein sudoers.
rm -f /etc/sudoers.d/video-token


echo "==> WLAN-Client-Konfiguration (Vorlage, für Wartungsmodus)"
install -d -m 0755 /etc/wpa_supplicant
if [[ ! -f /etc/wpa_supplicant/wpa_supplicant-client.conf.example ]]; then
  install -m 0600 "$REPO_DIR/config/wpa_supplicant-client.conf.example" \
    /etc/wpa_supplicant/wpa_supplicant-client.conf.example
fi

echo "==> systemd-Units"
install -m 0644 "$REPO_DIR/systemd/video-token-bootmode.service" /etc/systemd/system/
install -m 0644 "$REPO_DIR/systemd/video-token-ap.service"       /etc/systemd/system/
install -m 0644 "$REPO_DIR/systemd/video-token-admin.service"    /etc/systemd/system/
install -d -m 0755 /etc/systemd/system/dnsmasq.service.d
install -m 0644 "$REPO_DIR/systemd/dnsmasq.service.d/override.conf" \
  /etc/systemd/system/dnsmasq.service.d/override.conf

# alte USB/GPIO-Unit ggf. entfernen
systemctl disable --now video-token-gpio.service 2>/dev/null || true
rm -f /etc/systemd/system/video-token-gpio.service

systemctl daemon-reload
systemctl enable video-token-bootmode.service
systemctl enable video-token-ap.service
systemctl enable video-token-admin.service

echo
echo "Fertig. Bitte neu starten:  sudo reboot"
echo "SSID nach Reboot: Video_GB   |   http://192.168.4.1/"
echo "Admin:            http://192.168.4.1/admin.html (PIN 1234)"
