# Guest_Video_Token

Offline-Video-Token auf **Raspberry Pi Zero W**. Gäste einer Veranstaltung
verbinden sich mit einem offenen WLAN und scannen den QR-Code auf ihrem
Ausdruck, um das am Video-Gästebuch aufgenommene Video anzusehen, herunter-
zu laden oder per WhatsApp zu teilen. **Kein Internet nötig.**

## GPIO-Belegung (aktuell)

| GPIO | Phys. Pin | Funktion | Logik |
|---|---|---|---|
| **GPIO 24** | 18 | Schiebeschalter Position **AP** | gegen GND = AP-Modus |
| **GPIO 25** | 22 | Schiebeschalter Position **USB** | gegen GND = USB-Modus |
| **GPIO 16** | 36 | **Schreibschutz** für USB-Gadget | LOW = Admin/beschreibbar, HIGH = Kunde/read-only |
| **GPIO 27** | 13 | **Wartungs-Modus** (nur beim Boot) | LOW beim Boot = Heim-WLAN-Client |
| GPIO 17 | 11 | *Optionaler Taster* „Modus umschalten" | Nur falls kein Schiebeschalter verwendet wird |

**Schiebeschalter-Verdrahtung (3-polig):** Mittlerer Pin → **GND**, Außenpin 1 → **GPIO 24**, Außenpin 2 → **GPIO 25**.

> **Wichtig:** Die internen Pull-Ups sind aktiviert. Alle Eingänge sind daher im unbeschalteten Zustand **HIGH** (offen) und werden durch Verbindung mit **GND** als aktiv erkannt.

## Betriebsmodi

| Modus | Beschreibung | Umschalten |
|---|---|---|
| **AP** (Default) | Offenes WLAN `Video_GB`, nginx auf `192.168.4.1` | Schalter auf GPIO 24 / `switch-mode ap` |
| **USB** | Pi als USB-Massenspeicher am Windows-PC (exFAT `VIDEOS`) | Schalter auf GPIO 25 / `switch-mode usb` |
| **Wartung** | SSH über Heim-WLAN (GPIO 27 LOW beim Boot) | – |

Der USB-Modus kennt zwei Schreibschutz-Zustände:

| Zustand | Bedeutung | Wer darf schreiben |
|---|---|---|
| **Read-only** (`ro=1`) | Windows sieht das Laufwerk als schreibgeschützt | niemand (Kunden-Modus) |
| **Beschreibbar** (`ro=0`) | Windows sieht das Laufwerk wie eine normale USB-Festplatte | Admin zum Aufspielen |

- **Modus-Umschaltung** erfolgt mit dem Schiebeschalter an **GPIO 24 (AP)** und **GPIO 25 (USB)**. Der mittlere Pin des Schalters gehört an **GND**.
- **Schreibschutz** wird über **GPIO 16** gesteuert: gegen GND = Admin/beschreibbar, offen/HIGH = Kunde/read-only.
- **Wartungsmodus** wird einmalig beim Boot durch **GPIO 27 LOW** aktiviert (siehe Abschnitt unten).

## SD-Karte partitionieren

Empfohlenes Layout (min. 32 GB):

```
p1  FAT32   ~256 MB   /boot           (Raspberry Pi Imager Default)
p2  ext4    ~6 GB     /               (Raspberry Pi OS Lite)
p3  exFAT   Rest      Label: VIDEOS   (Datenpartition)
```

Ablauf:

1. **Raspberry Pi OS Lite (32-bit)** mit dem *Raspberry Pi Imager* auf die SD-Karte flashen. Im Imager unter „Einstellungen": SSH aktivieren, WLAN leer lassen, User `pi` mit Passwort setzen.
2. SD-Karte in Linux-PC stecken (oder auf dem Pi selbst nach dem ersten Boot). Root-Partition auf ~6 GB verkleinern:
   ```bash
   sudo parted /dev/sdX
   (parted) resizepart 2 6GiB
   (parted) mkpart primary 6GiB 100%
   (parted) name 3 VIDEOS
   (parted) quit
   sudo mkfs.exfat -n VIDEOS /dev/sdX3
   ```
