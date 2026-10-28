(async function () {
  const state = document.getElementById('welcome-state');
  const normal = document.getElementById('normal-mode');
  const secure = document.getElementById('https-mode');
  const instruction = document.getElementById('scan-instruction');
  const isPreview = document.documentElement.dataset.preview === 'true';
  if (isPreview) {
    state.textContent = 'Vorschau · keine Verbindung zum Raspberry Pi';
    normal.hidden = false;
    document.getElementById('accept-form').hidden = true;
    document.querySelectorAll('a').forEach(a => a.addEventListener('click', e => {
      e.preventDefault();
      state.textContent = 'Bitte diese Seite im WLAN Video_GB unter http://192.168.4.1 öffnen.';
    }));
    return;
  }
  try {
    const response = await fetch('/api/public/video-link', { cache: 'no-store' });
    if (!response.ok) throw new Error('Token-Einstellungen nicht erreichbar.');
    const settings = await response.json();
    const https = settings.mode === 'https';
    state.textContent = https ? 'HTTPS-Modus · Einrichtung ausstehend' : 'Normalmodus · lokale Video-QRs';
    normal.hidden = https;
    secure.hidden = !https;
    if (https) {
      document.getElementById('certificate-message').textContent = settings.certificate.message;
      instruction.textContent = 'Öffne nach der WLAN-Anmeldung in Safari http://192.168.4.1. Die Zertifikatseinrichtung muss abgeschlossen sein, bevor Cloud-QRs direkt über die Kamera funktionieren.';
    }
  } catch (error) {
    state.textContent = error.message + ' Bitte die Seite neu laden oder den Admin verständigen.';
    state.classList.add('welcome-error');
  }
})();