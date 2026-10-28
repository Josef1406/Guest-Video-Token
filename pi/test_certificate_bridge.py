import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import certificate_bridge as bridge
import video_link

class CertificateBridgeRules(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config = video_link.CONFIG_FILE
        self.tls = video_link.TLS_DIR
        video_link.CONFIG_FILE = Path(self.tmp.name) / 'mode.json'
        video_link.TLS_DIR = Path(self.tmp.name) / 'tls'
        video_link.save_mode('https')

    def tearDown(self):
        video_link.CONFIG_FILE = self.config
        video_link.TLS_DIR = self.tls
        self.tmp.cleanup()

    def test_enrollment_transports_only_public_csr(self):
        result = bridge.enrollment()
        self.assertIn('BEGIN CERTIFICATE REQUEST', result['csr'])
        self.assertNotIn('PRIVATE KEY', json.dumps(result))
        self.assertEqual(set(result), {'version', 'device_id', 'csr'})

    def test_renewal_is_idempotent_and_does_not_select_a_csr(self):
        bridge.enrollment()
        first = bridge.renewal()
        self.assertEqual(first, bridge.renewal())
        self.assertEqual(set(first), {'payload', 'signature'})
        self.assertNotIn('PRIVATE KEY', json.dumps(first))

    def test_direct_mode_cannot_trigger_renewal(self):
        bridge.enrollment()
        video_link.save_mode('normal')
        with self.assertRaises(ValueError): bridge.renewal()

    def test_staging_cannot_activate_https(self):
        bridge.enrollment()
        with self.assertRaises(ValueError):
            bridge.activate({'version': 1, 'environment': 'staging', 'device_id': bridge.identity(), 'chain': 'test'})
        self.assertFalse((video_link.TLS_DIR / 'activation.json').exists())

    def test_wrong_device_cannot_activate_https(self):
        bridge.enrollment()
        with self.assertRaises(ValueError):
            bridge.activate({'version': 1, 'environment': 'production', 'device_id': 'wrong', 'chain': 'test'})

    def test_failed_activation_restores_old_nginx_configuration(self):
        bridge.enrollment()
        include = Path(self.tmp.name) / 'tls.conf'
        include.write_text('old-config')
        bundle = {'version': 1, 'environment': 'production', 'device_id': bridge.identity(), 'chain': 'test'}
        with patch.object(bridge, 'TLS_INCLUDE', include), patch.object(bridge, 'inspect', return_value='2030-01-01T00:00:00+00:00'), patch.object(bridge, 'run', side_effect=OSError('nginx failed')):
            with self.assertRaises(OSError): bridge.activate(bundle)
        self.assertEqual(include.read_text(), 'old-config')
        self.assertFalse((video_link.TLS_DIR / 'activation.json').exists())

if __name__ == '__main__': unittest.main()