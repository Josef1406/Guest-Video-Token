"""Public-file bridge. Device private key never leaves the Pi."""
import base64
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import socket
import ssl
import subprocess
import tempfile
import threading
import uuid
import video_link

BRIDGE_LOCK = threading.Lock()
TLS_INCLUDE = Path('/etc/nginx/conf.d/video-token-tls.conf')
TRUST_FILE = '/etc/ssl/certs/ca-certificates.crt'

def run(*args):
    return subprocess.run(args, check=True, capture_output=True, timeout=20).stdout

def identity():
    file = video_link.TLS_DIR / 'device-id'
    if not file.exists():
        file.write_text(str(uuid.uuid4()))
        os.chmod(file, 0o600)
    return file.read_text().strip()

def enrollment():
    csr = video_link.prepare_csr()
    return {'version': 1, 'device_id': identity(), 'csr': csr['csr']}

def renewal():
    if video_link.load_mode() != 'https':
        raise ValueError('Erneuerung ist nur im Zertifikat-Modus möglich.')
    with BRIDGE_LOCK:
        if not (video_link.TLS_DIR / 'device.key').exists():
            raise ValueError('Bitte zuerst den Admin um die Token-Freigabe bitten.')
        saved = video_link.TLS_DIR / 'renewal-request.json'
        if saved.exists():
            return json.loads(saved.read_text())
        payload = json.dumps({'version': 1, 'device_id': identity(), 'request_id': str(uuid.uuid4()), 'purpose': 'renew'}, separators=(',', ':')).encode()
        with tempfile.NamedTemporaryFile(dir=video_link.TLS_DIR) as file:
            file.write(payload); file.flush()
            signature = run('openssl', 'dgst', '-sha256', '-sign', str(video_link.TLS_DIR / 'device.key'), file.name)
        enc = lambda data: base64.urlsafe_b64encode(data).decode().rstrip('=')
        result = {'payload': enc(payload), 'signature': enc(signature)}
        saved.write_text(json.dumps(result)); os.chmod(saved, 0o600)
        return result

def inspect(chain_file):
    leaf = chain_file.parent / 'leaf.pem'
    blocks = re.findall(r'-----BEGIN CERTIFICATE-----[\s\S]+?-----END CERTIFICATE-----', chain_file.read_text())
    if not 2 <= len(blocks) <= 8:
        raise ValueError('Vollständige Zertifikatskette fehlt.')
    leaf.write_text(blocks[0] + '\n')
    intermediates = chain_file.parent / 'intermediates.pem'
    intermediates.write_text('\n'.join(blocks[1:]) + '\n')
    # Current Pi time is trusted only through its configured OS clock; never
    # accept a phone-provided time to bypass certificate validity checking.
    run('openssl', 'verify', '-CAfile', TRUST_FILE, '-untrusted', str(intermediates), '-purpose', 'sslserver', '-verify_hostname', video_link.DOMAIN, str(leaf))
    san = run('openssl', 'x509', '-in', str(leaf), '-noout', '-ext', 'subjectAltName').decode().splitlines()[1:]
    if ''.join(san).strip() != 'DNS:' + video_link.DOMAIN:
        raise ValueError('Zertifikat ist nicht ausschließlich für die Video-Domain.')
    cert_pub = run('openssl', 'x509', '-in', str(leaf), '-pubkey', '-noout')
    key_pub = run('openssl', 'pkey', '-in', str(video_link.TLS_DIR / 'device.key'), '-pubout')
    if cert_pub.strip() != key_pub.strip():
        raise ValueError('Zertifikat gehört nicht zum Schlüssel dieses Pi.')
    run('openssl', 'x509', '-in', str(leaf), '-checkend', '3600', '-noout')
    expiry = run('openssl', 'x509', '-in', str(leaf), '-enddate', '-noout').decode().strip().split('=', 1)[1]
    date = datetime.datetime.strptime(expiry, '%b %d %H:%M:%S %Y %Z').replace(tzinfo=datetime.timezone.utc)
    return date.isoformat()

