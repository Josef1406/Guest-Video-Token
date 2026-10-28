"""Home-WLAN uplink: the Pi joins the customer's Wi-Fi with a second radio
and renews its own certificate. Video_GB keeps running for guests.

Preferred radio: USB-WLAN stick (wlan1). Fallback: virtual station on the
built-in chip (must share the AP channel, less stable)."""
import datetime
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
import certificate_bridge
import video_link

CONFIG_FILE = Path('/etc/video-token/home-wifi.json')
RUN_DIR = Path('/run/video-token')
BROKER_URL = 'https://guest-video-share.lovable.app/api/public/certificates'
RENEW_BEFORE_DAYS = 30
CHECK_EVERY = 6 * 3600
LOCK = threading.Lock()
STATE = {'phase': 'idle', 'progress': 0, 'message': '', 'last_success': None}

def _set(phase, progress, message):
    STATE.update(phase=phase, progress=progress, message=message)

def run(*args, timeout=30, check=True):
    return subprocess.run(args, check=check, capture_output=True, timeout=timeout, text=True).stdout

def validate(ssid, psk):
    if not isinstance(ssid, str) or not 1 <= len(ssid.encode()) <= 32:
        raise ValueError('Bitte den WLAN-Namen angeben.')
    if not isinstance(psk, str) or not (psk == '' or 8 <= len(psk) <= 63):
        raise ValueError('Das WLAN-Passwort muss 8 bis 63 Zeichen haben.')
    if any(c in ssid + psk for c in '\n\r"\\'):
        raise ValueError('WLAN-Name oder Passwort enthält ungültige Zeichen.')
    if ssid == 'Video_GB':
        raise ValueError('Bitte das Heim-WLAN wählen, nicht das Token-WLAN.')

def save(ssid, psk):
    validate(ssid, psk)
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=CONFIG_FILE.parent, prefix='.home-wifi-')
    with os.fdopen(fd, 'w') as f:
        json.dump({'ssid': ssid, 'psk': psk}, f)
    os.chmod(tmp, 0o600)
    os.replace(tmp, CONFIG_FILE)

def load():
    try:
        data = json.loads(CONFIG_FILE.read_text())
        validate(data['ssid'], data['psk'])
        return data
    except (OSError, ValueError, KeyError, TypeError):
        return None

AP_IP = '192.168.4.1/24'

def _ap_alive():
    return subprocess.run(['systemctl', 'is-active', '--quiet', 'hostapd'],
                          capture_output=True).returncode == 0

def ensure_ap():
    """Bring Video_GB back after the internal chip was borrowed for scan/uplink.
    With a USB stick (wlan1) the AP is untouched and this is a no-op."""
    if Path('/sys/class/net/wlan1').exists() and _ap_alive():
        return
    run('ip', 'addr', 'replace', AP_IP, 'dev', 'wlan0', check=False)
    if not _ap_alive():
        run('systemctl', 'restart', 'hostapd', check=False, timeout=30)
    run('systemctl', 'restart', 'dnsmasq', check=False, timeout=30)
    run('systemctl', 'reload-or-restart', 'nginx', check=False, timeout=30)

HOSTAPD_CONF = Path('/etc/hostapd/hostapd.conf')

def _station_mac():
    """Virtual station needs its own (locally administered) MAC; reusing wlan0's
    MAC makes `ip link set wlsta0 up` fail with 'Name not unique on network'."""
    try:
        mac = Path('/sys/class/net/wlan0/address').read_text().strip().split(':')
        mac[0] = '%02x' % ((int(mac[0], 16) | 0x02) & 0xfe)
        mac[5] = '%02x' % (int(mac[5], 16) ^ 0x01)
        return ':'.join(mac)
    except (OSError, ValueError, IndexError):
        return None

def interface():
    if Path('/sys/class/net/wlan1').exists():
        return 'wlan1'
    if not Path('/sys/class/net/wlsta0').exists():
        mac = _station_mac()
        run('iw', 'dev', 'wlan0', 'interface', 'add', 'wlsta0', 'type', 'managed', *(('addr', mac) if mac else ()))
    return 'wlsta0'

def bring_up(dev):
    result = subprocess.run(['ip', 'link', 'set', dev, 'up'], capture_output=True, text=True, timeout=15)
    if result.returncode:
        raise ValueError('Zweite WLAN-Verbindung am Token konnte nicht gestartet werden (%s). '
                         'Token neu starten und erneut versuchen.' % (result.stderr.strip() or dev))

