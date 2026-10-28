#!/usr/bin/env python3
"""Software-Update-Pakete für den Video-Token: prüfen, entpacken, installieren.

Ein Paket kommt von der Admin-Seite, die die Dateien direkt von GitHub lädt
(JSON: {"sha": "<commit>", "files": {"<pfad>": {"b64": "...", "sha": "<git-blob-sha>"}}}).
Erlaubt sind ausschließlich Dateien unter web/ (Webseiten) und pi/ (Skripte,
Konfigurationen, systemd-Units). Videos, Admin-PIN, Upload-Secret und die
WLAN-Einstellungen bleiben von einem Update unberührt.

Die Ziel-Pfade entsprechen pi/install.sh; mit dest_root (nur für Tests)
werden alle Ziele unter ein Wurzelverzeichnis geschrieben.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import shutil
import time

UPDATE_DIR = "/var/lib/video-token/update"
VERSION_FILE = "/var/lib/video-token/installed-version.json"

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TOTAL_BYTES = 30 * 1024 * 1024
MAX_FILES = 2000

SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9._\-]+$")
ALLOWED_ROOTS = ("web/", "pi/")
REQUIRED_PATHS = ("web/index.html", "pi/admin-server.py")

WEB_DEST = "/var/www/video-token"
SYSTEMD_DEST = "/etc/systemd/system"

PI_INSTALL = {
    "pi/admin-server.py": ("/usr/local/sbin/admin-server.py", 0o755),
    "pi/video_link.py": ("/usr/local/sbin/video_link.py", 0o644),
    "pi/switch-mode.sh": ("/usr/local/sbin/switch-mode", 0o755),
    "pi/pi-lock-videos.sh": ("/usr/local/sbin/pi-lock-videos", 0o755),
    "pi/pi-unlock-videos.sh": ("/usr/local/sbin/pi-unlock-videos", 0o755),
    "pi/boot-mode.sh": ("/usr/local/sbin/video-token-bootmode", 0o755),
}
CONFIG_INSTALL = {
    "pi/config/hostapd.conf": "/etc/hostapd/hostapd.conf",
    "pi/config/dnsmasq.conf": "/etc/dnsmasq.d/video-token.conf",
    "pi/config/nginx.conf": "/etc/nginx/sites-available/video-token",
    "pi/config/wpa_supplicant-client.conf.example":
        "/etc/wpa_supplicant/wpa_supplicant-client.conf.example",
}
WEB_OWNER = "www-data"


class PackageError(ValueError):
    """Das Update-Paket ist ungültig oder unvollständig."""


def git_blob_sha(data: bytes) -> str:
    """Git-Blob-Prüfsumme (sha1), wie sie die GitHub-Tree-API liefert."""
    return hashlib.sha1(b"blob %d\x00" % len(data) + data).hexdigest()


def _clean_relpath(path: str) -> str:
    if not isinstance(path, str) or not path or "\\" in path:
        raise PackageError("Ungültiger Dateipfad im Paket.")
    if path.startswith("/") or any(part in ("", ".", "..") for part in path.split("/")):
        raise PackageError("Ungültiger Dateipfad im Paket: " + path[:80])
    for part in path.split("/"):
        if not SAFE_COMPONENT.match(part):
            raise PackageError("Ungültiger Dateiname im Paket: " + path[:80])
    return path


def build_staging(payload: object, staging_dir: str) -> dict:
    """Prüft das Paket und schreibt die erlaubten Dateien nach staging_dir.

    Bei jedem Fehler wird das Zielverzeichnis wieder entfernt.
    """
    if not isinstance(payload, dict):
        raise PackageError("Ungültiges Paket.")
    files = payload.get("files")
    if not isinstance(files, dict) or not files:
        raise PackageError("Das Paket enthält keine Dateien.")
    if len(files) > MAX_FILES:
        raise PackageError("Das Paket enthält zu viele Dateien.")
    commit = payload.get("sha")
    if commit is not None and (
        not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{7,64}", commit)
    ):
        raise PackageError("Ungültige Commit-Angabe im Paket.")

    kept: dict[str, bytes] = {}
    ignored: list[str] = []
    total = 0
    for path, entry in files.items():
        rel = _clean_relpath(path)
        if not rel.startswith(ALLOWED_ROOTS) or "__pycache__/" in rel:
            ignored.append(rel)
            continue
        if not isinstance(entry, dict) or not isinstance(entry.get("b64"), str):
            raise PackageError("Ungültiger Dateiinhalt: " + rel)
        try:
            data = base64.b64decode(entry["b64"], validate=True)
        except (binascii.Error, ValueError):
            raise PackageError("Beschädigter Dateiinhalt: " + rel)
        if len(data) > MAX_FILE_BYTES:
            raise PackageError("Datei zu groß: " + rel)
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise PackageError("Das Paket ist zu groß.")
        expected = entry.get("sha")
        if isinstance(expected, str) and expected and expected != git_blob_sha(data):
            raise PackageError("Inhalt passt nicht zur GitHub-Prüfsumme: " + rel)
        kept[rel] = data

    for required in REQUIRED_PATHS:
        if required not in kept:
            raise PackageError(
                "Das Paket sieht nicht nach einem Video-Token-Update aus "
                "(es fehlt " + required + ")."
            )

    os.makedirs(staging_dir, exist_ok=True)
    try:
        for rel, data in kept.items():
            dst = os.path.join(staging_dir, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "wb") as f:
                f.write(data)
            os.chmod(dst, 0o644)
    except Exception:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise
    web_count = sum(1 for p in kept if p.startswith("web/"))
    return {
        "commit": commit,
        "files": len(kept),
        "web_files": web_count,
        "pi_files": len(kept) - web_count,
        "ignored": ignored[:20],
    }


def _file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _chown_owner(path: str, owner: str) -> None:
    try:
        shutil.chown(path, owner, owner)
    except (LookupError, OSError):
        pass


def apply(staging_dir: str, dest_root: str = "") -> dict:
    """Installiert die gestagten Dateien an die im Installer üblichen Ziele.

    Dateien, die vor dem Update schon existierten, werden gesichert und bei
    einem Fehler während der Installation wiederhergestellt (Rollback).
    """
    def d(p: str) -> str:
        return os.path.join(dest_root, p.lstrip("/")) if dest_root else p

    web_src = os.path.join(staging_dir, "web")
    if not os.path.isdir(web_src):
        raise PackageError("Paket enthält web/ nicht mehr.")

    plan: list[tuple[str, str, int, str | None, str]] = []
    for root, _dirs, names in os.walk(web_src):
        for name in names:
            src = os.path.join(root, name)
            target = os.path.join(WEB_DEST, os.path.relpath(src, web_src))
            plan.append((src, d(target), 0o644, WEB_OWNER, target))
    for rel, (target, mode) in PI_INSTALL.items():
        src = os.path.join(staging_dir, rel)
        if not os.path.isfile(src):
            if rel == REQUIRED_PATHS[1]:
                raise PackageError("Paket enthält " + rel + " nicht mehr.")
            continue
        plan.append((src, d(target), mode, None, target))
    for rel, target in CONFIG_INSTALL.items():
        src = os.path.join(staging_dir, rel)
        if os.path.isfile(src):
            plan.append((src, d(target), 0o644, None, target))
    systemd_src = os.path.join(staging_dir, "pi", "systemd")
    if os.path.isdir(systemd_src):
        for root, _dirs, names in os.walk(systemd_src):
            for name in names:
                src = os.path.join(root, name)
                rel = os.path.relpath(src, systemd_src)
                target = os.path.join(SYSTEMD_DEST, rel)
                plan.append((src, d(target), 0o644, None, target))

    skipped: list[str] = []
    pi_src = os.path.join(staging_dir, "pi")
    for root, _dirs, names in os.walk(pi_src):
        for name in names:
            src = os.path.join(root, name)
            rel = os.path.relpath(src, staging_dir)
            if (rel in PI_INSTALL or rel in CONFIG_INSTALL
                    or rel.startswith("pi/systemd/")):
                continue
            skipped.append(rel)

    backup: dict[str, tuple[bool, bytes | None, int | None]] = {}
    try:
        for _src, dst, _mode, _owner, _target in plan:
            existed = os.path.isfile(dst)
            old = None
            old_mode = None
            if existed:
                with open(dst, "rb") as f:
                    old = f.read()
                old_mode = os.stat(dst).st_mode & 0o777
            backup[dst] = (existed, old, old_mode)
        for src, dst, mode, owner, _target in plan:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, dst)
            os.chmod(dst, mode)
            if owner:
                _chown_owner(dst, owner)
    except Exception:
        for dst, (existed, old, old_mode) in backup.items():
            if existed and old is not None:
                with open(dst, "wb") as f:
                    f.write(old)
                if old_mode is not None:
                    os.chmod(dst, old_mode)
            elif not existed:
                try:
                    os.remove(dst)
                except OSError:
                    pass
        raise

    changed_set: set[str] = set()
    unchanged = 0
    for _src, dst, _mode, _owner, target in plan:
        existed, old, _old_mode = backup[dst]
        if existed and old is not None and \
                hashlib.sha256(old).hexdigest() == _file_sha256(dst):
            unchanged += 1
        else:
            changed_set.add(dst)

    changed_targets = [target for _s, dst_p, _m, _o, target in plan
                       if dst_p in changed_set]

    if not dest_root and any(t.startswith("/etc/systemd/")
                             for t in changed_targets):
        import subprocess
        try:
            subprocess.run(["systemctl", "daemon-reload"],
                           capture_output=True, timeout=15)
        except Exception:
            pass

    config_changed = sorted(t for t in changed_targets
                            if t.startswith(("/etc/hostapd/", "/etc/dnsmasq",
                                             "/etc/systemd/")))
    changed = sorted(changed_set if not dest_root
                     else [os.path.relpath(t, dest_root) for t in changed_set])
    return {
        "changed": changed,
        "unchanged_count": unchanged,
        "skipped": sorted(set(skipped))[:20],
        "config_changed": sorted(config_changed),
        "needs_reboot": bool(config_changed),
    }


def save_installed_version(commit: str | None) -> None:
    if not commit:
        return
    os.makedirs(os.path.dirname(VERSION_FILE), exist_ok=True)
    tmp = VERSION_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"commit": commit, "applied_at": int(time.time())}, f)
    os.replace(tmp, VERSION_FILE)


def installed_version() -> dict | None:
    try:
        with open(VERSION_FILE) as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("commit"), str):
            return data
    except Exception:
        pass
    return None


def cleanup_staging(staging_dir: str) -> None:
    shutil.rmtree(staging_dir, ignore_errors=True)
