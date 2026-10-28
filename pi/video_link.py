"""Persistent video-link selection; certificate issuance is not configured yet.

This setting is intentionally independent of the AP/client boot-mode file.
Private keys never leave the Pi. Only authenticated admins may request a CSR.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading

DOMAIN = "video.gaestebuch.cloud"
CONFIG_FILE = Path("/etc/video-token/video-link.json")
TLS_DIR = Path("/etc/video-token/tls")
LOCK = threading.Lock()


def load_mode():
    try:
        data = json.loads(CONFIG_FILE.read_text())
        if data.get("mode") in ("normal", "https"):
            return data["mode"]
    except (OSError, ValueError, AttributeError):
        pass
    return "normal"


def save_mode(mode):
    if mode not in ("normal", "https"):
        raise ValueError("Ungültiger Video-Link-Modus")
    with LOCK:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(dir=CONFIG_FILE.parent, prefix=".video-link-")
        try:
            with os.fdopen(fd, "w") as handle:
                json.dump({"mode": mode}, handle)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, CONFIG_FILE)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return status()


def status():
    mode = load_mode()
    from certificate_bridge import certificate_status
    return {
        "mode": mode,
        "base_url": "http://192.168.4.1" if mode == "normal" else f"https://{DOMAIN}",
        "certificate": certificate_status() if mode == "https" else None,
    }


def prepare_csr():
    if load_mode() != "https":
        raise ValueError("Zertifikatsanfragen sind nur im HTTPS-Modus verfügbar")
    with LOCK:
        TLS_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(TLS_DIR, 0o700)
        key = TLS_DIR / "device.key"
        if not key.exists():
            fd, temporary = tempfile.mkstemp(dir=TLS_DIR, prefix=".key-")
            os.close(fd)
            try:
                subprocess.run(["openssl", "genpkey", "-algorithm", "EC", "-pkeyopt",
                                "ec_paramgen_curve:P-256", "-out", temporary],
                               check=True, capture_output=True, timeout=30)
                os.chmod(temporary, 0o600)
                os.replace(temporary, key)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        os.chmod(key, 0o600)
        result = subprocess.run(
            ["openssl", "req", "-new", "-key", str(key), "-subj", f"/CN={DOMAIN}",
             "-addext", f"subjectAltName=DNS:{DOMAIN}"],
            check=True, capture_output=True, text=True, timeout=30)
        return {"domain": DOMAIN, "csr": result.stdout,
                "state": "prepared", "certificate_ready": False}