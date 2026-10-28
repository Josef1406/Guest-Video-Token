(function () {
  const state = document.getElementById('welcome-state');
  const normal = document.getElementById('normal-mode');
  const secure = document.getElementById('https-mode');
  const instruction = document.getElementById('scan-instruction');
  const instructions = document.getElementById('video-instructions');
  const directInstruction = 'Öffne die normale Handy-Kamera und scanne den QR-Code auf deinem Video-Botschaft-Aufkleber.';
  const isPreview = document.documentElement.dataset.preview === 'true';
  let requestId = 0;
  if (isPreview) {
    state.textContent = 'Vorschau · keine Verbindung zum Raspberry Pi';
    normal.hidden = false;
    instructions.hidden = false;
    instruction.textContent = directInstruction;
    document.getElementById('accept-form').hidden = true;
    document.querySelectorAll('a').forEach(a => a.addEventListener('click', e => {
      e.preventDefault();
      state.textContent = 'Bitte diese Seite im WLAN Video_GB unter http://192.168.4.1 öffnen.';
    }));
    return;
  }
  async function refreshMode() {
    const currentRequest = ++requestId;
    state.classList.remove('welcome-error');
    try {
    const response = await fetch('/api/public/video-link', { cache: 'no-store' });
    if (!response.ok) throw new Error('Token-Einstellungen nicht erreichbar.');
    const settings = await response.json();
    if (currentRequest !== requestId) return;
    if (settings.mode !== 'normal' && settings.mode !== 'https') {
      throw new Error('Token-Einstellung ungültig. Bitte den Admin verständigen.');
    }
    const https = settings.mode === 'https';
    const certificate = settings.certificate;
    const expiry = Date.parse(certificate?.expires_at);
    const ready = https && certificate?.ready === true && Number.isFinite(expiry) && expiry > Date.now();
    state.textContent = https ? (ready ? 'Zertifikat-Modus · bereit zum Scannen' : 'Zertifikat-Modus · noch nicht bereit') : 'Direkt-Modus · lokale Video-QRs';
    normal.hidden = https && !ready;
    secure.hidden = !https || ready;
    instructions.hidden = https && !ready;
    document.getElementById('scan-ready-title').textContent = ready ? 'Zertifikat aktiv. Dein Video ist bereit.' : 'Dein QR-Code ist der direkte Weg.';
    document.getElementById('scan-ready-message').textContent = ready
      ? 'Bleibe im WLAN Video_GB. Öffne die normale Handy-Kamera und scanne den Cloud-QR auf deinem Video-Botschaft-Aufkleber.'
      : 'Kamera öffnen, QR-Code scannen – dein Video öffnet sich direkt vom Token. Dafür müssen die mobilen Daten eingeschaltet sein.';
    instruction.textContent = directInstruction;
    if (https) {
      document.getElementById('renew-certificate').disabled = certificate?.renewal_available !== true;
      document.getElementById('certificate-message').textContent = certificate?.message || 'Bitte den Admin wegen der Zertifikatseinrichtung verständigen.';
      document.getElementById('certificate-state').textContent = ready ? 'Zertifikat geprüft und aktiv' : certificate?.state === 'setup_required' ? 'Einrichtung noch ausstehend' : 'Kein gültiges, aktiviertes Zertifikat';
      document.getElementById('certificate-validity').textContent = Number.isFinite(expiry) ? 'Gültig bis: ' + new Date(expiry).toLocaleString('de-DE') : 'Noch kein gültiges Zertifikat vorhanden.';
      document.getElementById('scan-certificate-validity').textContent = ready ? 'Zertifikat gültig bis: ' + new Date(expiry).toLocaleString('de-DE') : '';
    } else {
      document.getElementById('scan-certificate-validity').textContent = '';
    }
  } catch (error) {
    if (currentRequest !== requestId) return;
    normal.hidden = true;
    secure.hidden = true;
    instructions.hidden = true;
    state.textContent = error.message + ' Bitte die Seite neu laden oder den Admin verständigen.';
    state.classList.add('welcome-error');
  }
  }
  // Re-read the Pi's saved selection, including after returning from Admin.
  window.addEventListener('pageshow', refreshMode);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') refreshMode();
  });
  refreshMode();
  // Observe verified Pi activation without changing the Admin's saved mode.
  window.setInterval(() => {
    if (document.visibilityState === 'visible') refreshMode();
  }, 10000);
})();