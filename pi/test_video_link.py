import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("video_link", Path(__file__).with_name("video_link.py"))
video_link = importlib.util.module_from_spec(spec)
spec.loader.exec_module(video_link)


class VideoLinkRules(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        video_link.CONFIG_FILE = Path(self.tmp.name) / "video-link.json"
        video_link.TLS_DIR = Path(self.tmp.name) / "tls"

    def tearDown(self):
        self.tmp.cleanup()

    def test_normal_defaults_to_existing_ip_without_certificate(self):
        state = video_link.status()
        self.assertEqual(state["mode"], "normal")
        self.assertEqual(state["base_url"], "http://192.168.4.1")
        self.assertIsNone(state["certificate"])

    def test_https_uses_exact_cloud_domain_and_persists(self):
        video_link.save_mode("https")
        self.assertEqual(json.loads(video_link.CONFIG_FILE.read_text()), {"mode": "https"})
        self.assertEqual(video_link.status()["base_url"], "https://video.gaestebuch.cloud")
        self.assertEqual(video_link.load_mode(), "https")

    def test_unconfigured_renewal_never_claims_success(self):
        video_link.save_mode("https")
        self.assertFalse(video_link.status()["certificate"]["ready"])
        self.assertFalse(video_link.status()["certificate"]["renewal_available"])

    def test_saved_selection_survives_module_restart_for_both_modes(self):
        for mode in ("https", "normal"):
            video_link.save_mode(mode)
            restarted = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(restarted)
            restarted.CONFIG_FILE = video_link.CONFIG_FILE
            self.assertEqual(restarted.status()["mode"], mode)

    def test_rejects_other_modes_without_changing_selection(self):
        video_link.save_mode("https")
        with self.assertRaises(ValueError):
            video_link.save_mode("client")
        self.assertEqual(video_link.load_mode(), "https")

    def test_normal_cannot_prepare_certificate(self):
        with self.assertRaises(ValueError):
            video_link.prepare_csr()
        self.assertFalse(video_link.TLS_DIR.exists())

    def test_csr_keeps_private_key_local_and_reuses_it(self):
        video_link.save_mode("https")
        result = video_link.prepare_csr()
        key = (video_link.TLS_DIR / "device.key").read_bytes()
        self.assertIn("BEGIN CERTIFICATE REQUEST", result["csr"])
        self.assertNotIn("PRIVATE KEY", json.dumps(result))
        self.assertFalse(result["certificate_ready"])
        self.assertEqual((video_link.TLS_DIR / "device.key").stat().st_mode & 0o777, 0o600)
        video_link.prepare_csr()
        self.assertEqual((video_link.TLS_DIR / "device.key").read_bytes(), key)


if __name__ == "__main__":
    unittest.main()

class CloudDomainDns(unittest.TestCase):
    def test_normal_mode_does_not_answer_cloud_domain_locally(self):
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "https.conf"
            with patch.object(video_link, "HTTPS_DNS_FILE", f), patch.object(video_link.subprocess, "run"):
                video_link.apply_dns("https")
                self.assertIn("address=/video.gaestebuch.cloud/192.168.4.1", f.read_text())
                video_link.apply_dns("normal")
                self.assertFalse(f.exists())

    def test_base_config_hijacks_only_captive_checks(self):
        conf = (Path(__file__).parent / "config" / "dnsmasq.conf").read_text()
        self.assertNotIn("address=/#/", conf)
        self.assertNotIn("address=/video.gaestebuch.cloud/", conf)
        self.assertIn("address=/captive.apple.com/192.168.4.1", conf)


class ThreeGuestModes(unittest.TestCase):
    def test_cloud_and_local_modes_persist_and_use_token_address(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d, patch.object(video_link, "CONFIG_FILE", Path(d) / "m.json"), \
             patch.object(video_link, "apply_dns"):
            for mode in ("cloud", "local", "normal"):
                video_link.save_mode(mode)
                self.assertEqual(video_link.load_mode(), mode)
                self.assertEqual(video_link.status()["base_url"], "http://192.168.4.1")
