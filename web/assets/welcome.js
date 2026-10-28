(function () {
  const state = document.getElementById('welcome-state');
  const normal = document.getElementById('normal-mode');
  const secure = document.getElementById('https-mode');
  const instruction = document.getElementById('scan-instruction');
  const instructions = document.getElementById('video-instructions');
  const directInstruction = 'Öffne die normale Handy-Kamera und scanne den QR-Code auf deinem Video-Botschaft-Aufkleber.';
  const isPreview = document.documentElement.dataset.preview === 'true';
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
    normal.hidden = true;
    secure.hidden = true;
    instructions.hidden = true;
    state.classList.remove('welcome-error');
    state.textContent = 'Token-Einstellungen werden geladen…';
    try {
    const response = await fetch('/api/public/video-link', { cache: 'no-store' });
    if (!response.ok) throw new Error('Token-Einstellungen nicht erreichbar.');
    const settings = await response.json();
    if (settings.mode !== 'normal' && settings.mode !== 'https') {
      throw new Error('Token-Einstellung ungültig. Bitte den Admin verständigen.');
    }
    const https = settings.mode === 'https';
    state.textContent = https ? 'Zertifikat-Modus · Einrichtung ausstehend' : 'Direkt-Modus · lokale Video-QRs';
    normal.hidden = https;
    secure.hidden = !https;
    instructions.hidden = false;
    instruction.textContent = directInstruction;
    if (https) {
      document.getElementById('certificate-message').textContent = settings.certificate?.message || 'Bitte den Admin wegen der Zertifikatseinrichtung verständigen.';
      instruction.textContent = 'Öffne nach der WLAN-Anmeldung in Safari http://192.168.4.1. Die Zertifikatseinrichtung muss abgeschlossen sein, bevor Cloud-QRs direkt über die Kamera funktionieren.';
    }
  } catch (error) {
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
})();