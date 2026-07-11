#!/usr/bin/env python3
"""
Guest_Video_Token – Admin- und Public-API
Läuft auf 127.0.0.1:8080, nginx proxied /api/admin/ und /api/public/ hierher.

Admin (PIN-geschützt via Cookie):
  POST /api/admin/login              {"pin":"1234"}
  POST /api/admin/logout
  GET  /api/admin/status
  POST /api/admin/lock | /unlock
  POST /api/admin/event/<name>       Event-Verzeichnis anlegen
  DELETE /api/admin/event/<name>     Event komplett löschen (rekursiv)
  PUT  /api/admin/upload/<event>/<file.mp4>   Body = MP4-Bytes (streamed)
  DELETE /api/admin/file/<event>/<file>       Einzelnes Video löschen

Public (offen, read-only):
  GET  /api/public/events            Liste aller Events + Videos
"""
import json, os, re, subprocess, secrets, time, shutil, hmac, shlex
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
from urllib.parse import unquote

PIN_FILE      = "/etc/video-token/admin.pin"
MODE_FILE     = "/var/lib/video-token/mode"
VIDEO_ROOT    = "/srv/videos"
SESSION_TTL   = 3600
SESSIONS: dict[str, float] = {}

SAFE_NAME = re.compile(r"^[A-Za-z0-9._\- ]{1,120}$")

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

def safe_component(name: str) -> str | None:
    """Ordner- oder Dateiname absichern: keine Slashes, keine '..'."""
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        return None
    if not SAFE_NAME.match(name):
        return None
    return name

# --- Status ---------------------------------------------------------------

def get_mode() -> str:
    try:
        with open(MODE_FILE) as f: return f.read().strip()
    except Exception: return "ap"

def list_events():
    events = []
    if not os.path.isdir(VIDEO_ROOT):
        return events
    for name in sorted(os.listdir(VIDEO_ROOT)):
        p = os.path.join(VIDEO_ROOT, name)
        if not os.path.isdir(p): continue
        videos = []
        try:
            for f in sorted(os.listdir(p)):
                fp = os.path.join(p, f)
                if os.path.isfile(fp) and f.lower().endswith(".mp4"):
                    videos.append({
                        "name": f,
                        "size": os.path.getsize(fp),
                        "url":  f"/media/{name}/{f}",
                        "play": f"/v/{name}/{f}",
                    })
        except PermissionError:
            pass
        events.append({
            "name": name,
            "count": len(videos),
            "bytes": sum(v["size"] for v in videos),
            "videos": videos,
        })
    return events

def get_disk():
    target = VIDEO_ROOT if os.path.exists(VIDEO_ROOT) else "/"
    total, used, free = shutil.disk_usage(target)
    return {"total": total, "used": used, "free": free, "path": target}

def get_lock_state():
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

def get_clients():
    clients = {}
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
    events = list_events()
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

