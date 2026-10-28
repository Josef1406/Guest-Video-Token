"""HTTP-Tests für die Software-Update-Endpunkte des Admin-Servers."""
import base64
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
spec = importlib.util.spec_from_file_location("token_admin", Path(__file__).with_name("admin-server.py"))
admin = importlib.util.module_from_spec(spec)
with patch("os.makedirs"):
    spec.loader.exec_module(admin)

git_blob_sha = admin.update_package.git_blob_sha


def payload(commit: str = "abc1234def5678") -> dict:
    files = {"web/index.html": b"<html>new</html>", "pi/admin-server.py": b"print(1)\n"}
    return {
        "sha": commit,
        "files": {p: {"b64": base64.b64encode(d).decode(), "sha": git_blob_sha(d)}
                  for p, d in files.items()},
    }


class UpdateApiRules(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.updates = Path(self.tmp.name) / "update"
        admin.PIN_FILE = str(Path(self.tmp.name) / "admin.pin")
        Path(admin.PIN_FILE).write_text("1234")
        admin.SESSIONS.clear()
        self.applied = []
        self.saved_versions = []
        self.patchers = [
            patch.object(admin.update_package, "UPDATE_DIR", str(self.updates)),
            patch.object(admin.update_package, "apply",
                         lambda staging, dest_root="": self.applied.append(staging) or {
                             "changed": ["/var/www/video-token/index.html"],
                             "unchanged_count": 1, "skipped": [],
                             "config_changed": [], "needs_reboot": False}),
            patch.object(admin.update_package, "save_installed_version",
                         lambda commit: self.saved_versions.append(commit)),
        ]
        for p in self.patchers:
            p.start()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), admin.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def request(self, method, path, data=None, cookie=None, origin=None, ctype="application/json"):
        conn = HTTPConnection("127.0.0.1", self.server.server_port)
        headers = {"Content-Type": ctype}
        if cookie: headers["Cookie"] = cookie
        if origin: headers["Origin"] = origin
        body = json.dumps(data) if data is not None else None
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        result = response.status, json.loads(response.read())
        conn.close()
        return result

    def login(self):
        code, _, cookie = self.request("POST", "/api/admin/login", {"pin": "1234"})[0:3] \
            if False else (self.request("POST", "/api/admin/login", {"pin": "1234"}))
        self.assertEqual(code, 200)
        return cookie.split(";", 1)[0]

    def test_update_requires_pin(self):
        self.assertEqual(self.request("PUT", "/api/admin/update-payload", payload())[0], 401)
        self.assertEqual(self.applied, [])

    def test_admin_can_install_valid_payload(self):
        cookie = self.login()
        code, result = self.request("PUT", "/api/admin/update-payload", payload(), cookie)
        self.assertEqual(code, 200)
        self.assertTrue(result["ok"])
        self.assertEqual(result["files"], 2)
        self.assertEqual(result["commit"], "abc1234def5678")
        self.assertEqual(len(self.applied), 1)
        staging = Path(self.applied[0])
        self.assertTrue((staging / "web" / "index.html").is_file())
        self.assertTrue((staging / "pi" / "admin-server.py").is_file())
        self.assertEqual(self.saved_versions, ["abc1234def5678"])
        self.assertFalse(self.updates.exists())  # Staging wieder aufgeräumt

    def test_rejects_tampered_payload(self):
        cookie = self.login()
        data = payload()
        data["files"]["web/index.html"]["sha"] = "0" * 40
        code, result = self.request("PUT", "/api/admin/update-payload", data, cookie)
        self.assertEqual(code, 400)
        self.assertIn("Prüfsumme", result["error"])
        self.assertEqual(self.applied, [])

    def test_rejects_foreign_paths(self):
        cookie = self.login()
        data = payload()
        del data["files"]["pi/admin-server.py"]
        code, _ = self.request("PUT", "/api/admin/update-payload", data, cookie)
        self.assertEqual(code, 400)
        self.assertEqual(self.applied, [])

    def test_restart_and_reboot_are_pin_and_origin_protected(self):
        self.assertEqual(self.request("POST", "/api/admin/update/restart")[0], 401)
        cookie = self.login()
        self.assertEqual(
            self.request("POST", "/api/admin/update/restart", None, cookie, "https://evil.example")[0],
            403)
        with patch.object(admin.subprocess, "Popen") as popen:
            self.assertEqual(self.request("POST", "/api/admin/update/restart", None, cookie)[0], 200)
            self.assertEqual(self.request("POST", "/api/admin/reboot", None, cookie)[0], 200)
            self.assertEqual(popen.call_count, 2)
            commands = " | ".join(c.args[0][2] for c in popen.call_args_list)
            self.assertIn("systemctl restart nginx video-token-admin", commands)
            self.assertIn("systemctl reboot", commands)


if __name__ == "__main__":
    unittest.main()
