"""Run the real local handler to enforce PIN protection and mode rules."""
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


class ModeApiRules(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        admin.video_link.CONFIG_FILE = Path(self.tmp.name) / "video-link.json"
        admin.video_link.TLS_DIR = Path(self.tmp.name) / "tls"
        admin.PIN_FILE = str(Path(self.tmp.name) / "admin.pin")
        Path(admin.PIN_FILE).write_text("1234")
        admin.SESSIONS.clear()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), admin.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def request(self, method, path, data=None, cookie=None, origin=None):
        conn = HTTPConnection("127.0.0.1", self.server.server_port)
        headers = {"Content-Type": "application/json"}
        if cookie: headers["Cookie"] = cookie
        if origin: headers["Origin"] = origin
        conn.request(method, path, body=json.dumps(data) if data is not None else None, headers=headers)
        response = conn.getresponse()
        result = response.status, json.loads(response.read()), response.getheader("Set-Cookie")
        conn.close()
        return result

    def login(self):
        code, _, cookie = self.request("POST", "/api/admin/login", {"pin": "1234"})
        self.assertEqual(code, 200)
        return cookie.split(";", 1)[0]

    def test_unsigned_users_cannot_change_mode_or_create_key(self):
        for endpoint in ("/api/admin/video-link", "/api/admin/certificate/prepare"):
            self.assertEqual(self.request("POST", endpoint, {"mode": "https"})[0], 401)
        self.assertEqual(admin.video_link.load_mode(), "normal")
        self.assertFalse(admin.video_link.TLS_DIR.exists())

    def test_pin_admin_can_save_https_then_normal_and_read_public_result(self):
        cookie = self.login()
        for mode, base in (("https", "https://video.gaestebuch.cloud"), ("normal", "http://192.168.4.1")):
            self.assertEqual(self.request("POST", "/api/admin/video-link", {"mode": mode}, cookie)[0], 200)
            code, result, _ = self.request("GET", "/api/public/video-link")
            self.assertEqual(code, 200)
            self.assertEqual(result["base_url"], base)
            self.assertEqual(result["mode"], mode)

    def test_cross_origin_cannot_save_even_with_admin_cookie(self):
        cookie = self.login()
        self.assertEqual(self.request("POST", "/api/admin/video-link", {"mode": "https"}, cookie, "https://evil.example")[0], 403)
        self.assertEqual(admin.video_link.load_mode(), "normal")

    def test_guest_cannot_overwrite_saved_admin_mode(self):
        cookie = self.login()
        self.assertEqual(self.request("POST", "/api/admin/video-link", {"mode": "https"}, cookie)[0], 200)
        self.assertEqual(self.request("POST", "/api/admin/video-link", {"mode": "normal"})[0], 401)
        self.assertEqual(self.request("GET", "/api/public/video-link")[1]["mode"], "https")

    def test_prepare_returns_csr_but_never_certificate_success(self):
        cookie = self.login()
        self.request("POST", "/api/admin/video-link", {"mode": "https"}, cookie)
        code, data, _ = self.request("POST", "/api/admin/certificate/prepare", {}, cookie)
        self.assertEqual(code, 200)
        self.assertFalse(data["certificate_ready"])
        self.assertIn("BEGIN CERTIFICATE REQUEST", data["csr"])
        self.assertNotIn("PRIVATE KEY", json.dumps(data))


if __name__ == "__main__":
    unittest.main()