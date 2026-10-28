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
    def test_scan_restores_ap_after_borrowing_internal_chip(self):
        calls = []
        def fake_run(*args, **kw):
            calls.append(args)
            return 'SSID: Heim\n' if 'scan' in args else ''
        with patch.object(up, 'interface', return_value='wlsta0'), \
             patch.object(up, 'run', side_effect=fake_run), \
             patch.object(up, 'ensure_ap') as ap, \
             patch.object(up.Path, 'exists', return_value=True):
            self.assertEqual(up.scan(), ['Heim'])
        ap.assert_called_once()
        self.assertIn(('iw', 'dev', 'wlsta0', 'del'), calls)
    def test_scan_restores_ap_even_on_error(self):
        with patch.object(up, 'interface', return_value='wlsta0'), \
             patch.object(up, 'run', side_effect=OSError('boom')), \
             patch.object(up, 'ensure_ap') as ap, \
             patch.object(up.Path, 'exists', return_value=True):
            with self.assertRaises(OSError): up.scan()
        ap.assert_called_once()
    def test_connect_cleans_up_before_creating_station(self):
        order = []
        with patch.object(up, 'disconnect', side_effect=lambda **k: order.append('disconnect')), \
             patch.object(up, 'interface', side_effect=lambda: order.append('interface') or 'wlsta0'), \
             patch.object(up, 'bring_up', side_effect=lambda d: (_ for _ in ()).throw(ValueError('stop'))), \
             patch.object(up, 'RUN_DIR', Path(self.tmp.name)):
            with self.assertRaises(ValueError): up.connect({'ssid': 'Heim', 'psk': 'geheim123'})
        self.assertEqual(order, ['disconnect', 'interface'])
    def _renew_with(self, connect_effect):
        order = []
        up.save('Heim', 'geheim123')
        with patch.object(up.video_link, 'load_mode', return_value='https'), \
             patch.object(up, 'shared_radio', return_value=True), \
             patch.object(up.time, 'sleep'), \
             patch.object(up, 'pause_ap', side_effect=lambda: order.append('pause')), \
             patch.object(up, 'connect', side_effect=lambda c: order.append('connect') or connect_effect()), \
             patch.object(up, 'issue', side_effect=lambda: order.append('issue') or {'expires_at': 'x'}), \
             patch.object(up, 'disconnect', side_effect=lambda: order.append('restore')):
            up.renew_now()
        return order
    def test_internal_radio_pauses_ap_before_connecting_and_restores_after(self):
        self.assertEqual(self._renew_with(lambda: None), ['pause', 'connect', 'issue', 'restore'])
        self.assertEqual(up.STATE['phase'], 'done')
    def test_ap_is_restored_even_when_home_wifi_fails(self):
        def fail(): raise ValueError('Heim-WLAN nicht erreichbar')
        self.assertEqual(self._renew_with(fail), ['pause', 'connect', 'restore'])
        self.assertEqual(up.STATE['phase'], 'error')
    def test_pause_arms_safety_timer_before_stopping_ap(self):
        cmds = []
        with patch.object(up, 'run', side_effect=lambda *a, **k: cmds.append(a) or ''):
            up.pause_ap()
        timer = next(i for i, c in enumerate(cmds) if c[0] == 'systemd-run')
        stop = cmds.index(('systemctl', 'stop', 'dnsmasq', 'hostapd'))
        self.assertLess(timer, stop)
        self.assertIn('/usr/local/sbin/switch-mode', cmds[timer])
    def test_ensure_ap_restarts_hostapd_only_when_down(self):
        states = iter([1, 0])  # first check: down, second: up
        cmds = []
        def fake_run(*args, **kw):
            cmds.append(args); return ''
        class FakeCompleted:
            def __init__(self, rc): self.returncode = rc
        with patch.object(up.subprocess, 'run', side_effect=lambda *a, **k: FakeCompleted(next(states))), \
             patch.object(up, 'run', side_effect=fake_run), \
             patch.object(up.Path, 'exists', return_value=False):
            up.ensure_ap()
        self.assertIn(('systemctl', 'restart', 'hostapd'), cmds)
        self.assertIn(('systemctl', 'restart', 'dnsmasq'), cmds)

if __name__ == '__main__': unittest.main()
