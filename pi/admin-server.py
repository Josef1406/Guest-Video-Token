#!/usr/bin/env python3
"""
Guest_Video_Token – Admin-API (PIN-geschützt)
Läuft auf 127.0.0.1:8080, nginx proxied /api/admin/ hierher.
Endpunkte:
  POST /api/admin/login   {"pin": "1234"}   -> setzt Session-Cookie
  GET  /api/admin/status                     -> JSON (nur mit Cookie)
"""
import json, os, re, subprocess, secrets, time, shutil, hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
from http.cookies import SimpleCookie

PIN_FILE      = "/etc/video-token/admin.pin"
MODE_FILE     = "/var/lib/video-token/mode"
VIDEO_ROOT    = "/srv/videos"
SESSION_TTL   = 3600  # 1h
SESSIONS: dict[str, float] = {}

def load_pin() -> str:
    try:
        with open(PIN_FILE) as f:
            return f.read().strip()
    except FileNotFoundError:
        return "1234"

def gc_sessions():
    now = time.time()
    for k, t in list(SESSIONS.items()):
        if t < now:
            SESSIONS.pop(k, None)

def is_authed(headers) -> bool:
    gc_sessions()
    raw = headers.get("Cookie", "")
    if not raw: return False
    c = SimpleCookie(); c.load(raw)
    if "vt_admin" not in c: return False
    return c["vt_admin"].value in SESSIONS

# --- Status-Sammler --------------------------------------------------------

def get_mode() -> str:
    try:
        with open(MODE_FILE) as f: return f.read().strip()
    except Exception: return "unknown"

def get_events():
    events = []
    if not os.path.isdir(VIDEO_ROOT):
        return events
    for name in sorted(os.listdir(VIDEO_ROOT)):
        p = os.path.join(VIDEO_ROOT, name)
        if not os.path.isdir(p): continue
        files = [f for f in os.listdir(p) if f.lower().endswith(".mp4")]
        size  = sum(os.path.getsize(os.path.join(p, f)) for f in files if os.path.isfile(os.path.join(p, f)))
        events.append({"name": name, "count": len(files), "bytes": size})
    return events

def get_disk():
    target = VIDEO_ROOT if os.path.exists(VIDEO_ROOT) else "/"
    total, used, free = shutil.disk_usage(target)
    return {"total": total, "used": used, "free": free, "path": target}

def get_lock_state():
    """Ermittelt Schreibschutz-Status der Videos.
    Rückgabe: {"locked": bool|None, "detail": str, "fs": str}
    """
    fs = "unknown"
    try:
        out = subprocess.check_output(
            ["findmnt", "-n", "-o", "FSTYPE", "--target", VIDEO_ROOT],
            stderr=subprocess.DEVNULL, timeout=2
        ).decode().strip()
        if out: fs = out
    except Exception:
        pass
    sample = None
    try:
        for ev in os.listdir(VIDEO_ROOT):
            p = os.path.join(VIDEO_ROOT, ev)
            if not os.path.isdir(p): continue
            for f in os.listdir(p):
                if f.lower().endswith(".mp4"):
                    sample = os.path.join(p, f); break
            if sample: break
    except FileNotFoundError:
        return {"locked": None, "detail": "Video-Verzeichnis fehlt", "fs": fs}
    if not sample:
        return {"locked": None, "detail": "Keine Videos vorhanden", "fs": fs}
    mode = os.stat(sample).st_mode
    writable = bool(mode & 0o200)
    immutable = False
    try:
        out = subprocess.check_output(["lsattr", "-d", sample],
            stderr=subprocess.DEVNULL, timeout=2).decode()
        immutable = "i" in out.split()[0] if out.strip() else False
    except Exception:
        pass
    locked = (not writable) or immutable
    detail = []
    if immutable: detail.append("chattr +i")
    detail.append("0444" if not writable else "0644")
    return {"locked": locked, "detail": " · ".join(detail), "fs": fs}