def config(chain):
    # Only video/static guest files on HTTPS. No administration or listings.
    return '''server {
 listen 443 ssl;
 server_name video.gaestebuch.cloud;
 ssl_certificate %s;
 ssl_certificate_key %s;
 ssl_protocols TLSv1.2 TLSv1.3;
 root /var/www/video-token;
 location ~ ^/v/([^/]+)/([^/]+\\.mp4)$ { rewrite ^ /v.html?e=$1&f=$2 last; }
 location ~ ^/media/(?<ev>[^/]+)/(?<fn>[^/]+\\.mp4)$ {
  alias /srv/videos/$ev/$fn; default_type video/mp4; sendfile on;
 }
 location = /v.html { try_files /v.html =404; }
 location /assets/ { try_files $uri =404; }
 location / { return 404; }
}
''' % (chain, video_link.TLS_DIR / 'device.key')

def activate(bundle):
    if video_link.load_mode() != 'https':
        raise ValueError('Zertifikat-Modus ist nicht eingestellt.')
    if not isinstance(bundle, dict) or bundle.get('version') != 1 or bundle.get('environment') != 'production':
        raise ValueError('Nur echte, vertrauenswürdige Zertifikate können aktiviert werden; kein Testzertifikat.')
    if bundle.get('device_id') != identity():
        raise ValueError('Zertifikat ist für einen anderen Token.')
    chain = bundle.get('chain')
    if not isinstance(chain, str) or len(chain) > 32768 or 'PRIVATE KEY' in chain:
        raise ValueError('Zertifikatsdatei ungültig.')
    with BRIDGE_LOCK:
        staging = Path(tempfile.mkdtemp(prefix='chain-', dir=video_link.TLS_DIR))
        chain_file = staging / 'fullchain.pem'
        chain_file.write_text(chain)
        old_config = TLS_INCLUDE.read_bytes() if TLS_INCLUDE.exists() else None
        changed = False
        try:
            expiry = inspect(chain_file)
            previous = video_link.TLS_DIR / 'activation.json'
            if previous.exists():
                old = json.loads(previous.read_text())
                if old.get('expires_at', '') > expiry:
                    raise ValueError('Ein neueres Zertifikat ist bereits installiert.')
            TLS_INCLUDE.parent.mkdir(parents=True, exist_ok=True)
            pending = TLS_INCLUDE.with_suffix('.pending')
            pending.write_text(config(chain_file)); os.replace(pending, TLS_INCLUDE); changed = True
            run('nginx', '-t'); run('systemctl', 'reload', 'nginx')
            context = ssl.create_default_context(cafile=TRUST_FILE)
            with socket.create_connection(('127.0.0.1', 443), timeout=5) as connection:
                with context.wrap_socket(connection, server_hostname=video_link.DOMAIN) as secure:
                    served = secure.getpeercert(binary_form=True)
            expected = ssl.PEM_cert_to_DER_cert((staging / 'leaf.pem').read_text())
            if served != expected:
                raise ValueError('HTTPS liefert noch nicht das neue Zertifikat. Bitte erneut versuchen.')
            previous.write_text(json.dumps({'expires_at': expiry, 'chain': str(chain_file)}))
            (video_link.TLS_DIR / 'renewal-request.json').unlink(missing_ok=True)
            return {'ready': True, 'expires_at': expiry}
        except Exception:
            if changed:
                if old_config is None: TLS_INCLUDE.unlink(missing_ok=True)
                else: TLS_INCLUDE.write_bytes(old_config)
                try: run('nginx', '-t'); run('systemctl', 'reload', 'nginx')
                except subprocess.SubprocessError: pass
            shutil.rmtree(staging, ignore_errors=True)
            raise

def certificate_status():
    available = (video_link.TLS_DIR / 'device.key').exists()
    state = {'state': 'renewal_required' if available else 'setup_required', 'ready': False,
             'renewal_available': available, 'expires_at': None,
             'message': 'Zertifikat über das Handy erneuern.' if available else 'Bitte den Admin um die einmalige Token-Freigabe bitten.'}
    try:
        record = json.loads((video_link.TLS_DIR / 'activation.json').read_text())
        expiry = datetime.datetime.fromisoformat(record['expires_at'])
        if expiry > datetime.datetime.now(datetime.timezone.utc) and TLS_INCLUDE.exists():
            # Confirm both local certificate validity and currently served TLS.
            context = ssl.create_default_context(cafile=TRUST_FILE)
            with socket.create_connection(('127.0.0.1', 443), timeout=3) as connection:
                with context.wrap_socket(connection, server_hostname=video_link.DOMAIN): pass
            state.update(state='active', ready=True, expires_at=record['expires_at'], message='Zertifikat geprüft und HTTPS aktiv.')
    except (OSError, ValueError, KeyError, ssl.SSLError):
        pass
    return state