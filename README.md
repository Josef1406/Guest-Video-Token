# Guest_Video_Token

Offline-Video-Token auf **Raspberry Pi Zero W**. Gäste einer Veranstaltung
verbinden sich mit einem offenen WLAN und öffnen dort ihre Videos zum Ansehen,
Herunterladen oder Teilen (WhatsApp / Fotos). **Kein Internet nötig.**
Videos werden vom Admin bequem über das Web-Admin-Interface hochgeladen —
einzeln, mehrere MP4s parallel oder als ZIP mit einem ganzen Event.

---

## Inhaltsverzeichnis

- [Betriebsmodi](#betriebsmodi)
- [Hardware / GPIO](#hardware--gpio)
- [SD-Karte flashen](#sd-karte-flashen-einziger-setup-schritt)
- [Installation (ein Befehl)](#installation-ein-befehl)
- [Gäste-Ansicht](#gäste-ansicht)
- [Admin-Web-UI](#admin-web-ui)
- [Wartungs-Modus](#wartungs-modus-heim-wlan-gpio-27)
- [Dateien direkt kopieren (WinSCP / scp)](#dateien-direkt-kopieren-winscp--scp)
- [LED manuell testen](#led-manuell-testen)
- [Services & Skripte](#services--skripte)
- [Integration mit Video-Gästebuch](#integration-mit-video-gästebuch)
- [Troubleshooting](#troubleshooting)

---

## Betriebsmodi

| Modus | Wann | Zweck |
|---|---|---|
| **AP** (Default) | Immer beim normalen Boot | Offenes WLAN `Video_GB` auf `192.168.4.1`, Gäste sehen ihre Videos, Admin lädt neue hoch |
| **Wartung** | GPIO 27 → GND beim Boot | Pi verbindet sich mit deinem Heim-WLAN → SSH / RustDesk / VNC / WinSCP |

Kein USB-Massenspeicher-Modus, kein Schiebeschalter — alles läuft entweder
über die Admin-Web-UI (AP) oder über SSH/WinSCP im Heim-WLAN (Wartung).

---

## Hardware / GPIO

Benötigt: **Raspberry Pi Zero W**, SD-Karte (≥ 16 GB), Micro-USB-Netzteil,
optional Duo-LED + Vorwiderstand, optional Jumper/Taster für GPIO 27.

| GPIO | Phys. Pin | Funktion | Logik |
|---|---|---|---|
| **GPIO 27** | 13 | **Wartungs-Modus** (nur beim Boot ausgewertet) | LOW beim Boot = Heim-WLAN-Client |
| **GPIO 23** | 16 | Duo-LED Pol A (via ~330 Ω) | HIGH im Wartungs-Modus |
| **GPIO 16** | 36 | Duo-LED Pol B                | HIGH im AP-Modus |
| GND         | 14 | Masse für GPIO 27 Brücke | — |

**Duo-LED (2-polig, antiparallel):** zwischen GPIO 23 (Pin 16) und GPIO 16
(Pin 36) mit ~330 Ω in Reihe. Farbe hängt von der Stromrichtung ab:

- **AP-Modus:**       GPIO23 = LOW,  GPIO16 = HIGH → z. B. rot
- **Wartungs-Modus:** GPIO23 = HIGH, GPIO16 = LOW  → z. B. grün
- **Aus:**            beide LOW

Falls die Farben vertauscht sind: LED umdrehen oder in `pi/boot-mode.sh` die
Zuweisungen `ap` / `client` tauschen.

---

## SD-Karte flashen (einziger Setup-Schritt)

Mit dem **Raspberry Pi Imager** (Windows/Mac/Linux):

1. **OS wählen:** *Raspberry Pi OS Lite (32-bit)* – Bookworm empfohlen.
2. **Speicher:** deine SD-Karte (≥ 16 GB, mehr für viele Videos).
3. **⚙️ Zahnrad-Symbol (Erweitert)** — hier alles Wichtige eintragen:
   - **Hostname:** z. B. `videotoken`
   - **SSH aktivieren:** Passwort-Auth, Benutzer `pi` + Passwort setzen
   - **WLAN konfigurieren:** deine **Heim-WLAN-SSID + Passwort** (Land `AT`/`DE`)
     — dient für die einmalige Installation und für spätere Wartung.
4. **Schreiben.** SD-Karte in den Pi, einschalten, ~2 Minuten warten.

Keine Partitionierung, kein GParted, kein Mounten. Videos landen später einfach
unter `/srv/videos` auf der Root-Partition.

---

## Installation (ein Befehl)

Nach dem ersten Boot ist der Pi im **Heim-WLAN** (weil im Imager konfiguriert).
IP am Router ablesen, dann per SSH:

```bash
ssh pi@<ip-des-pi>
curl -fsSL https://raw.githubusercontent.com/Josef1406/Guest-Video-Token/main/pi/bootstrap.sh | sudo bash
sudo reboot
```

Das Bootstrap-Skript:

- installiert `git`, klont das Repo nach `/opt/guest-video-token`
- übernimmt die Heim-WLAN-Zugangsdaten aus dem Imager als
  `/etc/wpa_supplicant/wpa_supplicant-client.conf` (Wartungs-Config)
- ruft `pi/install.sh` auf: Pakete, nginx, hostapd, dnsmasq, Admin-API,
  systemd-Units, Rechte auf `/srv/videos` (Gruppe `videos`, `pi` + `www-data`)

Nach dem Reboot ist der Pi im AP-Modus:

- Gäste-WLAN: **`Video_GB`** (offen, kein Passwort)
- Pi-IP:      `192.168.4.1`
- Admin-UI:   `http://192.168.4.1/admin.html`  — Standard-PIN **`1234`**

Später im Heim-WLAN wartbar: GPIO 27 (Pin 13) beim Boot gegen GND (Pin 14)
brücken. Siehe [Wartungs-Modus](#wartungs-modus-heim-wlan-gpio-27).

---

## Gäste-Ansicht

Die Startseite (`/`) zeigt bewusst **nur einen Hinweis**, den QR-Code des
eigenen Videos zu scannen — keine Liste, keine Übersicht anderer Gäste.

### QR-Code-URL-Schema (kompatibel zum Video-Gästebuch)

```
http://192.168.4.1/v/<event-slug>/<event-slug>_TT_MM_JJJJ_HH_MM_SS_PIN.mp4
```

Auf der Player-Seite (`v.html`) hat der Gast:

- **Abspielen** — HTML5-Player mit Range-Support (iOS-Seek funktioniert)
- **Download** — MP4 direkt aufs Handy (WhatsApp / Fotos-App)
- **Teilen** — Web Share API (teilt bei Unterstützung die Datei selbst,
  auch offline); Fallback auf `wa.me`-Link
- **Kein Delete** — Gäste haben nur Leserechte

Anhang `?raw=1` liefert direkt die MP4-Datei (für externe Downloader).

---

## Admin-Web-UI

Erreichbar unter `http://192.168.4.1/admin.html` (nach Verbindung mit `Video_GB`).

- **Login** per PIN (Standard `1234`), Session-Cookie
- **Events** anlegen, umbenennen, löschen
- **Videos hochladen** — mehrere MP4s parallel, Streaming-Upload mit Fortschrittsbalken
- **ZIP-Upload** — komplette Event-ZIP hochladen, danach Vorschau der enthaltenen
  MP4s und „Als Event extrahieren" mit frei wählbarem Event-Namen
- **🔒 Schützen** — `chmod 0444` + `chattr +i` auf alle Dateien eines Events
- **🔓 Freigeben** — Sperre aufheben
- **Löschen** — einzelne Datei oder ganzes Event

**PIN ändern:**

```bash
sudo nano /etc/video-token/admin.pin
sudo systemctl restart video-token-admin
```

---

## Wartungs-Modus (Heim-WLAN, GPIO 27)

Wenn du beim Flashen im Imager schon dein Heim-WLAN eingetragen hast, hat
`bootstrap.sh` die Zugangsdaten bereits nach
`/etc/wpa_supplicant/wpa_supplicant-client.conf` übernommen.

Falls die Datei fehlt (siehe `ls /etc/wpa_supplicant/wpa_supplicant-client.conf`),
einmalig anlegen:

```bash
sudo tee /etc/wpa_supplicant/wpa_supplicant-client.conf > /dev/null <<'EOF'
country=AT
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={
    ssid="DEIN_HEIM_WLAN"
    psk="DEIN_WLAN_PASSWORT"
    key_mgmt=WPA-PSK
}
EOF
sudo chmod 600 /etc/wpa_supplicant/wpa_supplicant-client.conf
```

**Nutzung:**

1. Pi ausschalten.
2. **GPIO 27 (Pin 13)** gegen **GND (Pin 14)** brücken.
3. Pi einschalten. Statt AP verbindet er sich ins Heim-WLAN. LED wechselt Farbe.
4. IP am Router ablesen → `ssh pi@<ip>` oder WinSCP.
5. Nach der Wartung Brücke entfernen und neu booten → wieder AP.

**Recovery ohne SSH:** SD-Karte in einen PC, auf der Boot-Partition eine
`wpa_supplicant.conf` mit deinem Heim-WLAN ablegen und eine leere Datei
`video-token-client-mode` daneben. Beim nächsten Boot mit GPIO 27 → GND
geht der Pi in den Wartungs-Modus.

---

## Dateien direkt kopieren (WinSCP / scp)

Der User `pi` gehört zur Gruppe `videos` und darf direkt in `/srv/videos/`
schreiben (setgid, `chmod 2775`, neue Dateien erben die Gruppe).

- **Im Wartungs-Modus:** Heim-WLAN-IP verwenden (bequem, volle LAN-Geschwindigkeit).
- **Im AP-Modus:** PC mit `Video_GB` verbinden, WinSCP/scp auf `192.168.4.1`,
  Benutzer `pi`. Langsamer (Pi-Zero-WLAN), aber funktioniert.

```bash
scp -r ./Hochzeit2024 pi@192.168.4.1:/srv/videos/
```

---

## LED manuell testen

```bash
# AP-Farbe (z. B. rot)
sudo pinctrl set 23 op dl && sudo pinctrl set 16 op dh

# Wartungs-Farbe (z. B. grün)
sudo pinctrl set 23 op dh && sudo pinctrl set 16 op dl

# Aus
sudo pinctrl set 23 op dl && sudo pinctrl set 16 op dl
```

---

## Services & Skripte

| Unit | Zweck |
|---|---|
| `video-token-bootmode.service` | Liest GPIO 27 beim Boot, setzt Client- oder AP-Modus |
| `video-token-ap.service`       | Startet AP + nginx |
| `video-token-admin.service`    | Admin-API auf `127.0.0.1:8080` (nginx proxied `/api/admin/`) |
| `hostapd`, `dnsmasq`, `nginx`  | Standard-Systemdienste |

| Pfad | Zweck |
|---|---|
| `/usr/local/sbin/switch-mode`         | `ap` / `status` |
| `/usr/local/sbin/video-token-bootmode`| Boot-Modus-Erkennung + LED |
| `/usr/local/sbin/admin-server.py`     | Admin-API (Python) |
| `/usr/local/sbin/pi-lock-videos`      | `chmod 0444` + `chattr +i` auf `/srv/videos` |
| `/usr/local/sbin/pi-unlock-videos`    | Aufheben |
| `/srv/videos/`                        | Event-Ordner mit MP4-Dateien |
| `/var/www/video-token/`               | Statische Web-UI (nginx-Root) |
| `/etc/video-token/admin.pin`          | Admin-PIN |
| `/var/lib/video-token/uploads/`       | Temporäre ZIP-Uploads |

**Repo updaten und ausrollen:**

```bash
cd /opt/guest-video-token && sudo git pull
sudo bash pi/install.sh          # Configs + Skripte neu ausrollen
# oder gezielt nur einzelne Teile:
sudo install -m 0755 pi/admin-server.py /usr/local/sbin/admin-server.py
sudo cp -r web/. /var/www/video-token/
sudo systemctl restart video-token-admin nginx
```

---

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

---

## Phonebooth-Direktupload (`/api/upload`)

Externe Systeme (Video-Gästebuch / Phonebooth) können Videos direkt zum
Token pushen — ohne Admin-PIN, authentifiziert über ein zufälliges
Upload-Secret.

**Secret**
- Wird beim `install.sh` einmalig generiert (`openssl rand -hex 32`) und
  liegt unter `/etc/video-token/upload.secret` (Modus `640 root:www-data`).
- Auslesen: `sudo cat /etc/video-token/upload.secret`
- Im Video-Gästebuch als `token_upload_secret` eintragen.

**Endpoints (nginx `/api/` → 127.0.0.1:8080, Streaming, unbegrenzte Größe)**

`POST /api/events`  – legt Event-Ordner idempotent an.
```bash
curl -X POST http://192.168.4.1/api/events \
  -H "X-Upload-Secret: $SECRET" \
  -H "Content-Type: application/json" \
  -d '{"event":"Hochzeit Helga & Bernd"}'
# -> {"ok":true,"event":"Hochzeit_Helga_Bernd","created":true,"path":"/srv/videos/..."}
```

`POST /api/upload`  – Multipart-Upload eines Videos.
Felder: `event` (Pflicht), `filename` (optional, sonst wird der originale
Dateiname des File-Feldes verwendet); File-Feld `file` mit dem MP4-Body.
```bash
curl -X POST http://192.168.4.1/api/upload \
  -H "X-Upload-Secret: $SECRET" \
  -F "event=Hochzeit Helga & Bernd" \
  -F "filename=Take_01.mp4" \
  -F "file=@/pfad/zum/video.mp4;type=video/mp4"
# -> {"ok":true,"event":"...","file":"Take_01.mp4","size":...,
#     "url":"/media/.../Take_01.mp4","play":"/v/.../Take_01.mp4"}
```

Ablauf serverseitig: der Datei-Teil wird direkt nach
`/srv/videos/.uploads-tmp/<tok>.part` gestreamt und nach erfolgreichem
Empfang atomar nach `/srv/videos/<event-slug>/<datei>.mp4` verschoben
(`os.replace`), Rechte `0664` in Gruppe `videos`.

Event-Namen werden zu Slugs normalisiert (nur `A-Z a-z 0-9 . _ - Leerzeichen`),
Dateinamen müssen auf `.mp4` enden.

Fehlermeldungen: `401 invalid or missing upload secret`, `400 invalid ...`,
`507 not enough disk space`.

---



## Troubleshooting

**iPhone springt nach dem Verbinden mit `Video_GB` zurück ins Heimnetz.**
→ Captive-Portal-Fix in `pi/config/nginx.conf` sorgt für `200 OK` auf allen
iOS/Android/Windows-Probes. Falls trotzdem: Portal-Sheet einmal bestätigen
(„Verbunden bleiben"), oder im WLAN-Info auf ⓘ → „Auto-Verbinden" für `Video_GB`
aktivieren.

**Admin-UI meldet 502 / Login geht nicht.**
```bash
sudo systemctl status video-token-admin
sudo journalctl -u video-token-admin -b --no-pager | tail -50
```

**Wartungs-Modus wird nicht erkannt (bleibt im AP).**
```bash
# GPIO-Pegel: mit Brücke = 0, ohne = 1
pinctrl get 27
# Log der Boot-Entscheidung:
sudo journalctl -u video-token-bootmode.service -b --no-pager
# Client-Config vorhanden?
ls -l /etc/wpa_supplicant/wpa_supplicant-client.conf
```
Fehlt die Client-Config, siehe [Wartungs-Modus](#wartungs-modus-heim-wlan-gpio-27).

**Hinweise:**

- Pi Zero W hat nur einen WLAN-Chip. Im AP-Modus gibt es kein Internet — gewollt.
- `wpa_supplicant` ist im AP-Betrieb deaktiviert, damit `hostapd` `wlan0` exklusiv nutzt.
- Upload-Geschwindigkeit ist durch den Pi-Zero-WLAN-Chip auf ~1–2 MB/s begrenzt.
  Für große Batches lieber Wartungs-Modus + `scp` über LAN oder ZIP-Upload nutzen.
