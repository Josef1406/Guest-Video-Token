# Guest_Video_Token

Offline-Video-Token auf **Raspberry Pi Zero W**. Gäste einer Veranstaltung
verbinden sich mit einem offenen WLAN und öffnen dort ihre Videos zum Ansehen
und Herunterladen. **Kein Internet nötig.**
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
- [Software-Update ohne Wartungsmodus](#software-update-ohne-wartungsmodus)
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

Die Startseite (`/`) zeigt die WLAN-Anmeldung und ausschließlich den vom Admin
gespeicherten Video-Link-Modus — keine Moduswahl für Kunden, keine Video-Liste.
Der lokale QR-Foto-Scanner bleibt unter `/scan.html` verfügbar; auf der
Startseite wird er nur im Zertifikat-Modus als Übergangslösung verlinkt.

### Zwei Video-Link-Modi (neu)

Auf der Startseite führt **Admin · PIN** zur vorhandenen PIN-Anmeldung. Unter
**Video-Link-Modus** wählt der Admin:

| Auswahl | Gäste-Seite | QR-Adresse |
|---|---|---|
| **Normal** (Standard) | WLAN-Hinweise und normaler Kamera-Scan; keine Zertifikatsseite | `http://192.168.4.1/v/<event>/<datei>.mp4` |
| **Mit Zertifikat** | Zertifikatsbereich mit aktuellem Einrichtungsstatus | `https://video.gaestebuch.cloud/v/<event>/<datei>.mp4` |

Die Auswahl wird atomar in `/etc/video-token/video-link.json` gespeichert und
bleibt bei Neustart und erneuter Installation erhalten. Sie ist **unabhängig**
vom AP-/Wartungsmodus, GPIO 27 und der LED.
Nur nach PIN-Anmeldung in der Admin-Oberfläche kann die Auswahl geändert
werden. Gäste lesen lediglich den gespeicherten Modus. Beim Zurückkehren
zur Startseite wird die Auswahl erneut vom Pi geladen; solange sie nicht
erreichbar ist, wird kein Video-Link-Modus angezeigt.

**Wichtig: Echte HTTPS-Ausstellung ist noch nicht freigeschaltet.** Der
Hetzner-API-Zugang zur korrekten Zone wurde lesend geprüft. Der neue
Online-Aussteller läuft standardmäßig gegen Let's Encrypt Staging.
Testzertifikate werden vom Pi ausdrücklich abgelehnt. Erst nach verifizierter
Eigentümerfreigabe, Test-Ausstellung, Veröffentlichung und echtem Pi-Test
darf `CERTIFICATE_ISSUER_ENV=production` gesetzt werden. Moduswahl allein
macht Cloud-QRs nicht über die normale Kamera lokal nutzbar.

### Neuer Handy-Ablauf und einmalige Gerätefreigabe

1. Auf dem aktualisierten Pi als PIN-Admin den Zertifikat-Modus einstellen.
2. **Token-Freigabeanfrage herunterladen** wählen. Der lokale P-256-Schlüssel
   bleibt auf dem Pi; nur Geräte-ID und öffentliche CSR werden exportiert.
3. Mit Internet `https://guest-video-share.lovable.app/certificates` öffnen,
   **Eigentümer · Token-Freigabe** wählen und mit Lovable anmelden.
4. Das angemeldete Konto muss durch den berechtigten Projekt-Verwalter in
   `certificate_operators` freigegeben werden. Es gibt keine automatische
   Erstbenutzer-Adminvergabe. Erst dann die heruntergeladene Anfrage genehmigen.
5. Auf der lokalen Gäste-Startseite **Zertifikat erneuern** wählen. Die
   signierte Anfrage bleibt bis zur Aktivierung gespeichert und kann erneut
   verwendet werden; Gäste wählen weder CSR noch Domain.
6. WLAN kurz verlassen, die Online-Seite in Safari öffnen und die Anfrage
   auswählen. Der Fortschritt zeigt Domainprüfung und Ausstellung.
7. Nach erfolgreicher **Produktions**-Ausstellung die öffentliche Zertifikatsdatei
   herunterladen, erneut mit Video_GB verbinden und unter
   **Zertifikat übertragen** auf der lokalen Startseite auswählen.

`pi/certificate_bridge.py` prüft System-Vertrauenskette, exakten SAN,
Pi-Schlüssel, Laufzeit und die tatsächlich über localhost/SNI ausgelieferte
TLS-Verbindung. Erst dann wird HTTPS als aktiv gemeldet. nginx-Fehler stellen
die vorherige Konfiguration wieder her. HTTP bleibt zur Wiederherstellung
erreichbar; der HTTPS-Server liefert keine Admin-API oder Eventliste.
Der Pi braucht eine ausreichend korrekte Systemzeit und vorhandene
CA-Vertrauensanker. Handyzeit wird nicht übernommen, TLS-Prüfung niemals
deaktiviert.

Der Online-Aussteller speichert Gerätefreigaben und Aufträge in Lovable Cloud,
verschlüsselt sein separates ACME-Konto und bearbeitet nur den festen
TXT-Prüfnamen `_acme-challenge.video`. Bestehende TXT-Werte werden nicht
ersetzt. Ein global aktiver Auftrag verhindert parallele DNS-Veränderungen.
Jeder Klick/Statusabruf setzt den gespeicherten Auftrag fort. Bei geschlossenem
Browser bleibt der Auftrag gespeichert; er muss mit derselben Anfrage fortgesetzt
werden. Ein geschützter Recovery-Endpunkt ist vorbereitet, jedoch **kein
automatischer Zeitplan aktiviert**. Echte Aussteller- und Hosting-Tests sowie
die physische Pi-/iPhone-Abnahme stehen noch aus.

Im HTTPS-Modus kann ein angemeldeter Admin bereits eine **Zertifikatsanfrage
vorbereiten** und als `.csr` herunterladen. Der Fortschritt und die Meldung
bestätigen nur diese Vorbereitung, **keine abgeschlossene Erneuerung**. OpenSSL
erzeugt pro Pi einen EC-Schlüssel, der unter `/etc/video-token/tls/device.key`
mit `0600` verbleibt. Nur die öffentliche Anfrage wird übertragen. Sie beweist
noch keinen Domainbesitz. Niemals den privaten Schlüssel der Cloud-Webseite
oder DNS-Zugangsdaten an Gäste verteilen.

Nächster Einrichtungsschritt: Eigentümerkonto anmelden und autorisieren,
Test-Ausstellung prüfen, Online-Dienst veröffentlichen und Pi aktualisieren;
anschließend echte Ausstellung und physische Aktivierung abnehmen.
Ein Zertifikat für dieselbe Cloud-Domain erlaubt auch dem Pi, diese Domain
darzustellen; die Geräte müssen entsprechend geschützt sein. Offline-Uhrzeit
und Zertifikatsablauf müssen ebenfalls gelöst werden.

Die bisher versprochene automatische Handy-Brücke ist **nicht garantiert**:
Wildcard-DNS im Token-WLAN und Handy-Routing können den Internetzugang verhindern.
Der geplante verlässliche Ablauf benötigt dann einen kurzen WLAN-Wechsel zum
Online-Abholen und anschließend die Rückkehr zum Token. Die echte Ausstellung
und der direkte Kamera-Scan müssen später auf dem Pi und iPhone geprüft werden.
Bis dahin bleibt der bestehende lokale Foto-Scanner für Cloud-QRs verfügbar.

**Diese Version komplett aktualisieren (Wartungsmodus):**

```bash
cd /opt/guest-video-token && sudo git pull
sudo bash pi/install.sh
sudo reboot
```

Diesmal genügt ein reines Kopieren der Webdateien nicht: auch `video_link.py`
muss neben `admin-server.py` installiert werden. Videos und vorhandene PIN
bleiben erhalten. Nach Neustart ohne GPIO-27-Brücke im `Video_GB`-WLAN testen.
Die Lovable-Vorschau zeigt dieselbe Startseite ausdrücklich ohne Pi-Verbindung;
Anmeldung und Moduswahl funktionieren nur auf dem Raspberry Pi.

### Ein Cloud-QR für Cloud und Token (ohne Zertifikat)

Der gedruckte QR kann unverändert dieses Format enthalten:

```text
https://video.gaestebuch.cloud/v/<event-slug>/<event-slug>_TT_MM_JJJJ_HH_MM_SS_PIN.mp4
```

- **Cloud:** Mit der normalen Kamera scannen, wie bisher.
- **Token:** Videos unter `/srv/videos/<event-slug>/<dateiname>.mp4` kopieren.
  Ordner- und Dateinamen müssen exakt dem Cloud-Link entsprechen.
  Gäste verbinden sich mit `Video_GB`, nehmen die Verbindung an und wählen
  am iPhone nach „Success“ über das X „Ohne Internet verwenden“.
  Danach in Safari/Chrome **`http://192.168.4.1/scan.html`** öffnen,
  „QR-Code fotografieren“ antippen und den QR auf dem Aufkleber fotografieren.
  Je nach Gerät öffnet sich die Kamera oder die Fotoauswahl.

Der Scanner liest das Foto vollständig lokal mit dem mitgelieferten jsQR
(Apache-2.0, Lizenz unter `web/assets/jsQR.LICENSE`). Weder Foto noch Cloud-Link
werden ins Internet hochgeladen. Er übernimmt Event und Datei unverändert,
prüft die lokale MP4 und öffnet den bestehenden Player. Kein TLS-Zertifikat,
kein Internet und keine Änderung der gedruckten Cloud-QRs nötig.
Als Alternative kann der vollständige Video-Link eingefügt werden.

Wichtig: Das ist **kein Live-Kamera-Scanner** (`getUserMedia` ist auf HTTP
normalerweise gesperrt). Verwendet wird die Fotoaufnahme über die Dateiauswahl.
Bitte im normalen Browser öffnen, nicht im iOS-Captive-Fenster. Ein direkter
Scan mit der normalen Kamera öffnet weiterhin den HTTPS-Cloud-Link.
Andere Domains oder QR-Formate mit einer undurchsichtigen ID werden abgewiesen.
Fehlt die lokale Datei, bleibt die Seite mit einer verständlichen Meldung offen.

**Bestehenden Token aktualisieren (Wartungsmodus mit Internet):**

```bash
cd /opt/guest-video-token && sudo git pull
sudo cp -r web/. /var/www/video-token/
```

Kein Installer-Lauf oder nginx-Neustart nötig. Scanner-Dateien müssen komplett
mitkopiert werden. Bei alten Seiten im Safari-Cache die Websitedaten für
`192.168.4.1` löschen. Die Fotoaufnahme auf einem echten iPhone/Android bitte
nach dem Rollout prüfen; sie kann im Captive-Fenster eingeschränkt sein.

### QR-Code-URL-Schema (kompatibel zum Video-Gästebuch)

```
http://192.168.4.1/v/<event-slug>/<event-slug>_TT_MM_JJJJ_HH_MM_SS_PIN.mp4
```

Auf der Player-Seite (`v.html`) hat der Gast:

- **Abspielen** — HTML5-Player mit Range-Support (iOS-Seek funktioniert)
- **Aufs Handy laden** — MP4 direkt herunterladen
- **Kein Delete** — Gäste haben nur Leserechte

Anhang `?raw=1` liefert direkt die MP4-Datei (für externe Downloader).

---

## Admin-Web-UI

Erreichbar unter `http://192.168.4.1/admin.html` (nach Verbindung mit `Video_GB`).

- **Login** per PIN (Standard `1234`), Session-Cookie
- **Video-Link-Modus** dauerhaft zwischen Normal und HTTPS-Vorbereitung wählen
- **Zertifikatsanfrage** im HTTPS-Modus lokal vorbereiten und herunterladen (noch keine Online-Erneuerung)
- **Events** anlegen, umbenennen, löschen
- **Videos hochladen** — mehrere MP4s parallel, Streaming-Upload mit Fortschrittsbalken
- **ZIP-Upload** — komplette Event-ZIP hochladen, danach Vorschau der enthaltenen
  MP4s und „Als Event extrahieren" mit frei wählbarem Event-Namen
- **Software aktualisieren** — lädt die aktuelle Version direkt von GitHub
  und installiert sie auf dem Token (siehe nächstes Kapitel)
- **🔒 Schützen** — `chmod 0444` + `chattr +i` auf alle Dateien eines Events
- **🔓 Freigeben** — Sperre aufheben
- **Löschen** — einzelne Datei oder ganzes Event

**PIN ändern:**

```bash
sudo nano /etc/video-token/admin.pin
sudo systemctl restart video-token-admin
```

---

## Software-Update ohne Wartungsmodus

Der Token kann sich selbst aktualisieren — ganz ohne GPIO-Brücke und SSH:

1. Mit `Video_GB` verbinden (das Handy behält sein Mobilfunk-Internet).
2. `http://192.168.4.1/admin.html` öffnen, PIN eingeben.
3. Karte **„Software aktualisieren"** → **Jetzt aktualisieren**.

Die Admin-Seite lädt die aktuelle Version direkt von GitHub (über das Handy),
überträgt sie PIN-geschützt an den Token, und der Token baut sie selbst ein:
Webseiten (`web/`), Skripte und Konfigurationen (`pi/`). Danach starten die
Dienste neu und die Seite lädt automatisch wieder.

- Videos, Admin-PIN, Upload-Secret und WLAN-Einstellungen bleiben erhalten.
- Jede Datei wird gegen die GitHub-Prüfsumme geprüft; bei einem Fehler wird
  der alte Stand wiederhergestellt (Rollback).
- Nach Änderungen an WLAN-/Boot-Konfiguration fordert die Seite einen
  Neustart des Pi (**Pi neu starten**).
- **Nicht** Teil des Updates: Betriebssystem-Pakete (`apt upgrade`). Dafür
  bleibt der Wartungsmodus (unten) die Rückfallebene.

Einmalige Voraussetzung: Diese Funktion muss selbst einmal installiert
werden — im Wartungsmodus `sudo git pull && sudo bash pi/install.sh`
ausführen. Danach wird der Wartungsmodus für normale Updates nicht mehr
gebraucht.

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

Alternativ kann immer der Cloud-QR im oben dokumentierten Format gedruckt
werden: Auf dem Token wird er über `/scan.html` per Foto lokal geöffnet.

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

## Zertifikat automatisch über Heim-WLAN erneuern

Im Zertifikat-Modus zeigt die Startseite (`http://192.168.4.1`) das Formular **„Token mit deinem Heim-WLAN verbinden“**. Der Kunde gibt dort einmalig WLAN-Name und Passwort ein. Der Token verbindet sich danach über ein **zweites WLAN-Modul** mit dem Internet und holt sich das Zertifikat selbst. Das Token-WLAN `Video_GB` bleibt dabei an.

- Empfohlen: USB-WLAN-Stick (erscheint als `wlan1`) am Micro-USB-OTG-Adapter.
- Ohne Stick pausiert der Token `Video_GB` für 2–5 Minuten, verbindet sich über den eingebauten Chip (`wlsta0`) mit dem Heim-WLAN, erneuert und schaltet `Video_GB` danach wieder ein. Ein Sicherheits-Timer startet `Video_GB` spätestens nach 10 Minuten neu, auch wenn etwas hängt. Die automatische Erneuerung startet nur, wenn gerade kein Gast verbunden ist.
- Alle 6 Stunden prüft der Token, ob das Zertifikat in weniger als 30 Tagen abläuft, und erneuert es dann automatisch, sobald das Heim-WLAN erreichbar ist.
- Das Passwort liegt nur auf dem Pi (`/etc/video-token/home-wifi.json`, 0600) und kann über keine Seite ausgelesen werden.
- Die Erneuerung über Dateien und WLAN-Wechsel am Handy bleibt als Rückfallweg erhalten.