3. Erster Boot am Pi (LAN/Monitor oder später via AP-SSH), dann Repo klonen und installieren.

## Installation

```bash
sudo apt update && sudo apt install -y git
git clone <dieses-repo> guest-video-token
cd guest-video-token
sudo bash pi/install.sh
sudo reboot
```

Nach dem Reboot erscheint das WLAN **`Video_GB`** (offen). Startseite:
`http://192.168.4.1/`.

## Videos aufspielen (Admin-Workflow)

1. **GPIO 16 auf Admin stellen** (gegen GND / LOW) – damit der USB-Gadget beschreibbar wird.
2. Schiebeschalter auf **USB** (oder `sudo switch-mode usb`).
3. Pi per USB-Kabel (Port **USB**, nicht **PWR**) an Windows anschließen.
4. Laufwerk `VIDEOS` erscheint. Videos in Ordner-Struktur ablegen:

   ```
   VIDEOS:\<event-slug>\<event-slug>_TT_MM_JJJJ_HH_MM_SS_PIN.mp4
   ```

   Beispiel: `hochzeit-mueller\hochzeit-mueller_06_07_2026_18_42_11_4711.mp4`

5. Sicher trennen, Schiebeschalter auf **AP** (oder `sudo switch-mode ap`).
6. **GPIO 16 auf Kunde stellen** (offen / HIGH) – jetzt wird der USB-Gadget bei Bedarf read-only geladen.
7. Datenpartition wird automatisch nach `/srv/videos/` gemountet (siehe fstab-Eintrag).

> Hinweis: Der GPIO 16-Schalter wirkt nur auf den USB-Massenspeicher. Im AP-Modus greifen Gäste ausschließlich über den schreibgeschützten nginx-Webserver auf die Videos zu.

## QR-Code-URL-Schema

Kompatibel zum Video-Gästebuch:

```
http://192.168.4.1/v/<event-slug>/<event-slug>_TT_MM_JJJJ_HH_MM_SS_PIN.mp4
```

Diese URL öffnet die Player-Seite mit Download- und WhatsApp-Button.
`?raw=1` liefert direkt die MP4-Datei (für externe Player/Downloader).

## Integration mit Video-Gästebuch

Der Token ist bewusst generisch: er weiß nichts über Domains oder Cloud-Ziele.
Die Entscheidung „Cloud oder Token" fällt beim Anlegen des Events **im
Video-Gästebuch-Projekt** – der QR-Generator baut die URL entsprechend.

Empfohlenes Konfig-Feld pro Event:

```jsonc
{
  "event_slug": "hochzeit-mueller",
  "delivery_mode": "token",           // "cloud" | "token"
  "qr_base_url_cloud": "https://videos.deinedomain.de",
  "qr_base_url_token": "http://192.168.4.1"
}
```

Der QR-Generator wählt die Base-URL nach `delivery_mode` und hängt das
bekannte Namensschema an:

| Modus  | QR-URL |
|---|---|
| cloud  | `https://videos.deinedomain.de/<event>/<file>.mp4` |
| token  | `http://192.168.4.1/v/<event>/<file>.mp4` |

Wichtig:

- Für Token-Events **`http://`** verwenden (kein HTTPS-Zertifikat auf dem Pi).
- Beim Token-Modus zusätzlich `/v/` im Pfad – das triggert die Player-Seite
  (`v.html`) mit Download- und WhatsApp-Button. Ohne `/v/` bzw. mit `?raw=1`
  wird direkt die MP4-Datei ausgeliefert.
- Der Datei- und Ordnername ist in beiden Modi identisch
  (`<event-slug>_TT_MM_JJJJ_HH_MM_SS_PIN.mp4`) – dieselben Videos funktionieren
  also ohne Umbenennen sowohl in der Cloud als auch auf dem Token.

Am Token selbst muss nichts angepasst werden.



## Schreibschutz

