#!/usr/bin/env python3
"""Tests für pi/update_package.py: Paketprüfung und Installation."""
import base64
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import update_package  # noqa: E402


def payload(files: dict, commit: str = "abc1234def5678") -> dict:
    return {
        "sha": commit,
        "files": {
            path: {"b64": base64.b64encode(data).decode(),
                   "sha": update_package.git_blob_sha(data)}
            for path, data in files.items()
        },
    }


class BuildStagingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.staging = os.path.join(self.tmp.name, "stage")

    def tearDown(self):
        self.tmp.cleanup()

    def test_builds_staging_and_ignores_foreign_paths(self):
        p = payload({
            "web/index.html": b"<html>hi</html>",
            "pi/admin-server.py": b"print('x')\n",
            "README.md": b"ignored",
            "pi/__pycache__/x.pyc": b"ignored",
        })
        info = update_package.build_staging(p, self.staging)
        self.assertTrue(os.path.isfile(os.path.join(self.staging, "web/index.html")))
        self.assertTrue(os.path.isfile(os.path.join(self.staging, "pi/admin-server.py")))
        self.assertFalse(os.path.exists(os.path.join(self.staging, "README.md")))
        self.assertEqual(info["files"], 2)
        self.assertEqual(info["web_files"], 1)
        self.assertEqual(info["pi_files"], 1)
        self.assertEqual(info["commit"], "abc1234def5678")

    def test_rejects_missing_required_file(self):
        p = payload({"web/index.html": b"<html>hi</html>"})
        with self.assertRaises(update_package.PackageError):
            update_package.build_staging(p, self.staging)
        self.assertFalse(os.path.exists(self.staging))

    def test_rejects_path_traversal(self):
        p = payload({
            "web/index.html": b"x",
            "pi/admin-server.py": b"x",
            "../escape.txt": b"evil",
        })
        with self.assertRaises(update_package.PackageError):
            update_package.build_staging(p, self.staging)
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "escape.txt")))

    def test_rejects_wrong_checksum(self):
        p = payload({"web/index.html": b"x", "pi/admin-server.py": b"x"})
        p["files"]["web/index.html"]["sha"] = "0" * 40
        with self.assertRaises(update_package.PackageError):
            update_package.build_staging(p, self.staging)

    def test_rejects_empty_and_oversized(self):
        with self.assertRaises(update_package.PackageError):
            update_package.build_staging({"sha": "abc", "files": {}}, self.staging)
        big = {"web/index.html": b"x", "pi/admin-server.py": b"y",
               "web/big.bin": b"z" * (update_package.MAX_FILE_BYTES + 1)}
        with self.assertRaises(update_package.PackageError):
            update_package.build_staging(payload(big), self.staging)


class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.staging = os.path.join(self.tmp.name, "stage")
        self.dest = os.path.join(self.tmp.name, "dest")
        update_package.build_staging(payload({
            "web/index.html": b"<html>new</html>",
            "web/assets/player.js": b"//player\n",
            "pi/admin-server.py": b"#!/usr/bin/env python3\n",
            "pi/video_link.py": b"# link\n",
            "pi/boot-mode.sh": b"#!/bin/sh\n",
            "pi/config/nginx.conf": b"server {}\n",
            "pi/config/hostapd.conf": b"ssid=Video_GB\n",
            "pi/systemd/video-token-admin.service": b"[Unit]\n",
            "pi/systemd/dnsmasq.service.d/override.conf": b"[Service]\n",
            "pi/install.sh": b"#!/bin/sh\n",
        }), self.staging)

    def tearDown(self):
        self.tmp.cleanup()

    def test_applies_to_expected_targets(self):
        result = update_package.apply(self.staging, dest_root=self.dest)
        admin = os.path.join(self.dest, "usr/local/sbin/admin-server.py")
        web = os.path.join(self.dest, "var/www/video-token/index.html")
        unit = os.path.join(self.dest, "etc/systemd/system/video-token-admin.service")
        nginx = os.path.join(self.dest, "etc/nginx/sites-available/video-token")
        for path in (admin, web, unit, nginx):
            self.assertTrue(os.path.isfile(path), path)
        self.assertEqual(open(admin).read(), "#!/usr/bin/env python3\n")
        self.assertEqual(open(web).read(), "<html>new</html>")
        self.assertEqual(oct(os.stat(admin).st_mode & 0o777), "0o755")
        self.assertEqual(oct(os.stat(web).st_mode & 0o777), "0o644")
        self.assertIn("pi/install.sh", result["skipped"])
        self.assertTrue(result["needs_reboot"])  # hostapd.conf wurde geändert

    def test_change_detection_and_unchanged_count(self):
        first = update_package.apply(self.staging, dest_root=self.dest)
        self.assertGreaterEqual(len(first["changed"]), 1)
        second = update_package.apply(self.staging, dest_root=self.dest)
        self.assertEqual(second["changed"], [])
        self.assertEqual(second["unchanged_count"], len(first["changed"]))

    def test_rollback_restores_previous_state(self):
        update_package.apply(self.staging, dest_root=self.dest)
        # Blockiere eine Zieldatei mit einem Verzeichnis ->_apply muss fehlschlagen
        blocker = os.path.join(self.dest, "usr/local/sbin/video_link.py")
        os.remove(blocker)
        os.makedirs(blocker)
        staged = os.path.join(self.staging, "web/index.html")
        with open(staged, "w") as f:
            f.write("<html>changed</html>")
        with self.assertRaises(OSError):
            update_package.apply(self.staging, dest_root=self.dest)
        # Rollback: web/index.html wieder auf den alten Stand (nicht "changed")
        web = os.path.join(self.dest, "var/www/video-token/index.html")
        self.assertEqual(open(web).read(), "<html>new</html>")

    def test_version_roundtrip(self):
        old = update_package.VERSION_FILE
        update_package.VERSION_FILE = os.path.join(self.tmp.name, "version.json")
        try:
            self.assertIsNone(update_package.installed_version())
            update_package.save_installed_version("abc1234def5678")
            self.assertEqual(update_package.installed_version()["commit"],
                             "abc1234def5678")
        finally:
            update_package.VERSION_FILE = old


if __name__ == "__main__":
    unittest.main()
