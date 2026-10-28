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
# normal = Cloud-QR per Foto lesen, cloud = Cloud-Seite leitet weiter,
# local = QR mit http://192.168.4.1 gedruckt, https = Zertifikat (alt).
MODES = ("normal", "cloud", "local", "https")


def load_mode():
    try:
        data = json.loads(CONFIG_FILE.read_text())
        if data.get("mode") in MODES:
            return data["mode"]
    except (OSError, ValueError, AttributeError):
        pass
    return "normal"


def save_mode(mode):
    if mode not in MODES:
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
    apply_dns(mode)
    return status()


HTTPS_DNS_FILE = Path("/etc/dnsmasq.d/video-token-https.conf")


def apply_dns(mode):
    """Only the certificate mode answers the cloud domain locally. In normal
    mode the phone resolves it via mobile data and the cloud page redirects
    to http://192.168.4.1/v/..."""
    try:
        if mode == "https":
            HTTPS_DNS_FILE.write_text(f"address=/{DOMAIN}/192.168.4.1\n")
        elif HTTPS_DNS_FILE.exists():
            HTTPS_DNS_FILE.unlink()
        else:
            return
        subprocess.run(["systemctl", "restart", "dnsmasq"], capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        pass


def status():
    mode = load_mode()
    from certificate_bridge import certificate_status
    return {
        "mode": mode,
        "base_url": f"https://{DOMAIN}" if mode == "https" else "http://192.168.4.1",
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