Da Windows-Gäste die exFAT-Datenpartition per USB-Gadget direkt mounten, können klassische Unix-Rechte (`chmod`, `chattr`) nicht verhindern, dass jemand im Explorer Dateien löscht oder umbenennt. Die einzige Strategie, die Windows akzeptiert, ist der **USB-Gadget-Read-Only-Flag `ro=1`**.

### Empfohlene Strategie: Hardware-Schalter (GPIO 16)

| GPIO 16 | Zustand | USB-Gadget | Bedeutung |
|---|---|---|---|
| **gegen GND / LOW** | Admin | `ro=0` beschreibbar | Admin kopiert/ändert/löscht Videos |
| **offen / HIGH** | Kunde | `ro=1` read-only | Gäste können nur kopieren, nichts verändern |

Vorgang:

1. Token an Admin-PC anschließen, GPIO 16 auf GND → USB-Gadget beschreibbar.
2. Videos mit dem Explorer/WinSCP kopieren oder bearbeiten.
3. Token wieder abziehen, GPIO 16 offen/HIGH.
4. Token an Kunden übergeben. Falls der Kunde in den USB-Modus schaltet, meldet Windows das Laufwerk als schreibgeschützt.

## Wartungs-Modus (Heim-WLAN-Client, GPIO 27 beim Boot)

GPIO 27 wird **einmalig beim Boot** ausgewertet.
Damit lässt sich der Token für Wartung/Updates ins eigene Heim-WLAN holen –
ganz ohne Bildschirm/Tastatur:

