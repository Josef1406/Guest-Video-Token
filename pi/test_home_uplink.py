from pathlib import Path
import sys, tempfile, unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).parent))
import home_uplink as up

class HomeUplinkRules(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.orig = up.CONFIG_FILE
        up.CONFIG_FILE = Path(self.tmp.name) / 'home-wifi.json'
    def tearDown(self):
        up.CONFIG_FILE = self.orig; self.tmp.cleanup()
    def test_password_saved_private_and_never_in_status(self):
        up.save('Heim', 'geheim123')
        self.assertEqual(up.CONFIG_FILE.stat().st_mode & 0o777, 0o600)
        self.assertNotIn('geheim123', str(up.status()))
    def test_rejects_token_wlan_and_short_password(self):
        with self.assertRaises(ValueError): up.save('Video_GB', 'geheim123')
        with self.assertRaises(ValueError): up.save('Heim', 'kurz')
        with self.assertRaises(ValueError): up.save('Heim"\n}', 'geheim123')
    def test_production_chain_is_activated(self):
        got = {}
        with patch.object(up.certificate_bridge, 'renewal', return_value={'payload': 'p'}):
            up.issue(lambda b: {'state': 'complete', 'environment': 'production', 'device_id': 'd', 'chain': 'C'},
                     lambda bundle: got.update(bundle) or {'expires_at': 'x'}, lambda s: None)
        self.assertEqual(got, {'version': 1, 'device_id': 'd', 'environment': 'production', 'chain': 'C'})
    def test_staging_chain_is_not_activated(self):
        with patch.object(up.certificate_bridge, 'renewal', return_value={}):
            with self.assertRaises(ValueError):
                up.issue(lambda b: {'state': 'complete', 'environment': 'staging', 'chain': 'C'},
                         lambda b: self.fail('activated'), lambda s: None)

if __name__ == '__main__': unittest.main()
