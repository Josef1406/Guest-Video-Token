# Guest_Video_Token

Offline-Video-Token auf **Raspberry Pi Zero W**. Gäste einer Veranstaltung
verbinden sich mit einem offenen WLAN und öffnen dort ihre Videos zum Ansehen
oder Herunterladen (WhatsApp / Fotos). **Kein Internet nötig.**
Videos werden vom Admin bequem über das Web-Admin-Interface hochgeladen.

## Betriebsmodi

| Modus | Wann | Zweck |
|---|---|---|
| **AP** (Default) | Immer beim normalen Boot | Offenes WLAN `Video_GB` auf `192.168.4.1`, Gäste sehen ihre Videos, Admin lädt neue hoch |
| **Wartung** | GPIO 27 → GND beim Boot | Pi verbindet sich mit deinem Heim-WLAN → SSH / RustDesk / VNC |

Kein USB-Massenspeicher-Modus, kein Schiebeschalter für Modus-Umschaltung —
alles Weitere läuft über die Admin-Web-UI.

## GPIO

| GPIO | Phys. Pin | Funktion | Logik |
|---|---|---|---|
| **GPIO 27** | 13 | **Wartungs-Modus** (nur beim Boot) | LOW beim Boot = Heim-WLAN-Client |

Alle anderen GPIO-Rollen (Modus-Schalter, USB-Read-Only) sind entfallen.

## SD-Karte

Empfohlenes Layout (min. 16 GB, für viele Videos mehr):

```
p1  FAT32   ~256 MB   /boot
p2  ext4    Rest      /            (Raspberry Pi OS Lite, enthält /srv/videos)
```

Ein separates Datenpartitions-Label ist **nicht** mehr nötig — Videos liegen
einfach unter `/srv/videos` auf der Root-Partition. Wer trotzdem mit exFAT
oder einer Extra-Partition arbeiten möchte, kann sie unter `/srv/videos`
mounten (fstab-Eintrag).

## Installation

```bash
sudo apt update && sudo apt install -y git
git clone <dieses-repo> guest-video-token
cd guest-video-token
sudo bash pi/install.sh
sudo reboot
```

Nach dem Reboot:

- Gäste-WLAN: **`Video_GB`** (offen)
- Startseite: `http://192.168.4.1/`
- Admin:     `http://192.168.4.1/admin.html` (Standard-PIN `1234`)

## Videos verwalten (Admin)

1. Mit dem WLAN `Video_GB` verbinden.
2. `http://192.168.4.1/admin.html` öffnen, PIN eingeben.
3. **Event anlegen** (z. B. `hochzeit-mueller`).
4. **Videos hochladen** (mehrere MP4 gleichzeitig möglich, mit Fortschrittsbalken).
5. Optional **🔒 Schützen**: setzt die Dateien read-only (ext4 `chmod 0444` +
   `chattr +i`), damit auch versehentliche Änderungen ausgeschlossen sind.

Löschen (Datei oder ganzes Event) geht nur aus der Admin-UI. Gäste haben nur
Leserechte via nginx — sie können nichts löschen.

**PIN ändern:**
```bash
sudo nano /etc/video-token/admin.pin
sudo systemctl restart video-token-admin
```

## Gäste-Ansicht

Startseite `/` listet alle Events mit ihren Videos auf. Klick auf ein Video
öffnet die Player-Seite (`/v/<event>/<file>.mp4`) mit Download- und
WhatsApp-Button.

### QR-Code-URL-Schema (kompatibel zum Video-Gästebuch)

```
http://192.168.4.1/v/<event-slug>/<event-slug>_TT_MM_JJJJ_HH_MM_SS_PIN.mp4
```

`?raw=1` liefert direkt die MP4-Datei (für externe Player/Downloader).

## Wartungs-Modus (Heim-WLAN, GPIO 27)

Einmalig einrichten:

```bash
sudo cp /etc/wpa_supplicant/wpa_supplicant-client.conf.example \
        /etc/wpa_supplicant/wpa_supplicant-client.conf
sudo nano /etc/wpa_supplicant/wpa_supplicant-client.conf   # SSID + PSK
sudo chmod 600 /etc/wpa_supplicant/wpa_supplicant-client.conf
```

Nutzung:

1. Pi ausschalten.
2. GPIO 27 (Pin 13) gegen GND (Pin 14) brücken.
3. Pi einschalten. Statt AP verbindet er sich ins Heim-WLAN.
4. IP am Router ablesen, `ssh pi@<ip>`.
5. Nach der Wartung Brücke entfernen und neu booten → wieder normal.

**Recovery ohne SSH:** Windows-PC, SD-Karte auf Boot-Partition eine
`wpa_supplicant.conf` mit deinem Heim-WLAN ablegen und eine leere Datei
`video-token-client-mode`. Beim nächsten Boot mit GPIO 27 → GND geht der
Pi in den Wartungsmodus.

## Integration mit Video-Gästebuch

Der Token ist bewusst generisch. Beim Anlegen eines Events im Video-Gästebuch
wird pro Event entschieden, ob QR-Codes für Cloud oder Token generiert werden:

```jsonc
{
  "event_slug": "hochzeit-mueller",
  "delivery_mode": "token",           // "cloud" | "token"
  "qr_base_url_cloud": "https://videos.deinedomain.de",
  "qr_base_url_token": "http://192.168.4.1"
}
```

| Modus  | QR-URL |
|---|---|
| cloud  | `https://videos.deinedomain.de/<event>/<file>.mp4` |
| token  | `http://192.168.4.1/v/<event>/<file>.mp4` |

Am Token selbst muss nichts angepasst werden.

## Services (nach Install)

| Unit | Zweck |
|---|---|
| `video-token-bootmode.service` | GPIO 27 beim Boot lesen, Client- oder AP-Modus setzen |
| `video-token-ap.service`       | AP + nginx starten |
| `video-token-admin.service`    | Admin-API (127.0.0.1:8080), von nginx geproxied |
| `hostapd`, `dnsmasq`, `nginx`  | Standard-Systemdienste |

## Skripte

| Pfad | Zweck |
|---|---|
| `/usr/local/sbin/switch-mode`      | `ap` / `status` |
| `/usr/local/sbin/pi-lock-videos`   | `chmod 0444` + `chattr +i` auf `/srv/videos` |
| `/usr/local/sbin/pi-unlock-videos` | Aufheben |

## Hinweise

- Pi Zero W hat nur einen WLAN-Chip. Im AP-Modus gibt es kein Internet — das ist gewollt.
- `wpa_supplicant` ist im Normalbetrieb deaktiviert, damit `hostapd` `wlan0` exklusiv nutzt.
- Für iOS-Seek (Range-Requests) sind `Accept-Ranges: bytes` und `mp4`-MIME in `nginx.conf` gesetzt.
- Upload-Geschwindigkeit ist durch den Pi-Zero-WLAN-Chip begrenzt (~1–2 MB/s). Für große Batches
  empfiehlt sich der Wartungsmodus + `scp` über LAN.
