#!/usr/bin/env python3
"""Guest_Video_Token GPIO-Daemon.

Unterstützt:
- Taster an GPIO 17 (pull-up, Druck gegen GND) -> Modus umschalten
- Optionaler Schiebeschalter GPIO 5 (AP) / GPIO 6 (USB) gegen GND
"""
import subprocess
import time
from gpiozero import Button

SWITCH_CMD = "/usr/local/sbin/switch-mode"

def run(mode: str) -> None:
    try:
        subprocess.run([SWITCH_CMD, mode], check=False)
    except Exception as e:  # noqa: BLE001
        print(f"switch-mode failed: {e}", flush=True)

def on_button():
    print("Taster: toggle", flush=True)
    run("toggle")

def on_ap():
    print("Schiebeschalter: AP", flush=True)
    run("ap")

def on_usb():
    print("Schiebeschalter: USB", flush=True)
    run("usb")

def main() -> None:
    btn = Button(17, pull_up=True, bounce_time=0.05)
    btn.when_pressed = on_button

    try:
        ap_pin = Button(5, pull_up=True, bounce_time=0.1)
        usb_pin = Button(6, pull_up=True, bounce_time=0.1)
        ap_pin.when_pressed = on_ap
        usb_pin.when_pressed = on_usb
        # Initial-Zustand anwenden
        if ap_pin.is_pressed and not usb_pin.is_pressed:
            on_ap()
        elif usb_pin.is_pressed and not ap_pin.is_pressed:
            on_usb()
    except Exception as e:  # noqa: BLE001
        print(f"Schiebeschalter nicht verfügbar: {e}", flush=True)

    print("GPIO-Daemon läuft. Ctrl+C zum Beenden.", flush=True)
    while True:
        time.sleep(3600)

if __name__ == "__main__":
    main()
