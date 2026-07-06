## Ziel

Ein Repo mit allen Skripten, Configs und Doku für einen Offline-Video-Token auf dem Raspberry Pi Zero W. Kein Web-App-Build im Lovable-Preview – Lovable dient hier als Editor/Ablage. Die minimale Web-UI ist statisches HTML/CSS/JS, das direkt von nginx auf dem Pi ausgeliefert wird.

## Repo-Struktur

```text
pi/
  install.sh                 # System-Setup (hostapd, dnsmasq, nginx, exfat, usb-gadget)
  switch-mode.sh             # ap | usb | status
  gpio-switch.py             # optionaler Daemon (gpiozero, Pin 17)
  pi-lock-videos.sh          # chattr +i, chmod 0444 rekursiv auf /srv/videos
  pi-unlock-videos.sh        # chattr -i, chmod 0644 rekursiv
  systemd/
    video-token-ap.service
    video-token-gpio.service
  config/
    hostapd.conf             # SSID Video_GB, offen, ch 6
    dnsmasq.conf             # DHCP 192.168.4.10-100, Captive-DNS → 192.168.4.1
    dhcpcd.conf.append       # static ip wlan0 = 192.168.4.1
    nginx.conf               # CORS, Range, MP4, Captive-Portal-Redirect
    boot-config.append       # dtoverlay=dwc2, modules-load
    modules.append           # dwc2
web/
  index.html                 # Fallback-Seite (Event-Liste)
  v.html                     # Player-Seite (liest ?e=<event>&f=<file>)
  assets/
    styles.css
    player.js                # Video-Player, Download, WhatsApp-Share, kein Delete
README.md                    # Partitionierung, Flash, Install, Bedienung, QR-URL-Schema
```

## Web-UI (statisch)

- `v.html` mit `<video controls playsinline preload="metadata">`, Quelle `/v/<event>/<file>.mp4`
- Buttons: **Download** (`<a download>`), **WhatsApp teilen** (`https://wa.me/?text=<encoded URL>`)
- Kein Delete, kein Upload
- URL-Schema kompatibel zum Video-Gästebuch: `http://192.168.4.1/v/<event-slug>/<event-slug>_TT_MM_JJJJ_HH_MM_SS_PIN.mp4`
- nginx rewrite `/v/<event>/<file>` → `v.html?e=<event>&f=<file>` für die Player-Seite; direkter `.mp4`-Pfad bleibt für Download/Range erhalten

## Betriebsmodi

- **AP (Default)**: `systemctl start hostapd dnsmasq nginx`, `modprobe -r g_mass_storage`
- **USB**: `systemctl stop hostapd dnsmasq`, `modprobe g_mass_storage file=/dev/disk/by-label/VIDEOS removable=1 ro=0 stall=0`
- **Wartung**: SSH über AP (`ssh pi@192.168.4.1`) – keine extra Services

`switch-mode.sh` schreibt zusätzlich `/var/lib/video-token/mode` für Statusabfrage.

## GPIO

- `gpiozero.Button(17, pull_up=True)` – kurzer Druck ruft `switch-mode.sh` mit dem jeweils anderen Modus auf
- Hardware-Schiebeschalter GPIO5/GND/GPIO6 wird zusätzlich als 2-Positionen-Schalter unterstützt (Level auf GPIO5 = AP, auf GPIO6 = USB); der Daemon reagiert auf Flankenwechsel

## Schreibschutz

- `pi-lock-videos.sh`: `find /srv/videos -type f -exec chmod 0444 {} +` und `chattr +i`
- `pi-unlock-videos.sh`: umgekehrt
- Hinweis in README: im USB-Modus wird die exFAT-Partition roh gemountet – `chattr` wirkt nur auf ext4. Empfehlung: `/srv/videos` liegt auf einer kleinen ext4-Partition, exFAT-Datenpartition wird per systemd-Job nach `/srv/videos` gesynct und dann gelockt. Alternative (einfacher): USB-Gadget mit `ro=1` erzwingt Read-only auf Windows-Seite. Beide Varianten dokumentiert, `ro=1` als Default.

## install.sh

- `apt install hostapd dnsmasq nginx-light exfat-fuse exfatprogs python3-gpiozero`
- Kopiert Configs an ihre Zielpfade, appendet Overlay-Zeilen idempotent in `/boot/config.txt` und `/etc/modules`
- `systemctl unmask/enable hostapd`, disabled `wpa_supplicant@wlan0`
- Installiert die drei systemd-Units, aktiviert `video-token-ap.service` und optional `video-token-gpio.service`
- Legt `/srv/videos/` an

## README

- SD-Karten-Layout: Boot (FAT32, ~256 MB) + Root (ext4, ~4 GB) + Daten (exFAT, Rest, Label `VIDEOS`)
- Erst-Flash mit Raspberry Pi Imager, danach dritte Partition per `parted`/`mkfs.exfat`
- Erste Inbetriebnahme, `switch-mode.sh usb` → Videos auf Windows kopieren → `switch-mode.sh ap` → `pi-lock-videos`
- QR-Code-Schema und Beispiel-URL

## Nicht enthalten

- Kein React-Build, kein Node-Server, kein Lovable-Cloud – reines Pi-Deployment
- Der bestehende TanStack-Start-Preview bleibt unverändert; die Preview zeigt weiter die Standard-Startseite. Willst du zusätzlich eine kleine Landing im Preview, die die README rendert?