# Guest_Video_Token

Offline-Video-Token auf **Raspberry Pi Zero W**. Gäste einer Veranstaltung
verbinden sich mit einem offenen WLAN und scannen den QR-Code auf ihrem
Ausdruck, um das am Video-Gästebuch aufgenommene Video anzusehen, herunter-
zuladen oder per WhatsApp zu teilen. **Kein Internet nötig.**

## Betriebsmodi

| Modus | Beschreibung | Umschalten |
|---|---|---|
| **AP** (Default) | Offenes WLAN `Video_GB`, nginx auf `192.168.4.1` | `switch-mode ap` |
| **USB** | Pi als USB-Massenspeicher am Windows-PC (exFAT `VIDEOS`) | `switch-mode usb` |
| **Wartung** | SSH über AP (`ssh pi@192.168.4.1`) | – |

Der USB-Modus kennt zwei Schreibschutz-Zustände:

| Zustand | Bedeutung | Wer darf schreiben |
|---|---|---|
| **Read-only** (`ro=1`) | Windows sieht das Laufwerk als schreibgeschützt | niemand (Kunden-Modus) |
| **Beschreibbar** (`ro=0`) | Windows sieht das Laufwerk wie eine normale USB-Festplatte | Admin zum Aufspielen |

Hardware-Umschaltung optional per GPIO 17 Taster oder Schiebeschalter GPIO 5 (AP) / GPIO 6 (USB) gegen GND. Schreibschutz per GPIO 26 gegen GND (Admin) bzw. offen/HIGH (Kunde).

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

## Videos aufspielen

1. `sudo switch-mode usb` (oder Schalter auf USB).
2. Pi per USB-Kabel (Port **USB**, nicht **PWR**) an Windows anschließen.
3. Laufwerk `VIDEOS` erscheint. Videos in Ordner-Struktur ablegen:

   ```
   VIDEOS:\<event-slug>\<event-slug>_TT_MM_JJJJ_HH_MM_SS_PIN.mp4
   ```

   Beispiel: `hochzeit-mueller\hochzeit-mueller_06_07_2026_18_42_11_4711.mp4`

4. Sicher trennen, `sudo switch-mode ap`.
5. Datenpartition wird automatisch nach `/srv/videos/` gemountet
   (siehe fstab-Eintrag; falls nicht: siehe unten „Schreibschutz").
6. Optional: `sudo pi-lock-videos` gegen versehentliches Ändern.

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

- `sudo pi-lock-videos` setzt `chmod 0444` + `chattr +i` (funktioniert auf ext4).
- `sudo pi-unlock-videos` macht es rückgängig.
- Auf **exFAT** wirken `chattr`/`chmod` nicht. Zwei Strategien:
  - **Einfach**: In `pi/switch-mode.sh` `GADGET_RO=1` setzen. Windows sieht das Laufwerk dann read-only – kein Löschen, keine Umbenennung möglich.
  - **Robust**: Videos nach dem Kopieren zusätzlich in `/srv/videos` (ext4) belassen (statt exFAT direkt zu servieren) und dort locken.

Der Default in `nginx.conf` liest aus `/srv/videos/` – wenn du die exFAT-Partition dort hin mountest, ist beides erreichbar.

## Skripte

| Pfad nach Install | Zweck |
|---|---|
| `/usr/local/sbin/switch-mode` | `ap` / `usb` / `toggle` / `status` |
| `/usr/local/sbin/pi-lock-videos` | Videos immutable + read-only |
| `/usr/local/sbin/pi-unlock-videos` | Aufheben |
| `/usr/local/sbin/gpio-switch.py` | GPIO-Daemon (via systemd) |

Services: `video-token-ap.service` (Boot-Default AP), `video-token-gpio.service` (Taster/Schalter).

## Hinweise

- Pi Zero W: nur ein WLAN-Chip. Im AP-Modus keine Internet-Verbindung – gewollt.
- `wpa_supplicant` wird deaktiviert, damit `hostapd` `wlan0` exklusiv nutzt.
- USB-Gadget funktioniert nur am **USB**-Port des Pi (der Port näher an der Mitte), nicht am `PWR`-Port.
- Für iOS-Seek (Range-Requests) sind `Accept-Ranges: bytes` und `mp4`-MIME in `nginx.conf` gesetzt.