def parse_channels(scan_output):
    """{ssid: 2.4-GHz channel} from `iw dev X scan` output."""
    found, freq = {}, None
    for line in scan_output.splitlines():
        line = line.strip()
        if line.startswith('BSS '): freq = None
        elif line.startswith('freq:'):
            try: freq = int(float(line.split(':', 1)[1]))
            except ValueError: freq = None
        elif line.startswith('SSID:') and freq and 2412 <= freq <= 2472:
            found.setdefault(line.split(':', 1)[1].strip(), (freq - 2407) // 5)
    return found

def ap_channel():
    try:
        for line in HOSTAPD_CONF.read_text().splitlines():
            if line.startswith('channel='): return int(line.split('=', 1)[1])
    except (OSError, ValueError):
        pass
    return None

def match_ap_channel(dev, ssid):
    """The built-in chip can only use one channel: move Video_GB to the home
    Wi-Fi's channel (guests reconnect automatically after a few seconds)."""
    if dev != 'wlsta0':
        return
    channel = None
    for _ in range(2):
        channel = parse_channels(run('iw', 'dev', dev, 'scan', timeout=20, check=False)).get(ssid)
        if channel: break
        time.sleep(2)
    if not channel:
        raise ValueError('Heim-WLAN „%s“ nicht gefunden (Token braucht 2,4-GHz-WLAN in Reichweite).' % ssid)
    if channel != ap_channel():
        text = HOSTAPD_CONF.read_text()
        lines = [('channel=%d' % channel) if l.startswith('channel=') else l for l in text.splitlines()]
        HOSTAPD_CONF.write_text('\n'.join(lines) + '\n')
        run('systemctl', 'restart', 'hostapd', check=False, timeout=30)
        time.sleep(3)
        if not Path('/sys/class/net/wlsta0').exists():
            interface()
        bring_up(dev)

def scan():
    dev = interface()
    try:
        bring_up(dev)
        names = set()
        for _ in range(2):
            out = run('iw', 'dev', dev, 'scan', timeout=20, check=False)
            names |= {line.split('SSID:', 1)[1].strip() for line in out.splitlines() if 'SSID:' in line}
            if names: break
            time.sleep(2)
        return sorted(n for n in names if n and n != 'Video_GB')
    finally:
        try:
            if dev == 'wlsta0' and Path('/sys/class/net/wlsta0').exists():
                run('iw', 'dev', 'wlsta0', 'del', check=False)
        except (OSError, subprocess.SubprocessError):
            pass
        ensure_ap()

def connect(cfg):
    # Clean up a previous attempt FIRST: disconnect() deletes wlsta0, so it must
    # run before interface() creates the virtual station again.
    disconnect()
    dev = interface()
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    conf = RUN_DIR / 'home-wifi.conf'
    net = 'key_mgmt=NONE' if cfg['psk'] == '' else 'psk="%s"' % cfg['psk']
    conf.write_text('ctrl_interface=/run/video-token/wpa\ncountry=DE\nnetwork={\n ssid="%s"\n %s\n}\n' % (cfg['ssid'], net))
    os.chmod(conf, 0o600)
    bring_up(dev)
    match_ap_channel(dev, cfg['ssid'])
    run('wpa_supplicant', '-B', '-i', dev, '-c', str(conf), '-P', str(RUN_DIR / 'wpa.pid'))
    for _ in range(30):
        status = run('wpa_cli', '-p', '/run/video-token/wpa', '-i', dev, 'status', check=False)
        if 'wpa_state=COMPLETED' in status: break
        time.sleep(1)
    else:
        raise ValueError('Verbindung mit dem Heim-WLAN fehlgeschlagen. Name und Passwort prüfen.')
    if subprocess.run(['which', 'dhcpcd'], capture_output=True).returncode == 0:
        run('dhcpcd', '-4', '-w', '-t', '30', dev, timeout=40, check=False)
    else:
        run('dhclient', '-1', dev, timeout=40, check=False)
    for _ in range(15):
        try:
            urllib.request.urlopen('https://guest-video-share.lovable.app/', timeout=8).close()
            break
        except OSError:
            time.sleep(2)
    else:
        raise ValueError('Heim-WLAN verbunden, aber kein Internet erreichbar.')
    # Real time matters for certificate checks; the Zero has no clock battery.
    run('timedatectl', 'set-ntp', 'true', check=False)
    for _ in range(15):
        if 'yes' in run('timedatectl', 'show', '-p', 'NTPSynchronized', '--value', check=False): break
        time.sleep(2)

def disconnect():
    dev = 'wlan1' if Path('/sys/class/net/wlan1').exists() else 'wlsta0'
    pid = RUN_DIR / 'wpa.pid'
    if pid.exists():
        try: os.kill(int(pid.read_text().strip()), 15)
        except (OSError, ValueError): pass
        pid.unlink(missing_ok=True)
    run('dhcpcd', '-k', dev, check=False, timeout=10) if Path('/usr/sbin/dhcpcd').exists() else None
    if dev == 'wlsta0' and Path('/sys/class/net/wlsta0').exists():
        run('iw', 'dev', 'wlsta0', 'del', check=False)
    ensure_ap()

def post(body):
    req = urllib.request.Request(BROKER_URL, data=json.dumps(body).encode(), method='POST',
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try: return json.loads(e.read())
        except ValueError: return {'error': 'Online-Aussteller antwortet nicht.'}

LABELS = {'creating': 'Auftrag wird angelegt', 'dns': 'Domain wird geprüft', 'validating': 'Domain wird bestätigt',
          'ready': 'Zertifikat wird ausgestellt', 'processing': 'Zertifikat wird ausgestellt', 'valid': 'Zertifikat wird abgeholt',
          'cleanup': 'Abschluss', 'complete': 'Fertig'}

def issue(post_fn=post, activate=certificate_bridge.activate, sleep=time.sleep):
    request = certificate_bridge.renewal()
    for i in range(120):
        result = post_fn(request)
        if result.get('error') and result.get('state') not in LABELS:
            raise ValueError(result['error'])
        if result.get('state') in ('failed', 'failed_cleanup'):
            raise ValueError('Ausstellung fehlgeschlagen. Später automatisch neuer Versuch.')
        if result.get('state') == 'complete' and result.get('chain'):
            if result.get('environment') != 'production':
                raise ValueError('Test-Ausstellung erfolgreich. Die echte Ausstellung ist noch nicht freigeschaltet.')
            return activate({'version': 1, 'device_id': result.get('device_id'),
                             'environment': result['environment'], 'chain': result['chain']})
        _set('issuing', min(90, 50 + i), LABELS.get(result.get('state'), 'Zertifikat wird ausgestellt') + '…')
        sleep(5)
    raise ValueError('Ausstellung dauert zu lange. Später automatisch neuer Versuch.')

def needs_renewal():
    if video_link.load_mode() != 'https' or not (video_link.TLS_DIR / 'device.key').exists():
        return False
    try:
        record = json.loads((video_link.TLS_DIR / 'activation.json').read_text())
        expiry = datetime.datetime.fromisoformat(record['expires_at'])
        return expiry - datetime.datetime.now(datetime.timezone.utc) < datetime.timedelta(days=RENEW_BEFORE_DAYS)
    except (OSError, ValueError, KeyError):
        return True

def renew_now():
    if not LOCK.acquire(blocking=False):
        return
    try:
        cfg = load()
        if not cfg:
            _set('needs_wifi', 0, 'Bitte ein Heim-WLAN eintragen.'); return
        if video_link.load_mode() != 'https':
            _set('idle', 0, 'Zertifikat-Modus ist nicht eingestellt.'); return
        _set('connecting', 15, 'Verbinde mit „%s“…' % cfg['ssid'])
        try:
            connect(cfg)
            _set('issuing', 45, 'Internet verbunden. Zertifikat wird angefordert…')
            result = issue()
            STATE['last_success'] = result.get('expires_at')
            _set('done', 100, 'Zertifikat erneuert und HTTPS aktiv.')
        except (ValueError, OSError, subprocess.SubprocessError) as error:
            _set('error', 0, str(error) or 'Erneuerung fehlgeschlagen.')
        finally:
            try: disconnect()
            except (OSError, subprocess.SubprocessError): pass
    finally:
        LOCK.release()

def start():
    threading.Thread(target=renew_now, daemon=True).start()

def status():
    cfg = load()
    return {**STATE, 'configured': cfg is not None, 'ssid': cfg['ssid'] if cfg else None,
            'busy': LOCK.locked(), 'radio': 'usb' if Path('/sys/class/net/wlan1').exists() else 'internal'}

def background():
    def loop():
        time.sleep(90)
        while True:
            if load() and needs_renewal():
                renew_now()
            time.sleep(CHECK_EVERY)
    threading.Thread(target=loop, daemon=True).start()
