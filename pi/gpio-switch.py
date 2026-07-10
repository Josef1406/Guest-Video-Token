#!/usr/bin/env python3
"""Guest_Video_Token GPIO-Daemon.

Belegte GPIOs (BCM-Nummerierung, alle gegen GND, intern pull-up):
- GPIO 17 : Taster        -> Modus umschalten (AP <-> USB)
- GPIO  5 : Schiebeschalter Position "AP"  (optional)
- GPIO  6 : Schiebeschalter Position "USB" (optional)
- GPIO 27 : Doppelfunktion
     * Beim Boot LOW -> Client-Modus (Pi verbindet sich mit Heim-WLAN,
       siehe boot-mode.sh). Prüfung erfolgt EINMAL beim Boot.
     * Zur Laufzeit  -> Schreibschutz-Schalter für den USB-Gadget:
       offen / HIGH  -> ro=1  (Kunden-Modus: nur lesen)
             gegen GND / LOW -> ro=0 (Admin-Modus: Videos aufspielen)
"""
import subprocess
import time
from pathlib import Path

from gpiozero import Button

SWITCH_CMD = "/usr/local/sbin/switch-mode"
RO_FILE = Path("/var/lib/video-token/gadget_ro")

def run(*args: str) -> None:
    try:
        subprocess.run([SWITCH_CMD, *args], check=False)
    except Exception as e:  # noqa: BLE001
        print(f"switch-mode failed: {e}", flush=True)

def set_ro(ro: int) -> None:
    """Schreibt gewünschten ro-Wert und lässt USB-Gadget ggf. neu laden."""
    try:
        RO_FILE.parent.mkdir(parents=True, exist_ok=True)
        RO_FILE.write_text(f"{ro}\n")
        print(f"Schreibschutz gesetzt: ro={ro}", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"gadget_ro konnte nicht geschrieben werden: {e}", flush=True)
    run("reapply")

def on_button():
    print("Taster: toggle", flush=True)
    run("toggle")

def on_ap():
    print("Schiebeschalter: AP", flush=True)
    run("ap")

def on_usb():
    print("Schiebeschalter: USB", flush=True)
    run("usb")

def on_wp_locked():
    # GPIO 26 offen / HIGH -> Button ist "released" (pull-up aktiv)
    print("Write-Protect-Schalter: LOCKED (Kunden-Modus)", flush=True)
    set_ro(1)

def on_wp_unlocked():
    # GPIO 26 gegen GND -> Button ist "pressed"
    print("Write-Protect-Schalter: UNLOCKED (Admin-Modus)", flush=True)
    set_ro(0)

def main() -> None:
    btn = Button(17, pull_up=True, bounce_time=0.05)
    btn.when_pressed = on_button

    try:
        ap_pin = Button(5, pull_up=True, bounce_time=0.1)
        usb_pin = Button(6, pull_up=True, bounce_time=0.1)
        ap_pin.when_pressed = on_ap
        usb_pin.when_pressed = on_usb
        if ap_pin.is_pressed and not usb_pin.is_pressed:
            on_ap()
        elif usb_pin.is_pressed and not ap_pin.is_pressed:
            on_usb()
    except Exception as e:  # noqa: BLE001
        print(f"Schiebeschalter nicht verfügbar: {e}", flush=True)

    # Schreibschutz-Schalter (GPIO 27). Optional: wenn Pin nicht verdrahtet,
    # bleibt der Default aus /var/lib/video-token/gadget_ro erhalten.
    # Hinweis: Beim Boot wird derselbe Pin von boot-mode.sh gelesen und
    # entscheidet dort über Client-Modus vs. Normal-Modus.
    try:
        wp_pin = Button(27, pull_up=True, bounce_time=0.1)
        wp_pin.when_pressed  = on_wp_unlocked   # gegen GND -> Admin/beschreibbar
        wp_pin.when_released = on_wp_locked     # offen     -> Kunde/read-only
        # Startzustand anwenden
        if wp_pin.is_pressed:
            on_wp_unlocked()
        else:
            on_wp_locked()
    except Exception as e:  # noqa: BLE001
        print(f"Write-Protect-Schalter nicht verfügbar: {e}", flush=True)

    print("GPIO-Daemon läuft. Ctrl+C zum Beenden.", flush=True)
    while True:
        time.sleep(3600)

if __name__ == "__main__":
    main()