| GPIO 27 beim Boot | `wpa_supplicant-client.conf` vorhanden | Ergebnis |
|---|---|---|
| **offen / HIGH** | egal | Normalbetrieb: AP `Video_GB` bzw. USB-Gadget (bisheriges Verhalten). |
| **gegen GND / LOW** | **ja** | **Client-Modus**: Pi verbindet sich mit dem konfigurierten Heim-WLAN (DHCP). AP, USB-Gadget und Admin-API bleiben aus. Zugriff per SSH / RustDesk / VNC über die vom Router vergebene IP. |
| gegen GND / LOW | nein | Normalbetrieb (Fallback, damit der Token nie „unerreichbar" wird). |

### Einrichtung (einmalig)

```bash
sudo cp /etc/wpa_supplicant/wpa_supplicant-client.conf.example \
        /etc/wpa_supplicant/wpa_supplicant-client.conf
sudo nano /etc/wpa_supplicant/wpa_supplicant-client.conf   # SSID + PSK
sudo chmod 600 /etc/wpa_supplicant/wpa_supplicant-client.conf
```

Ablauf für einen Wartungs-Zugriff:

1. Pi ausschalten.
2. GPIO 27 gegen GND legen (Schalter auf „Wartung").
3. Pi einschalten. `video-token-bootmode.service` liest GPIO 27, aktiviert
   `wpa_supplicant` und deaktiviert für diesen Boot AP-, USB- und Admin-Dienste.
4. Am Router die IP des Pi ablesen, dann `ssh pi@<ip>` oder RustDesk verbinden.
5. Nach der Wartung: Pi ausschalten, GPIO 27 wieder öffnen, Pi einschalten –
   der Token startet wieder normal (AP/USB). Der Schreibschutz-Schalter
   auf GPIO 16 arbeitet unabhängig davon.

> Wichtig: Der Wartungsmodus braucht eine WLAN-Client-Konfiguration. Ab dieser
> Version akzeptiert der Token entweder
> `/etc/wpa_supplicant/wpa_supplicant-client.conf` **oder** eine auf der
> Windows-sichtbaren Boot-Partition abgelegte `wpa_supplicant.conf`.

### Recovery ohne SSH über Windows-PC

Wenn der AP sichtbar ist, aber keine Verbindung zulässt, und der Wartungsmodus
nicht im Router auftaucht:

1. Pi ausschalten, SD-Karte in den Windows-PC stecken.
2. Auf der Boot-Partition eine leere Datei `ssh` ohne Endung anlegen.
3. Auf der Boot-Partition eine Datei `wpa_supplicant.conf` anlegen:

   ```conf
   country=DE
   ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
   update_config=1

   network={
       ssid="DEIN_HEIM_WLAN_NAME"
       psk="DEIN_HEIM_WLAN_PASSWORT"
       key_mgmt=WPA-PSK
   }
   ```

4. Optional zum Erzwingen des Wartungsmodus zusätzlich eine leere Datei
   `video-token-client-mode` auf der Boot-Partition anlegen.
5. SD-Karte zurück in den Pi, GPIO 27 beim Boot gegen GND legen und starten.
6. In der Fritzbox nach der neuen IP suchen und per SSH verbinden.


### Technische Details

- `switch-mode usb` liest den Wert aus `/var/lib/video-token/gadget_ro` (default `1`).
- Der GPIO-Daemon `gpio-switch.py` schreibt diesen Wert bei GPIO 16 und ruft `switch-mode reapply` auf, falls der USB-Modus bereits aktiv ist.
- Der aktive `ro`-Wert ist im Kernel-Modul-Parameter `/sys/module/g_mass_storage/parameters/ro` ablesbar.
- Admin-Status-Seite (`http://192.168.4.1/admin.html`) zeigt Soll- und Ist-Wert des Schreibschutzes an.

### Sekundärer Schutz (Dateisystem)

- `sudo pi-lock-videos` setzt `chmod 0444` + `chattr +i` (funktioniert auf ext4).
- `sudo pi-unlock-videos` macht es rückgängig.
- Auf **exFAT** wirken `chattr`/`chmod` nicht – daher ist der GPIO 16/USB-Gadget-Read-Only-Flag die wirksame Schutzschicht für Windows.

### Admin-Status

Die Admin-Seite zeigt:

- Betriebsmodus (AP / USB)
- USB-Schreibschutz: Soll-Wert (Datei) vs. Ist-Wert (Kernel)
- Dateisystem-Schreibschutz (`chmod`/`chattr`) als zusätzliche Info
- Event-Übersicht und Speicherplatz

## Skripte

| Pfad nach Install | Zweck |
|---|---|---|
| `/usr/local/sbin/switch-mode` | `ap` / `usb [0\|1]` / `toggle` / `reapply` / `status` |
| `/usr/local/sbin/pi-lock-videos` | Videos immutable + read-only (ext4) |
| `/usr/local/sbin/pi-unlock-videos` | Aufheben |
| `/usr/local/sbin/gpio-switch.py` | GPIO-Daemon (via systemd) |

Services: `video-token-ap.service` (Boot-Default AP), `video-token-gpio.service` (Taster/Schalter).

### GPIO-Belegung (Zusammenfassung)

| GPIO | Phys. Pin | Funktion | Verdrahtung | Logik |
|---|---|---|---|---|
| **24** | 18 | Schiebeschalter „AP" | Außenpin des Schalters | gegen GND = AP-Modus |
| **25** | 22 | Schiebeschalter „USB" | Außenpin des Schalters | gegen GND = USB-Modus |
| **16** | 36 | Schreibschutz-Schalter | gegen GND | LOW = Admin/beschreibbar, HIGH = Kunde/read-only |
| **27** | 13 | Wartungs-Modus (nur beim Boot) | gegen GND beim Boot | LOW = Heim-WLAN-Client |
| 17 | 11 | *Optionaler Taster* „Modus umschalten" | gegen GND | Nur falls kein Schiebeschalter verwendet wird |

Schiebeschalter-Verdrahtung (3-polig): Mittlerer Pin → **GND**, Außenpin 1 → **GPIO 24**, Außenpin 2 → **GPIO 25**.

## Hinweise

- Pi Zero W: nur ein WLAN-Chip. Im AP-Modus keine Internet-Verbindung – gewollt.
- `wpa_supplicant` wird deaktiviert, damit `hostapd` `wlan0` exklusiv nutzt.
- USB-Gadget funktioniert nur am **USB**-Port des Pi (der Port näher an der Mitte), nicht am `PWR`-Port.
- Für iOS-Seek (Range-Requests) sind `Accept-Ranges: bytes` und `mp4`-MIME in `nginx.conf` gesetzt.
