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

def interface():
    if Path('/sys/class/net/wlan1').exists():
        return 'wlan1'
    if not Path('/sys/class/net/wlsta0').exists():
        run('iw', 'dev', 'wlan0', 'interface', 'add', 'wlsta0', 'type', 'managed')
    return 'wlsta0'

def scan():
    dev = interface()
    run('ip', 'link', 'set', dev, 'up')
    names = set()
    for _ in range(2):
        out = run('iw', 'dev', dev, 'scan', timeout=20, check=False)
        names |= {line.split('SSID:', 1)[1].strip() for line in out.splitlines() if 'SSID:' in line}
        if names: break
        time.sleep(2)
    return sorted(n for n in names if n and n != 'Video_GB')

def connect(cfg):
    dev = interface()
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    conf = RUN_DIR / 'home-wifi.conf'
    net = 'key_mgmt=NONE' if cfg['psk'] == '' else 'psk="%s"' % cfg['psk']
    conf.write_text('ctrl_interface=/run/video-token/wpa\ncountry=DE\nnetwork={\n ssid="%s"\n %s\n}\n' % (cfg['ssid'], net))
    os.chmod(conf, 0o600)
    disconnect()
    run('ip', 'link', 'set', dev, 'up')
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