_MAC_RE = re.compile(r"([0-9a-f]{2}(?::[0-9a-f]{2}){5})", re.I)
_IP_RE  = re.compile(r"^\s*(\d+\.\d+\.\d+\.\d+)\s+([0-9a-f:]{17})", re.I | re.M)

def get_clients():
    """Verbundene WLAN-Clients (im AP-Mode via hostapd + dnsmasq leases)."""
    clients = {}
    # hostapd assoziierte Stationen
    try:
        out = subprocess.check_output(
            ["hostapd_cli", "-i", "wlan0", "all_sta"],
            stderr=subprocess.DEVNULL, timeout=2
        ).decode("utf-8", "ignore")
        for m in _MAC_RE.finditer(out):
            mac = m.group(1).lower()
            clients.setdefault(mac, {"mac": mac, "ip": None, "hostname": None})
    except Exception:
        pass
    # dnsmasq leases (IP + Hostname)
    for lease_path in ("/var/lib/misc/dnsmasq.leases", "/var/lib/dnsmasq/dnsmasq.leases"):
        try:
            with open(lease_path) as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 4:
                        _, mac, ip, host = parts[0], parts[1].lower(), parts[2], parts[3]
                        c = clients.setdefault(mac, {"mac": mac, "ip": None, "hostname": None})
                        c["ip"] = ip
                        c["hostname"] = host if host != "*" else None
        except FileNotFoundError:
            continue
    return list(clients.values())

def build_status():
    events = get_events()
    return {
        "mode":       get_mode(),
        "hostname":   os.uname().nodename,
        "events":     events,
        "video_count": sum(e["count"] for e in events),
        "clients":    get_clients(),
        "disk":       get_disk(),
        "lock":       get_lock_state(),
        "timestamp":  int(time.time()),
    }


# --- HTTP-Handler ----------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    def _json(self, code, obj, cookie=None):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if cookie: self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):  # ruhiger
        pass

    def do_POST(self):
        if self.path == "/api/admin/login":
            n = int(self.headers.get("Content-Length", "0") or "0")
            try: data = json.loads(self.rfile.read(n) or b"{}")
            except Exception: data = {}
            pin = str(data.get("pin", ""))
            if hmac.compare_digest(pin, load_pin()):
                tok = secrets.token_urlsafe(24)
                SESSIONS[tok] = time.time() + SESSION_TTL
                cookie = f"vt_admin={tok}; Path=/; HttpOnly; SameSite=Strict; Max-Age={SESSION_TTL}"
                return self._json(200, {"ok": True}, cookie=cookie)
            time.sleep(0.5)
            return self._json(401, {"ok": False, "error": "invalid pin"})
        if self.path == "/api/admin/logout":
            raw = self.headers.get("Cookie", "")
            c = SimpleCookie(); c.load(raw) if raw else None
            if "vt_admin" in c: SESSIONS.pop(c["vt_admin"].value, None)
            return self._json(200, {"ok": True}, cookie="vt_admin=; Path=/; Max-Age=0")
        if self.path in ("/api/admin/lock", "/api/admin/unlock"):
            if not is_authed(self.headers):
                return self._json(401, {"error": "unauthorized"})
            script = "/usr/local/sbin/pi-lock-videos" if self.path.endswith("/lock") \
                     else "/usr/local/sbin/pi-unlock-videos"
            try:
                r = subprocess.run([script], capture_output=True, text=True, timeout=30)
                ok = r.returncode == 0
                return self._json(200 if ok else 500, {
                    "ok": ok, "stdout": r.stdout[-2000:], "stderr": r.stderr[-2000:],
                    "lock": get_lock_state(),
                })
            except Exception as e:
                return self._json(500, {"ok": False, "error": str(e)})
        self._json(404, {"error": "not found"})

    def do_GET(self):
        if self.path == "/api/admin/status":
            if not is_authed(self.headers):
                return self._json(401, {"error": "unauthorized"})
            return self._json(200, build_status())
        self._json(404, {"error": "not found"})

def main():
    HTTPServer(("127.0.0.1", 8080), Handler).serve_forever()

if __name__ == "__main__":
    main()