# --- HTTP ------------------------------------------------------------------

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

    def log_message(self, fmt, *args):
        pass

    # ---- POST ----
    def do_POST(self):
        path = self.path.split("?", 1)[0]

        if path == "/api/admin/login":
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

        if path == "/api/admin/logout":
            raw = self.headers.get("Cookie", "")
            c = SimpleCookie()
            if raw: c.load(raw)
            if "vt_admin" in c: SESSIONS.pop(c["vt_admin"].value, None)
            return self._json(200, {"ok": True}, cookie="vt_admin=; Path=/; Max-Age=0")

        if not is_authed(self.headers):
            return self._json(401, {"error": "unauthorized"})

        if path in ("/api/admin/lock", "/api/admin/unlock"):
            script = "/usr/local/sbin/pi-lock-videos" if path.endswith("/lock") \
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

        # POST /api/admin/event/<name> -> Event anlegen
        m = re.match(r"^/api/admin/event/([^/]+)$", path)
        if m:
            name = safe_component(unquote(m.group(1)))
            if not name:
                return self._json(400, {"error": "invalid event name"})
            os.makedirs(os.path.join(VIDEO_ROOT, name), exist_ok=True)
            return self._json(200, {"ok": True, "name": name})

        return self._json(404, {"error": "not found"})

    # ---- PUT ---- (Upload)
    def do_PUT(self):
        if not is_authed(self.headers):
            return self._json(401, {"error": "unauthorized"})
        m = re.match(r"^/api/admin/upload/([^/]+)/([^/]+)$", self.path)
        if not m:
            return self._json(404, {"error": "not found"})
        ev = safe_component(unquote(m.group(1)))
        fn = safe_component(unquote(m.group(2)))
        if not ev or not fn or not fn.lower().endswith(".mp4"):
            return self._json(400, {"error": "invalid event/filename (must end .mp4)"})
        n = int(self.headers.get("Content-Length", "0") or "0")
        if n <= 0:
            return self._json(400, {"error": "empty body"})
        # Speicherplatz-Check
        free = shutil.disk_usage(VIDEO_ROOT).free
        if n > free - 50 * 1024 * 1024:
            return self._json(507, {"error": "not enough disk space"})
        os.makedirs(os.path.join(VIDEO_ROOT, ev), exist_ok=True)
        dst = os.path.join(VIDEO_ROOT, ev, fn)
        tmp = dst + ".part"
        remaining = n
        try:
            with open(tmp, "wb") as f:
                while remaining > 0:
                    chunk = self.rfile.read(min(1024 * 1024, remaining))
                    if not chunk: break
                    f.write(chunk)
                    remaining -= len(chunk)
            if remaining != 0:
                os.remove(tmp)
                return self._json(400, {"error": "short upload"})
            os.replace(tmp, dst)
            os.chmod(dst, 0o664)
        except Exception as e:
            try: os.remove(tmp)
            except Exception: pass
            return self._json(500, {"error": str(e)})
        return self._json(200, {"ok": True, "event": ev, "file": fn, "size": n})

    # ---- DELETE ----
    def do_DELETE(self):
        if not is_authed(self.headers):
            return self._json(401, {"error": "unauthorized"})
        # Datei
        m = re.match(r"^/api/admin/file/([^/]+)/([^/]+)$", self.path)
        if m:
            ev = safe_component(unquote(m.group(1)))
            fn = safe_component(unquote(m.group(2)))
            if not ev or not fn:
                return self._json(400, {"error": "invalid path"})
            fp = os.path.join(VIDEO_ROOT, ev, fn)
            if not os.path.isfile(fp):
                return self._json(404, {"error": "not found"})
            try:
                # Falls immutable, aufheben
                subprocess.run(["chattr", "-i", fp], capture_output=True, timeout=5)
                os.remove(fp)
            except Exception as e:
                return self._json(500, {"error": str(e)})
            return self._json(200, {"ok": True})
        # Event
        m = re.match(r"^/api/admin/event/([^/]+)$", self.path)
        if m:
            ev = safe_component(unquote(m.group(1)))
            if not ev:
                return self._json(400, {"error": "invalid event"})
            p = os.path.join(VIDEO_ROOT, ev)
            if not os.path.isdir(p):
                return self._json(404, {"error": "not found"})
            try:
                subprocess.run(["chattr", "-R", "-i", p], capture_output=True, timeout=10)
                shutil.rmtree(p)
            except Exception as e:
                return self._json(500, {"error": str(e)})
            return self._json(200, {"ok": True})
        return self._json(404, {"error": "not found"})

    # ---- GET ----
    def do_GET(self):
        if self.path == "/api/admin/status":
            if not is_authed(self.headers):
                return self._json(401, {"error": "unauthorized"})
            return self._json(200, build_status())
        if self.path == "/api/public/events":
            # Öffentlich lesbare Event-Liste für die Startseite
            return self._json(200, {"events": list_events()})
        self._json(404, {"error": "not found"})

def main():
    ThreadingHTTPServer(("127.0.0.1", 8080), Handler).serve_forever()

if __name__ == "__main__":
    main()
